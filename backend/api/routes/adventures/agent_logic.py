import logging
import os
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.turn_context_helpers import (
    _find_active_sequence,
    resolve_sequence_guidance,
)
from backend.api.routes.adventures.turn_llm_pipeline import TurnLlmContextBuilder
from backend.core.llm_router import GameMasterLLM
from backend.core.prompts import AGENT_PLAYER_TURN_SYSTEM_PROMPT
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity
from backend.utils.path_security import (
    ensure_within_data_dir,
    safe_data_path,
    sanitize_path_component,
)

logger = logging.getLogger(__name__)


def _resolve_session_issue_log_path(session_id: str) -> str:
    """Return the validated AGENTS.md path for a concrete session id."""
    safe_session_id = sanitize_path_component(session_id)
    if not safe_session_id:
        raise ValueError("Invalid session identifier.")

    session_dir = safe_data_path("adventures", "sessions", safe_session_id)
    if not os.path.isdir(session_dir):
        raise ValueError("Session directory does not exist.")

    return ensure_within_data_dir(os.path.join(session_dir, "AGENTS.md"))


class AgentDecision(BaseModel):
    thoughts: str = Field(
        description="Internal reasoning and goals based on the character persona, situation, and walkthrough."
    )
    action: str = Field(
        description="The next action or slash command to execute (e.g. '/inspect shelf', 'go north', '/say Hello')."
    )
    is_stuck_or_bug: bool = Field(
        description="True if an error, bug, or unsolvable puzzle prevents proceeding."
    )
    issue_description: str = Field(
        description="Description of the bug, error, or blocker if is_stuck_or_bug is true. Otherwise empty."
    )


def _resolve_current_scene(ctx: Any, state: Any) -> Any:
    current_scene = getattr(ctx, "current_scene", None)
    if current_scene or not hasattr(ctx, "all_scenes"):
        return current_scene
    cur_id = getattr(state, "current_scene_id", None)
    if not cur_id:
        return None
    return next((s for s in ctx.all_scenes if s.id == cur_id), None)


def _format_npcs_context(entities: list[Any]) -> str:
    visible_npcs = [
        e
        for e in entities
        if getattr(e, "entity_type", "") == "NPC" and not getattr(e, "is_hidden", False)
    ]
    if not visible_npcs:
        return "PRESENT CHARACTERS (NPCs): None"
    lines = [
        f"- {npc.name}: {npc.description or 'Present in the scene.'}"
        for npc in visible_npcs
        if getattr(npc, "name", None)
    ]
    return "PRESENT CHARACTERS (NPCs):\n" + "\n".join(lines)


def _format_exits_context(exits: list[Any]) -> str:
    visible_exits = [e for e in exits if not getattr(e, "is_hidden", False)]
    if not visible_exits:
        return "VISIBLE EXITS: No visible exits."

    exit_lines: list[str] = []
    for e in visible_exits:
        label = getattr(e, "label", "Door")
        is_locked = getattr(e, "is_locked", False)
        lock_desc = getattr(e, "lock_description", None)
        if is_locked and lock_desc:
            exit_lines.append(f"- {label} [LOCKED: {lock_desc}]")
        elif is_locked:
            exit_lines.append(f"- {label} [LOCKED]")
        else:
            exit_lines.append(f"- {label} [OPEN]")
    return "VISIBLE EXITS:\n" + "\n".join(exit_lines)


def build_player_perception_context(adventure: Any, state: Any, ctx: Any) -> str:
    """Builds legitimate, player-facing world context for the PlayAgent.

    Enforces fair play: a normal player only sees:
    - Adventure title and premise
    - Current scene name and public description
    - Visible NPCs present in this scene
    - Visible exits leading out of this scene

    Hidden objects, hidden doors, container unlock codes, and Game Master
    secret notes are strictly excluded to preserve fair player constraints.
    """
    parts: list[str] = []

    title = getattr(adventure, "title", "Adventure") or "Adventure"
    desc = getattr(adventure, "description", "") or ""
    parts.append(f"ADVENTURE: {title}\nPREMISE: {desc}" if desc else f"ADVENTURE: {title}")

    current_scene = _resolve_current_scene(ctx, state)
    if current_scene:
        parts.append(f"CURRENT LOCATION: {current_scene.label or current_scene.id}")
        if getattr(current_scene, "description", None):
            parts.append(f"SCENE DESCRIPTION: {current_scene.description}")

    entities = getattr(ctx, "entities", []) or []
    parts.append(_format_npcs_context(entities))

    exits = getattr(ctx, "exits", []) or []
    parts.append(_format_exits_context(exits))

    if not entities and not exits and not current_scene:
        fallback = getattr(ctx, "mechanics_system_prompt", "")
        if fallback:
            parts.append(f"SCENARIO CONTEXT:\n{fallback}")

    return "\n\n".join(parts)


def _collect_visible_scene_item_names(
    scene_entities: list[WorldEntity],
    states: dict[str, Any],
    current_scene_id: str | None,
) -> list[str]:
    container_payloads = [
        {
            "item_type": states.get(e.id, {}).get("item_type", e.item_type)
            if isinstance(states, dict)
            else e.item_type,
            "inventory": states.get(e.id, {}).get("inventory", e.inventory)
            if isinstance(states, dict)
            else e.inventory,
        }
        for e in scene_entities
    ]
    contained_ids = AdventureLogic.collect_container_item_ids(container_payloads)

    visible_names: list[str] = []
    for entity in scene_entities:
        e_state = states.get(entity.id, {}) if isinstance(states, dict) else {}
        if e_state.get("current_scene_id", entity.current_scene_id) != current_scene_id:
            continue
        if bool(e_state.get("is_hidden", entity.is_hidden)):
            continue
        if bool(e_state.get("is_in_inventory", entity.is_in_inventory)):
            continue
        if str(entity.id or "") in contained_ids:
            continue
        if entity.name:
            visible_names.append(entity.name)
    return visible_names


def _build_agent_objective_and_walkthrough(
    adventure: Any,
    state: Any,
    agent_state: dict[str, Any],
) -> tuple[str, str]:
    monkey_mode = bool(agent_state.get("monkey_mode", False))
    allow_walkthrough = bool(agent_state.get("allow_walkthrough", True))

    if monkey_mode:
        objective = (
            "MONKEY MODE (ROBUSTNESS TEST) IS ACTIVE.\n"
            "Your objective is to stress-test the engine by intentionally trying edge cases and bad inputs.\n"
            "Prefer actions that challenge validation (unknown commands, malformed commands, impossible interactions).\n"
            "Do NOT include harmful or illegal content. Stay safe, but be chaotic."
        )
        return objective, "Monkey mode active."

    if not allow_walkthrough:
        walkthrough_text = (
            "WALKTHROUGH ACCESS: DISABLED\n"
            "You do NOT have access to any walkthrough, solution guides, or sequence spoilers.\n"
            "Play naturally as a real human player: explore your surroundings, inspect objects, talk to characters, "
            "and solve puzzles through observation and logical deduction."
        )
        objective = (
            "Your objective is to play through the adventure autonomously as a regular player without walkthrough assistance.\n"
            "Observe the scene carefully, talk to present NPCs (/say), inspect interesting objects (/inspect), "
            "search the area (/search), read discovered notes/books (/read), take useful visible items (/take), "
            "and try reasonable actions to make progress. Learn from the game master's responses."
        )
        return objective, walkthrough_text

    seq_walkthrough, _ = resolve_sequence_guidance(adventure, state)
    active_seq = _find_active_sequence(adventure, state)
    seq_title = ""
    if active_seq:
        seq_title = active_seq.get("title") or active_seq.get("name") or ""

    if seq_walkthrough:
        header = (
            f"CURRENT SEQUENCE WALKTHROUGH ({seq_title}):"
            if seq_title
            else "CURRENT SEQUENCE WALKTHROUGH:"
        )
        walkthrough_text = f"{header}\n{seq_walkthrough}"
    else:
        fallback = state.walkthrough or getattr(adventure, "walkthrough", "")
        walkthrough_text = (
            fallback if fallback else "No specific walkthrough available for this sequence."
        )

    objective = (
        "Your objective is to play through the adventure as efficiently and purposefully as possible, "
        "following the current sequence walkthrough step-by-step while remaining in character.\n"
        "Analyze the current room, visible items, NPCs, and dialogue. If the current situation matches "
        "a step in the walkthrough, take that action to advance the story."
    )
    return objective, walkthrough_text


class AgentService:
    @staticmethod
    def get_agent_state(state: SessionState) -> dict[str, Any]:
        """Helper to get transient agent state out of entity_states."""
        if not state.entity_states:
            state.entity_states = {}
        if "__agent__" not in state.entity_states:
            state.entity_states["__agent__"] = {
                "active": False,
                "failure_count": 0,
                "monkey_mode": False,
                "allow_walkthrough": True,
                "step_by_step": False,
            }
        agent_state = state.entity_states["__agent__"]
        modified = False
        for key, default in (
            ("monkey_mode", False),
            ("allow_walkthrough", True),
            ("step_by_step", False),
        ):
            if key not in agent_state:
                agent_state[key] = default
                modified = True
        if modified:
            state.entity_states["__agent__"] = agent_state
            flag_modified(state, "entity_states")
        return agent_state

    @staticmethod
    def set_agent_active(state: SessionState, active: bool) -> None:
        """Helper to toggle agent state active and reset failures."""
        agent_state = AgentService.get_agent_state(state)
        agent_state["active"] = active
        if active:
            agent_state["failure_count"] = 0
        state.entity_states["__agent__"] = agent_state
        flag_modified(state, "entity_states")

    @staticmethod
    def set_monkey_mode(state: SessionState, enabled: bool) -> None:
        """Enable/disable monkey mode for the autonomous play-agent in this session."""
        agent_state = AgentService.get_agent_state(state)
        agent_state["monkey_mode"] = enabled
        state.entity_states["__agent__"] = agent_state
        flag_modified(state, "entity_states")

    @staticmethod
    def set_walkthrough_allowed(state: SessionState, allowed: bool) -> None:
        """Enable/disable sequence walkthrough access for the play-agent."""
        agent_state = AgentService.get_agent_state(state)
        agent_state["allow_walkthrough"] = allowed
        state.entity_states["__agent__"] = agent_state
        flag_modified(state, "entity_states")

    @staticmethod
    def set_step_by_step(state: SessionState, enabled: bool) -> None:
        """Enable/disable step-by-step confirmation mode for the play-agent."""
        agent_state = AgentService.get_agent_state(state)
        agent_state["step_by_step"] = enabled
        state.entity_states["__agent__"] = agent_state
        flag_modified(state, "entity_states")

    @staticmethod
    def increment_failure(state: SessionState) -> int:
        """Increment transient failure count. If >= 3, deactivate agent."""
        agent_state = AgentService.get_agent_state(state)
        count = agent_state.get("failure_count", 0) + 1
        agent_state["failure_count"] = count
        if count >= 3:
            agent_state["active"] = False
        state.entity_states["__agent__"] = agent_state
        flag_modified(state, "entity_states")
        return count

    @staticmethod
    def reset_failures(state: SessionState) -> None:
        """Reset consecutive failures to 0."""
        agent_state = AgentService.get_agent_state(state)
        agent_state["failure_count"] = 0
        state.entity_states["__agent__"] = agent_state
        flag_modified(state, "entity_states")

    @staticmethod
    def log_issue(
        session_id: str,
        thoughts: str,
        action: str,
        issue_description: str,
        history_summary: str,
    ) -> None:
        """Append agent issues to the existing AGENTS.md inside the resolved session directory."""
        try:
            file_path = _resolve_session_issue_log_path(session_id)
        except ValueError:
            logger.warning(
                "Agent issue log skipped: invalid or missing session directory for session_id=%s",
                session_id,
            )
            return

        mode = "a" if os.path.exists(file_path) else "w"
        with open(file_path, mode, encoding="utf-8") as f:
            if mode == "w":
                f.write(f"# TaleWeaver Agent Issues Log - Session {session_id}\n\n")
                f.write(
                    "This file contains bugs, unsolvable puzzles, or errors encountered during autonomous gameplay.\n\n"
                )

            f.write("## Issue Detected\n")
            f.write(f"- **Thoughts:** {thoughts}\n")
            f.write(f"- **Attempted Action:** {action}\n")
            f.write(f"- **Issue Description:** {issue_description}\n")
            f.write(f"- **Recent History Summary:** {history_summary}\n")
            f.write("\n---\n\n")

    @staticmethod
    async def get_decision(
        db: AsyncSession,
        game_id: str,
        user: User,
        state: SessionState,
        avatar: Avatar,
        adventure: AdventureTemplate,
        manager: Any,
    ) -> AgentDecision:
        """Runs the simple LLM to determine the agent's next action using legitimate player context."""
        builder = TurnLlmContextBuilder(manager)
        ctx = await builder.build_context(user_msg="", language=None)

        scene_items_res = await db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == game_id,
                WorldEntity.entity_type == "OBJECT",
            )
        )
        scene_entities = list(scene_items_res.scalars().all())
        states = state.entity_states or {}

        visible_item_names = _collect_visible_scene_item_names(
            scene_entities, states, state.current_scene_id
        )
        visible_scene_items_text = ", ".join(visible_item_names) if visible_item_names else "None"

        agent_state = AgentService.get_agent_state(state)
        objective_block, walkthrough_text = _build_agent_objective_and_walkthrough(
            adventure, state, agent_state
        )
        player_world_context = build_player_perception_context(adventure, state, ctx)

        inventory_names = [
            i.get("name") if isinstance(i, dict) else str(i) for i in (avatar.inventory or [])
        ]
        system_prompt = AGENT_PLAYER_TURN_SYSTEM_PROMPT.format(
            name=avatar.name,
            role=avatar.role or "Adventurer",
            level=getattr(avatar, "level", 1),
            exp=avatar.exp or 0,
            hp=avatar.hp,
            max_hp=avatar.max_hp,
            stamina=avatar.stamina,
            max_stamina=avatar.max_stamina,
            mana=avatar.mana,
            max_mana=avatar.max_mana,
            inventory=", ".join(inventory_names) if inventory_names else "Empty",
            equipment=avatar.equipment or "None",
            mechanics_system_prompt=player_world_context,
            visible_scene_items_text=visible_scene_items_text,
            walkthrough_text=walkthrough_text,
            objective_block=objective_block,
        )

        user_prompt = (
            "Based on the recent chat history and your current location, what is the single next "
            "action or command you want to perform? If you are stuck or encountered an error/bug, report it."
        )

        llm_settings = user.llm_settings or {}
        provider = llm_settings.get("play_agent_model_provider") or ctx.small_model_provider
        model = llm_settings.get("play_agent_model") or ctx.small_model
        gm_llm = GameMasterLLM(user=user, provider=provider, model_category="small")

        try:
            return await gm_llm.aexecute_complex_task(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=AgentDecision,
                model=model,
                adventure_id=adventure.id,
                game_id=game_id,
                operation="agent_turn",
                phase="decision",
            )
        except Exception as e:
            logger.exception("Failed to run agent decision LLM call")
            return AgentDecision(
                thoughts="Failed to contact GM model or parse JSON output.",
                action="Wait a moment.",
                is_stuck_or_bug=True,
                issue_description=f"LLM call exception: {str(e)}",
            )
