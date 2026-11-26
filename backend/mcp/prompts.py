"""MCP workflow prompts capturing TaleWeaver blueprint, editing, music, and debug practices."""

from __future__ import annotations

import json
from typing import Any

from backend.mcp.context import McpRequestContext
from backend.mcp.registry import PromptArgument, PromptSpec, mcp_registry
from backend.services.inspection_service import (
    get_adventure_details,
    get_session_state,
    resolve_adventure_template,
)


def _message(text: str) -> dict[str, Any]:
    return {"role": "user", "content": {"type": "text", "text": text}}


async def _prompt_create_blueprint(_ctx: McpRequestContext, args: dict[str, str]) -> dict[str, Any]:
    premise = args.get("premise", "").strip() or "(describe the desired adventure premise)"
    language = args.get("language", "English").strip() or "English"
    text = (
        f"Create a TaleWeaver Story Idea blueprint in {language} for: {premise}\n\n"
        "Requirements:\n"
        "1. Read taleweaver://docs/world-builder-syntax, taleweaver://docs/blueprint-manual, and "
        "taleweaver://docs/scripting-engine first.\n"
        "2. Enforce all puzzles deterministically with locks, switches, containers, readable clues "
        "(<= 500 chars), guards, or sandboxed tw.* scripts (no counting puzzles, no plain-text codes).\n"
        "3. Include a planted twist with >= 2 earlier clues and at least one mechanical consequence.\n"
        "4. Validate the finished blueprint before saving or generating."
    )
    return {
        "description": "Guided TaleWeaver Story Idea blueprint authoring checklist.",
        "messages": [_message(text)],
    }


async def _prompt_edit_safely(_ctx: McpRequestContext, args: dict[str, str]) -> dict[str, Any]:
    adventure = args.get("adventure", "").strip() or "<adventure>"
    text = (
        f"Safely edit TaleWeaver adventure '{adventure}':\n"
        "1. Call get_adventure_summary and get_adventure_details (or scene slice) to inspect existing IDs and init_script.\n"
        "2. Call list_change_set_operations to verify exact operation field names.\n"
        "3. Run apply_adventure_changes with commit=false first, review newly introduced validation findings, "
        "fix any errors, and only commit once the dry run is clean."
    )
    return {
        "description": "Safe inspect -> dry-run -> commit workflow for TaleWeaver adventures.",
        "messages": [_message(text)],
    }


async def _prompt_craft_music(ctx: McpRequestContext, args: dict[str, str]) -> dict[str, Any]:
    adventure_ident = args.get("adventure", "").strip()
    targets = args.get("targets", "main track, chapters, cutscenes, scenes").strip()
    provider = args.get("provider", "both (Suno and Stable Audio)").strip()

    context_block = (
        "(no adventure loaded; specify an adventure argument to preload scenes & chapters)"
    )
    if adventure_ident:
        tpl = await resolve_adventure_template(
            ctx.db, adventure_ident, owner_id=ctx.scoped_owner_id
        )
        details = await get_adventure_details(ctx.db, tpl.id, compact=True)
        adv = details.get("adventure", {})
        snapshot = {
            "title": adv.get("title"),
            "teaser": adv.get("teaser"),
            "selected_tone": adv.get("selected_tone"),
            "title_track_id": adv.get("title_track_id"),
            "audio_tracks": adv.get("audio_tracks", []),
            "sequences": [
                {"id": q.get("id"), "order": q.get("order"), "title": q.get("title")}
                for q in (adv.get("sequences") or [])
                if isinstance(q, dict)
            ],
            "cutscenes": [
                {
                    "id": c.get("id"),
                    "title": c.get("title"),
                    "audio_track_id": c.get("audio_track_id"),
                }
                for c in (adv.get("cutscenes") or [])
                if isinstance(c, dict)
            ],
            "scenes": [
                {
                    "id": s.get("id"),
                    "label": s.get("label"),
                    "section_id": s.get("section_id"),
                    "audio_track_id": s.get("audio_track_id"),
                }
                for s in details.get("scenes", [])
            ],
        }
        context_block = json.dumps(snapshot, indent=2, ensure_ascii=False, default=str)

    text = (
        f"Generate English music AI prompts ({provider}) for targets [{targets}] of adventure "
        f"'{adventure_ident or 'unknown'}'.\n"
        "Rules: instrumental by default, no real artist/composer/game names, include BPM/key/instruments/acoustics, "
        "Suno tags <= 200 chars with 'seamless loop, loopable', Stable Audio <= 400 chars ending with "
        "'Seamless loop: no intro, no fade-out ending.' for loops.\n\n"
        f"Adventure audio context:\n{context_block}"
    )
    return {
        "description": "Craft Suno and Stable Audio music prompts from adventure metadata.",
        "messages": [_message(text)],
    }


async def _prompt_diagnose_session(ctx: McpRequestContext, args: dict[str, str]) -> dict[str, Any]:
    session_id = args.get("session_id", "").strip()
    snapshot_text = "(provide a session_id argument to preload runtime state)"
    if session_id:
        state = await get_session_state(
            ctx.db, session_id, owner_id=ctx.scoped_owner_id, include_entities=False
        )
        snapshot_text = json.dumps(state, indent=2, ensure_ascii=False, default=str)
    text = (
        f"Diagnose TaleWeaver game session '{session_id or '<session_id>'}':\n"
        "Inspect get_session_state (including hidden_only=true if items/NPCs are missing), "
        "get_session_chat for recent GM narration/system announcements, and check_session_integrity "
        "for avatar equipment/item issues.\n\n"
        f"Session snapshot:\n{snapshot_text}"
    )
    return {
        "description": "Structured session troubleshooting prompt.",
        "messages": [_message(text)],
    }


def register_prompts() -> None:
    """Register MCP workflow prompts."""
    mcp_registry.register_prompt(
        PromptSpec(
            name="create_adventure_blueprint",
            description="Design a TaleWeaver Story Idea blueprint with deterministic puzzles and a planted twist.",
            feature="read_adventures",
            arguments=[
                PromptArgument(
                    "premise", "Core premise, setting, or protagonist idea.", required=True
                ),
                PromptArgument("language", "Target language for adventure prose.", required=False),
            ],
            builder=_prompt_create_blueprint,
        )
    )
    mcp_registry.register_prompt(
        PromptSpec(
            name="edit_adventure_safely",
            description="Step-by-step inspect -> dry-run -> validate -> commit workflow for editing an adventure.",
            feature="read_adventures",
            arguments=[
                PromptArgument(
                    "adventure", "Template ID, origin_id, or title substring.", required=True
                ),
            ],
            builder=_prompt_edit_safely,
        )
    )
    mcp_registry.register_prompt(
        PromptSpec(
            name="craft_music_prompts",
            description="Generate Suno and Stable Audio soundtrack prompts preloaded with an adventure's structure.",
            feature="read_adventures",
            arguments=[
                PromptArgument(
                    "adventure", "Template ID, origin_id, or title substring.", required=True
                ),
                PromptArgument(
                    "targets",
                    "Comma-separated targets (main track, chapters, cutscenes, scenes).",
                    required=False,
                ),
                PromptArgument("provider", "suno, stable_audio, or both.", required=False),
            ],
            builder=_prompt_craft_music,
        )
    )
    mcp_registry.register_prompt(
        PromptSpec(
            name="diagnose_session",
            description="Diagnose inventory, lock, reveal, or GM narration issues in a game session.",
            feature="read_sessions",
            arguments=[
                PromptArgument("session_id", "Game session ID or unique prefix.", required=True),
            ],
            builder=_prompt_diagnose_session,
        )
    )
