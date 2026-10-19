"""Protagonist (template avatar) persistence and portrait."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select

from backend.core import prompts
from backend.core.config import settings
from backend.engine.manifest_apply.assets import needs_image
from backend.engine.manifest_apply.context import ApplyContext
from backend.engine.manifest_apply.visuals import (
    generate_image,
    pick_existing_image,
    placeholder_image,
    t2i_config,
    uses_advanced_model,
)

EQUIPMENT_SLOTS = (
    "Head", "Chest", "Arms", "Legs", "Hands", "Feet", "Ring_1", "Ring_2", "Neck", "MainHand", "OffHand",
)  # fmt: skip

# (avatar attribute, manifest key, default for new avatars)
AVATAR_FIELDS: tuple[tuple[str, str, Any], ...] = (
    ("name", "name", "Hero"),
    ("role", "role", "Protagonist"),
    ("description", "description", ""),
    ("goal", "goal", ""),
    ("character", "character", ""),
    ("hp", "hp", 200),
    ("max_hp", "hp", 200),
    ("stamina", "stamina", 200),
    ("max_stamina", "stamina", 200),
    ("mana", "mana", 200),
    ("max_mana", "mana", 200),
    ("strength", "strength", 10),
    ("dexterity", "dexterity", 10),
    ("intelligence", "intelligence", 10),
    ("wisdom", "wisdom", 10),
    ("charisma", "charisma", 10),
    ("armor_class", "armor_class", 10),
    ("exp", "exp", 0),
)


@dataclass
class StartingItems:
    """Protagonist items declared in the manifest."""

    equipped_ids: dict[str, str] = field(default_factory=dict)  # item_id -> slot
    inventory_ids: set[str] = field(default_factory=set)
    item_defs: dict[str, dict[str, Any]] = field(default_factory=dict)


def empty_equipment() -> dict[str, None]:
    return dict.fromkeys(EQUIPMENT_SLOTS)


def collect_starting_items(prot: dict[str, Any]) -> StartingItems:
    items = StartingItems()
    for slot, val in (prot.get("starting_equipment") or {}).items():
        item_id = val.get("id") if isinstance(val, dict) else val
        if not item_id:
            continue
        items.equipped_ids[item_id] = slot
        if isinstance(val, dict):
            items.item_defs[item_id] = val
    for item in prot.get("starting_inventory") or []:
        item_id = item.get("id") if isinstance(item, dict) else item
        if not item_id:
            continue
        items.inventory_ids.add(item_id)
        if isinstance(item, dict):
            items.item_defs[item_id] = item
    return items


def starting_stats(prot: dict[str, Any]) -> dict[str, Any]:
    stats = dict(prot.get("stats") or {})
    # Generated manifests carry special actions at top level, exported ones inside `stats`.
    specials = prot.get("special_actions") or stats.get("special_actions") or []
    stats["special_actions"] = specials
    stats["unlocked_actions"] = [
        act.get("id") for act in specials if isinstance(act, dict) and not act.get("is_locked")
    ]
    return stats


def _new_avatar(ctx: ApplyContext, prot: dict[str, Any], stats: dict[str, Any]) -> Any:
    from backend.models.avatar import Avatar

    values = {attr: prot.get(key, default) for attr, key, default in AVATAR_FIELDS}
    avatar = Avatar(
        template_id=ctx.template_id,
        user_id=ctx.adventure.owner_id if ctx.adventure else None,
        status_effects=prot.get("status_effects", []),
        stats=stats,
        inventory=[],
        equipment=empty_equipment(),
        **values,
    )
    ctx.db.add(avatar)
    return avatar


def _update_avatar(avatar: Any, prot: dict[str, Any], stats: dict[str, Any]) -> None:
    for attr, key, _default in AVATAR_FIELDS:
        setattr(avatar, attr, prot.get(key, getattr(avatar, attr)))
    avatar.status_effects = prot.get("status_effects") or avatar.status_effects
    avatar.stats = stats
    avatar.inventory = []
    avatar.equipment = empty_equipment()


async def _generate_portrait(ctx: ApplyContext, avatar: Any) -> Optional[str]:
    from backend.engine.media_engine import MediaEngine

    prompt = prompts.PROTAGONIST_IMAGE_PROMPT_TEMPLATE.format(
        name=avatar.name, role=avatar.role, description=avatar.description
    )
    plot = (ctx.manifest.get("plot") or "").strip()
    if plot:
        prompt = f"{prompt} Narrative context: {plot[:1200]}"
    user_config, api_keys = t2i_config(ctx)
    return await generate_image(
        ctx,
        status=f"Envisioning Portrait for {avatar.name}...",
        prompt=prompt,
        factory=lambda: MediaEngine.generate_entity_image(
            prompt,
            ctx.template_id,
            "PROTAGONIST",
            "NPC",
            user_config,
            api_keys,
            style_instruction=ctx.style_instruction,
            use_advanced_model=uses_advanced_model(ctx, "protagonist_model_quality", "advanced"),
        ),  # fmt: skip
        timeout=float(settings.VISUAL_TIMEOUT),
        failure_label=f"Protagonist image generation for {ctx.template_id}",
    )


async def _portrait(ctx: ApplyContext, avatar: Any, prot: dict[str, Any]) -> Optional[str]:
    image_url = await pick_existing_image(
        ctx,
        kind="protagonist",
        label=f"Protagonist ({avatar.name})",
        source_asset_id=prot.get("source_asset_id"),
        before=[ctx.existing_images.get("PROTAGONIST")],
        after=[prot.get("profile_image")],
    )
    if not needs_image(image_url):
        return image_url
    if ctx.user and ctx.gen_protagonist_image:
        image_url = await _generate_portrait(ctx, avatar)
    if not needs_image(image_url):
        return image_url
    current = avatar.profile_image
    if current and current.startswith("/data/"):
        return current
    return await placeholder_image(ctx, "PROTAGONIST", category="SCENE")


async def persist_avatar(ctx: ApplyContext, prot: dict[str, Any]) -> tuple[Any, StartingItems]:
    """Creates or updates the template avatar from the manifest and resolves its portrait."""
    from backend.models.avatar import Avatar

    res = await ctx.db.execute(
        select(Avatar)
        .where(Avatar.template_id == ctx.template_id)
        .order_by(Avatar.created_at.asc(), Avatar.id.asc())
        .limit(1)
    )
    avatar = res.scalars().first()
    items = collect_starting_items(prot)
    stats = starting_stats(prot)
    if avatar:
        _update_avatar(avatar, prot, stats)
    else:
        avatar = _new_avatar(ctx, prot, stats)
    avatar.profile_image = await _portrait(ctx, avatar, prot)
    return avatar, items
