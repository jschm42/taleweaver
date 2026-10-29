"""Scene and exit persistence."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.engine.manifest_apply.assets import needs_image
from backend.engine.manifest_apply.context import ApplyContext, generator_module
from backend.engine.manifest_apply.visuals import (
    generate_image,
    pick_existing_image,
    placeholder_image,
    t2i_config,
)
from backend.engine.media.image_prompt_context import build_scene_image_prompt
from backend.models.world_entity import WorldExit, WorldScene

MAX_DECORATIVE_OBJECTS = 7
MAX_DECORATIVE_LENGTH = 100
_SCENE_SCRIPT_FIELDS = (
    "on_enter_scene_script",
    "on_enter_scene_text",
    "on_leave_scene_script",
    "on_leave_scene_text",
)
_EXIT_SCRIPT_FIELDS = (
    "unlock_expression",
    "on_open_exit_script",
    "on_open_exit_text",
    "on_exit_used_script",
    "on_exit_used_text",
    "on_unlock_success_script",
    "on_unlock_success_text",
    "on_unlock_failure_script",
    "on_unlock_failure_text",
)


def clean_decorative_objects(decorative: Any) -> list[str]:
    if not isinstance(decorative, list):
        return []
    cleaned = [
        d.strip()[:MAX_DECORATIVE_LENGTH] for d in decorative if isinstance(d, str) and d.strip()
    ]
    return cleaned[:MAX_DECORATIVE_OBJECTS]


def _scene_prompt(scene: dict[str, Any]) -> str:
    return build_scene_image_prompt(
        scene["name"],
        scene["description"],
        decorative_objects=clean_decorative_objects(scene.get("decorative_objects")),
    )


async def _scene_image(
    ctx: ApplyContext, scene: dict[str, Any], position: tuple[int, int]
) -> Optional[str]:
    from backend.engine.media.media_engine import MediaEngine

    image_url = await pick_existing_image(
        ctx,
        kind="scene",
        label=f"Scene: {scene.get('name')}",
        source_asset_id=scene.get("source_asset_id"),
        before=[ctx.existing_images.get(scene["id"])],
        after=[scene.get("image_url")],
    )
    if not needs_image(image_url):
        return image_url
    if ctx.user and ctx.gen_scenes:
        prompt = _scene_prompt(scene)
        user_config, api_keys = t2i_config(ctx)
        idx, total = position
        image_url = await generate_image(
            ctx,
            status=f"Envisioning Scene {idx}/{total}: {scene['name']}...",
            prompt=prompt,
            factory=lambda: MediaEngine.generate_scene_image(
                prompt,
                ctx.template_id,
                user_config,
                api_keys,
                style_instruction=ctx.style_instruction,
            ),
            timeout=generator_module()._image_generation_timeout_seconds(),
            failure_label=f"Scene image generation for {ctx.template_id}/{scene['id']}",
        )
    if not needs_image(image_url):
        return image_url
    return await placeholder_image(ctx, scene["id"], category="SCENE", subdir="scenes")


async def persist_scenes(ctx: ApplyContext, scenes: list[dict[str, Any]]) -> None:
    total = len(scenes)
    for idx, scene in enumerate(scenes, start=1):
        if scene["id"] in ctx.seen_scene_ids:
            continue
        ctx.seen_scene_ids.add(scene["id"])
        image_url = await _scene_image(ctx, scene, (idx, total))
        ctx.db.add(
            WorldScene(
                id=scene["id"],
                template_id=ctx.template_id,
                label=scene.get("name") or scene.get("label") or "Unknown Scene",
                description=scene.get("description") or "",
                image_url=image_url,
                decorative_objects=clean_decorative_objects(scene.get("decorative_objects"))
                or None,
                **{key: scene.get(key) or None for key in _SCENE_SCRIPT_FIELDS},
            )
        )


def _is_bidirectional(exit_def: dict[str, Any]) -> bool:
    exit_type = str(exit_def.get("exit_type") or "").strip().lower()
    if exit_type in ("bidirectional", "one_way"):
        return exit_type == "bidirectional"
    return bool(exit_def.get("is_bidirectional", True))


def persist_exits(db: AsyncSession, template_id: str, exits: list[dict[str, Any]]) -> None:
    """Adds exits, skipping duplicates (a bidirectional pair counts once in either direction)."""
    normalize_unlock = generator_module()._normalize_unlock_requirements
    seen: set[tuple[str, ...]] = set()
    for exit_def in exits:
        from_id = exit_def["from_scene_id"]
        to_id = exit_def["to_scene_id"]
        bidirectional = _is_bidirectional(exit_def)
        key = ("pair", *sorted((from_id, to_id))) if bidirectional else ("directed", from_id, to_id)
        if key in seen:
            continue
        seen.add(key)
        code_to_unlock, item_to_unlock, rule_to_unlock = normalize_unlock(
            exit_def.get("code_to_unlock"),
            exit_def.get("item_to_unlock"),
            exit_def.get("rule_to_unlock"),
        )
        db.add(
            WorldExit(
                template_id=template_id,
                from_scene_id=from_id,
                to_scene_id=to_id,
                label=exit_def["label"],
                exit_type="bidirectional" if bidirectional else "one_way",
                is_locked=bool(exit_def.get("is_locked", False)),
                lock_description=exit_def.get("lock_description"),
                code_to_unlock=code_to_unlock,
                item_to_unlock=item_to_unlock,
                rule_to_unlock=rule_to_unlock,
                **{field: exit_def.get(field) or None for field in _EXIT_SCRIPT_FIELDS},
            )
        )
