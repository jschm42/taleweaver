"""Adventure-level manifest data: quests, awards, sequences, narrative, timing and cover."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Optional

from sqlalchemy import select

from backend.core.ui_theme import normalize_ui_theme
from backend.engine.manifest_apply.assets import is_usable_image_url, resolve_source_asset_image
from backend.engine.manifest_apply.context import ApplyContext, generator_module
from backend.engine.manifest_apply.visuals import publish_status, t2i_config
from backend.engine.media.image_prompt_context import clean_appearance
from backend.engine.rules.sequence_walkthrough import apply_legacy_walkthrough
from backend.models.adventure_template import AdventureTemplate

logger = logging.getLogger(__name__)

_HARD_RULE_FIELDS = ("required_item_id", "required_scene_id", "required_defeated_npc_id")
_EMPTY_TOKENS = {"NONE", "NULL", "UNDEFINED", "N/A", "FALSE"}

# Narrative fields keep the stored value when the manifest has none.
_NARRATIVE_FIELDS = (
    "teaser",
    "cover_appearance",
    "plot",
    "rules",
    "intro_text",
    "completed_condition",
    "gameover_condition",
    "completed_guard_expression",
    "gameover_guard_expression",
    "tts_director_notes",
    "creator",
    "copyright",
    "license",
    "license_url",
)

# (manifest key, converter, apply only when truthy instead of when not None)
_RUNTIME_SETTINGS: tuple[tuple[str, Optional[Callable[[Any], Any]], bool], ...] = (
    ("time_per_turn", int, False),
    ("pacing_minutes", int, False),
    ("max_time_per_turn", int, False),
    ("max_memory_turns", int, False),
    ("clock_enabled", bool, False),
    ("time_system", None, True),
    ("time_config", None, True),
    ("starting_timestamp", None, False),
    ("allow_dynamic_items", None, False),
    ("can_damage_npcs", None, False),
    ("npcs_can_damage_protagonist", None, False),
    ("game_over_rules", None, False),
)

_SESSION_SYNC_FIELDS = (
    "plot",
    "rules",
    "completed_condition",
    "gameover_condition",
    "completed_guard_expression",
    "gameover_guard_expression",
    "tts_director_notes",
    "time_system",
    "time_config",
)

# Applied after NPCs are persisted: (attribute, default; None = keep current value).
_FINAL_FIELDS: tuple[tuple[str, Any], ...] = (
    ("teaser", ""),
    ("rules", ""),
    ("language", ""),
    ("creator", None),
    ("copyright", None),
    ("license", None),
    ("license_url", None),
    ("is_adventure_generator", False),
    ("can_damage_npcs", True),
    ("npcs_can_damage_protagonist", True),
)


def adventure_field(manifest: dict[str, Any], key: str, default: Any = None) -> Any:
    """Reads ``adventure.<key>`` (standard ADV layout) with a top-level fallback."""
    block = manifest.get("adventure") if isinstance(manifest.get("adventure"), dict) else {}
    if block.get(key) is not None:
        return block[key]
    if manifest.get(key) is not None:
        return manifest[key]
    return default


def _clean_sequence(seq: Any) -> Any:
    if not isinstance(seq, dict):
        return seq
    cleaned = dict(seq)
    for hard_field in _HARD_RULE_FIELDS:
        value = str(cleaned.get(hard_field) or "").replace("##", "").strip()
        cleaned[hard_field] = "" if value.upper() in _EMPTY_TOKENS else value.upper()
    return cleaned


def _apply_quests_awards_sequences(
    ctx: ApplyContext, adventure: AdventureTemplate
) -> tuple[list, list]:
    chat_mode = adventure.rule_enforcement_mode == "chat"
    quests = [] if chat_mode else (ctx.manifest.get("quests") or [])
    awards = [] if chat_mode else (ctx.manifest.get("awards") or [])
    for quest in quests:
        quest.setdefault("status", "open")
    for award in awards:
        award.setdefault("is_earned", False)
    adventure.quests = quests  # type: ignore[assignment]
    adventure.awards = awards  # type: ignore[assignment]
    if ctx.manifest.get("sequences"):
        adventure.sequences = [_clean_sequence(s) for s in ctx.manifest["sequences"]]  # type: ignore[assignment]
    return quests, awards


def _apply_narrative(ctx: ApplyContext, adventure: AdventureTemplate) -> None:
    for key in _NARRATIVE_FIELDS:
        setattr(adventure, key, adventure_field(ctx.manifest, key) or getattr(adventure, key))
    adventure.cover_appearance = clean_appearance(adventure.cover_appearance)  # type: ignore[assignment]

    # Legacy manifests with a walkthrough but no sequences get a single main sequence.
    apply_legacy_walkthrough(adventure, adventure_field(ctx.manifest, "walkthrough"))


def _apply_runtime_settings(ctx: ApplyContext, adventure: AdventureTemplate) -> None:
    for key, convert, truthy_only in _RUNTIME_SETTINGS:
        value = ctx.manifest.get(key)
        if (truthy_only and not value) or value is None:
            continue
        setattr(adventure, key, convert(value) if convert else value)

    ui_theme = adventure_field(ctx.manifest, "ui_theme")
    if ui_theme is not None:
        adventure.ui_theme = normalize_ui_theme(ui_theme)  # type: ignore[assignment]

    start_time = ctx.manifest.get("start_time")
    if not start_time:
        return
    try:
        hours, minutes = map(int, str(start_time).split(":"))
    except ValueError:
        logger.warning("Ignoring invalid start_time %r for %s", start_time, ctx.template_id)
        return
    adventure.starting_timestamp = hours * 60 + minutes  # type: ignore[assignment]


async def _sync_sessions(ctx: ApplyContext, adventure: AdventureTemplate, quests: list) -> None:
    from backend.models.session_state import SessionState

    res = await ctx.db.execute(
        select(SessionState).where(SessionState.template_id == ctx.template_id)
    )
    sequences = sorted(getattr(adventure, "sequences", None) or [], key=lambda s: s.get("order", 1))
    for state in res.scalars().all():
        if not state.quests:
            state.quests = quests
        if not state.active_sequence_id and sequences:
            state.active_sequence_id = sequences[0].get("id")
            state.active_sequence_order = sequences[0].get("order", 1)
        for key in _SESSION_SYNC_FIELDS:
            setattr(state, key, getattr(adventure, key))


async def _create_cover(
    ctx: ApplyContext, adventure: AdventureTemplate
) -> tuple[Optional[str], bool]:
    """Returns (cover_url, reused) for a reused source cover or a freshly generated one."""
    from backend.engine.media.media_engine import MediaEngine

    requested = ctx.manifest.get("cover_source_asset_id")
    reused = (
        resolve_source_asset_image(ctx.source_assets, ctx.template_id, "cover", requested)
        if requested == "COVER"
        else None
    )
    if reused:
        await generator_module()._log_reused_asset(ctx.db, adventure, "Adventure Cover", reused)
        return reused, True
    ctx.image_counters["attempts"] += 1
    user_config, api_keys = t2i_config(ctx)
    cover_url = await MediaEngine.generate_adventure_cover(
        title=adventure.title,
        original_prompt=adventure.teaser or adventure.original_prompt,
        adventure_id=ctx.template_id,
        user_config=user_config,
        api_keys=api_keys,
        style_instruction=ctx.style_instruction,
        appearance=adventure.cover_appearance,
    )
    return cover_url, False


async def _ensure_cover(ctx: ApplyContext) -> None:
    adventure = ctx.adventure
    if not adventure or not ctx.user or not ctx.any_image_generation:
        return
    if is_usable_image_url(adventure.image_url):
        return
    wg = generator_module()
    await publish_status(ctx, "Painting Adventure Cover...")
    try:
        cover_url, reused = await _create_cover(ctx, adventure)
        if not cover_url:
            return
        ctx.image_counters["successes"] += 1
        adventure.image_url = cover_url  # type: ignore[assignment]
        if not reused:
            prompt = adventure.teaser or adventure.original_prompt
            await wg._log_image_generation(ctx.db, adventure, prompt, cover_url)
        await ctx.commit_and_refresh(refresh_user=False)
    except Exception as exc:
        if wg.is_image_moderation_error(exc):
            ctx.image_counters["moderation"] += 1
        logger.warning("Failed to generate adventure cover for %s: %s", ctx.template_id, exc)


async def apply_adventure_meta(ctx: ApplyContext) -> None:
    """Syncs adventure-level fields to the template and to running sessions, then the cover."""
    adventure = ctx.adventure
    if not adventure:
        return
    quests, _awards = _apply_quests_awards_sequences(ctx, adventure)
    _apply_narrative(ctx, adventure)
    _apply_runtime_settings(ctx, adventure)
    await _sync_sessions(ctx, adventure, quests)
    await ctx.commit_and_refresh()
    await _ensure_cover(ctx)
    await ctx.db.flush()


def apply_final_adventure_fields(ctx: ApplyContext) -> None:
    """Writes the remaining adventure fields and stores the manifest as the template source."""
    adventure = ctx.adventure
    if not adventure:
        return
    for key, default in _FINAL_FIELDS:
        fallback = getattr(adventure, key) if default is None else default
        setattr(adventure, key, adventure_field(ctx.manifest, key, fallback))
    adventure.original_prompt = adventure_field(  # type: ignore[assignment]
        ctx.manifest, "original_prompt", adventure.original_prompt or ""
    )
    adventure.scripts_generation_enabled = adventure_field(  # type: ignore[assignment]
        ctx.manifest,
        "scripts_generation_enabled",
        getattr(adventure, "scripts_generation_enabled", False),
    )
    adventure.is_ready = False  # type: ignore[assignment]
    adventure.original_manifest = ctx.manifest  # type: ignore[assignment]
