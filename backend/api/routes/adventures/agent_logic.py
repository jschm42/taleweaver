import os
import logging
from typing import Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import select

from backend.core.config import settings
from backend.core.llm_router import GameMasterLLM
from backend.models.session_state import SessionState
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.models.chat import ChatMessage
from backend.api.routes.adventures.turn_llm_pipeline import TurnLlmContextBuilder

logger = logging.getLogger(__name__)

class AgentDecision(BaseModel):
    thoughts: str = Field(description="Internal reasoning and goals based on the character persona, current situation, history, and walkthrough. Keep it concise.")
    action: str = Field(description="The next action or slash command to execute (e.g. '/inspect shelf', 'go north', '/talk Merlin', 'I want to ask Merlin about the key'). Do not use markdown bolds or style formatting.")
    is_stuck_or_bug: bool = Field(description="Set to true if there is an error, a bug, or an unsolvable puzzle/situation that prevents proceeding.")
    issue_description: str = Field(description="Detailed description of the bug, error, or unsolvable puzzle if is_stuck_or_bug is true. Otherwise empty.")


class AgentService:
    @staticmethod
    def get_agent_state(state: SessionState) -> dict[str, Any]:
        """Helper to get transient agent state out of entity_states."""
        if not state.entity_states:
            state.entity_states = {}
        if "__agent__" not in state.entity_states:
            state.entity_states["__agent__"] = {"active": False, "failure_count": 0}
        return state.entity_states["__agent__"]

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
    def log_issue(game_id: str, thoughts: str, action: str, issue_description: str, history_summary: str) -> None:
        """Append agent issues or unsolvable puzzles/bugs to session AGENTS.md."""
        session_dir = os.path.join(settings.DATA_DIR, "adventures", "sessions", game_id)
        os.makedirs(session_dir, exist_ok=True)
        file_path = os.path.join(session_dir, "AGENTS.md")
        
        mode = "a" if os.path.exists(file_path) else "w"
        with open(file_path, mode, encoding="utf-8") as f:
            if mode == "w":
                f.write(f"# TaleWeaver Agent Issues Log - Session {game_id}\n\n")
                f.write("This file contains bugs, unsolvable puzzles, or errors encountered during autonomous gameplay.\n\n")
            
            f.write(f"## Issue Detected\n")
            f.write(f"- **Thoughts:** {thoughts}\n")
            f.write(f"- **Attempted Action:** {action}\n")
            f.write(f"- **Issue Description:** {issue_description}\n")
            f.write(f"- **Recent History Summary:** {history_summary}\n")
            f.write("\n---\n\n")

    @staticmethod
    async def get_decision(db: AsyncSession, game_id: str, user: User, state: SessionState, avatar: Avatar, adventure: AdventureTemplate, manager: Any) -> AgentDecision:
        """
        Runs the simple LLM to determine the agent's next action using the full gameplay context.
        """
        # Build LLM Turn context (exits, entities, current_scene, system prompts, models, etc.)
        builder = TurnLlmContextBuilder(manager)
        ctx = await builder.build_context(user_msg="", language=None)
        
        walkthrough_text = state.walkthrough or adventure.walkthrough or "No walkthrough available for this adventure."
        
        system_prompt = (
            "You are playing an interactive text adventure game as the protagonist, staying fully in character.\n"
            f"Character Name: {avatar.name}\n"
            f"Class/Role: {avatar.role or 'Adventurer'}\n"
            f"Level: {getattr(avatar, 'level', 1)} | XP: {avatar.exp or 0}\n"
            f"Current Stats: HP: {avatar.hp}/{avatar.max_hp}, Stamina: {avatar.stamina}/{avatar.max_stamina}, Mana: {avatar.mana}/{avatar.max_mana}\n"
            f"Inventory: {', '.join([i.get('name') if isinstance(i, dict) else str(i) for i in (avatar.inventory or [])]) or 'Empty'}\n"
            f"Equipment: {avatar.equipment or 'None'}\n\n"
            "--- COMMAND GUIDELINES (CRITICAL) ---\n"
            "You can execute actions in two ways: using official slash commands or writing natural language roleplay.\n\n"
            "1. OFFICIAL SLASH COMMANDS (Use EXACTLY this syntax):\n"
            "   - To speak/talk to an NPC: Use `/say <TEXT>` or `/speak <TEXT>` (e.g., `/say Hello, who are you?`). You must use this when addressing characters.\n"
            "   - To use or combine items: Use `/use <item>` or `/use <item_a> on <item_b>` or `/combine <item_a> with <item_b>` (e.g., `/use key on chest`, `/combine battery with flashlight`). Wear/use consumables or combine key pieces to solve puzzles!\n"
            "   - To take/pick up an item: Use `/take <item>` (e.g., `/take ancient key`).\n"
            "   - To equip gear/weapons/armor: Use `/equip <item>` (e.g., `/equip iron sword`).\n"
            "   - To remove gear: Use `/unequip <slot>` (e.g., `/unequip MainHand`).\n"
            "   - To inspect a person, item, or place: Use `/inspect <name>` (e.g., `/inspect desk`).\n"
            "   - To drop an item: Use `/drop <item>`.\n\n"
            "2. NATURAL LANGUAGE ACTIONS:\n"
            "   - For any other environmental interaction (e.g., plugging in an oven, flipping a switch, opening a standard door, moving/exiting, looking around): Write your action in natural, descriptive language (e.g., 'I plug in the oven', 'go north', 'look around', 'open the door').\n"
            "   - NEVER invent or use custom slash commands starting with `/` that are not listed above (e.g., do NOT write `/plug`, `/go`, `/flip`, `/open`). Unrecognized commands will fail.\n\n"
            "--- GAME WORLD CONTEXT ---\n"
            f"{ctx.mechanics_system_prompt}\n\n"
            "--- OFFICIAL ADVENTURE WALKTHROUGH/SOLUTION ---\n"
            f"{walkthrough_text}\n\n"
            "--- AGENT OBJECTIVES ---\n"
            "Your objective is to play through the adventure as efficiently and quickly as possible, adhering to the walkthrough step-by-step while remaining in character.\n"
            "Analyze the current room, NPCs, items, exits, and quests. If the current state matches a step in the walkthrough, take that action.\n"
            "Respond ONLY with a JSON object matching the schema exactly. Do not wrap in markdown or include extra text."
        )

        user_prompt = "Based on the recent chat history and your current location, what is the single next action or command you want to perform? If you are stuck or encountered an error/bug, report it."

        # Initialize the GameMasterLLM using the user's preferred simple/small model config
        gm_llm = GameMasterLLM(
            user=user,
            provider=ctx.small_model_provider,
            model_category="small",
        )

        try:
            decision = await gm_llm.aexecute_complex_task(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=AgentDecision,
                model=ctx.small_model,
                adventure_id=adventure.id,
                game_id=game_id,
                operation="agent_turn",
                phase="decision",
            )
            return decision
        except Exception as e:
            logger.exception("Failed to run agent decision LLM call")
            # Return a fallback decision indicating an error
            return AgentDecision(
                thoughts="Failed to contact GM model or parse JSON output.",
                action="Wait a moment.",
                is_stuck_or_bug=True,
                issue_description=f"LLM call exception: {str(e)}"
            )
