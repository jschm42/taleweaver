import logging
import os
import re
import json
import shutil
from copy import deepcopy
from typing import Any, Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.schemas import (
    AdventureTemplateDebugResponse,
    BiographyGenerationRequest,
    BiographyGenerationResponse,
    DecorativeItemsGenerationRequest,
    DecorativeItemsGenerationResponse,
    TraitGenerationRequest,
    TraitGenerationResponse,
    QuestDescriptionGenerationRequest,
    QuestDescriptionGenerationResponse,
    QuestGenerationRequest,
    QuestGenerationResponse,
    SceneDescriptionGenerationRequest,
    SceneDescriptionGenerationResponse,
)
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.llm_router import GameMasterLLM
from backend.core.validators_prompts import (
    AI_FIX_SUGGESTIONS_SYSTEM_PROMPT,
    AI_FIX_SUGGESTIONS_USER_PROMPT_TEMPLATE,
    AI_VALIDATION_SYSTEM_PROMPT,
    AI_VALIDATION_USER_PROMPT_TEMPLATE,
)
from backend.core.world_validator import validate_adventure
from backend.schemas.validation import (
    AIFixApplyRequest,
    AIFixApplyResponse,
    AIFixSuggestionsRequest,
    AIFixSuggestionsResponse,
    DeleteValidationFindingsRequest,
    FixProposal,
    FixProposalEntityPatch,
    ValidationFinding,
    ValidationRunRequest,
    ValidationRunResponse,
)
from backend.core.prompts import (
    BIOGRAPHY_GENERATION_SYSTEM_PROMPT,
    BIOGRAPHY_GENERATION_USER_PROMPT_TEMPLATE,
    DECORATIVE_ITEMS_GENERATION_SYSTEM_PROMPT,
    DECORATIVE_ITEMS_GENERATION_USER_PROMPT_TEMPLATE,
    QUEST_DESCRIPTION_GENERATION_SYSTEM_PROMPT,
    QUEST_DESCRIPTION_GENERATION_USER_PROMPT_TEMPLATE,
    QUEST_GENERATION_SYSTEM_PROMPT,
    QUEST_GENERATION_USER_PROMPT_TEMPLATE,
    SCENE_DESCRIPTION_GENERATION_SYSTEM_PROMPT,
    SCENE_DESCRIPTION_GENERATION_USER_PROMPT_TEMPLATE,
    TRAIT_GENERATION_SYSTEM_PROMPT,
    TRAIT_GENERATION_USER_PROMPT_TEMPLATE,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.ai_fix_cache import AIFixCache
from backend.models.avatar import Avatar
from backend.models.validation_run import ValidationRun
from backend.api.routes.adventures.sessions import _backfill_avatar_items_from_template_entities
from backend.api.routes.adventures.logic import AdventureLogic
from backend.engine.media_engine import MediaEngine
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.utils.path_security import (
    assert_within_data_dir,
    data_url_to_local_path,
    local_path_to_data_url,
)

router = APIRouter(tags=["Editor"])
logger = logging.getLogger(__name__)

_SAFE_SCENE_ID_RE = re.compile(r"^[A-Z0-9_]+$")

class EntityUpdateRequest(BaseModel):
    target_type: Literal["cover", "scene", "npc", "object", "protagonist", "exit"]
    target_id: str
    new_id: Optional[str] = None
    name: Optional[str] = None
    teaser: Optional[str] = None
    description: Optional[str] = None
    hp: Optional[int] = None
    mana: Optional[int] = None
    stamina: Optional[int] = None
    goal: Optional[str] = None
    character: Optional[str] = None
    is_killable: Optional[bool] = None
    item_type: Optional[str] = None
    is_portable: Optional[bool] = None
    locked: Optional[bool] = None
    code_to_unlock: Optional[str] = None
    item_to_unlock: Optional[str] = None
    rule_to_unlock: Optional[str] = None
    inventory: Optional[list] = None
    text_log_content: Optional[str] = None
    text_log_format: Optional[str] = None
    exit_type: Optional[str] = None
    wearable_slots: Optional[list[str]] = None
    combination_ingredients: Optional[list[str]] = None
    reveal_rule: Optional[str] = None
    is_hidden: Optional[bool] = None
    spatial_position: Optional[str] = None
    reveals_item_id: Optional[str] = None
    switch_states: Optional[list[str]] = None
    switch_initial_state: Optional[str] = None
    switch_transitions: Optional[list[dict[str, Any]]] = None
    effects: Optional[dict[str, Any]] = None
    stat_modifier_strength: Optional[int] = None
    current_scene_id: Optional[str] = None
    strength: Optional[int] = None
    intelligence: Optional[int] = None
    wisdom: Optional[int] = None
    dexterity: Optional[int] = None
    charisma: Optional[int] = None
    armor_class: Optional[int] = None
    exp: Optional[int] = None
    equipment: Optional[dict[str, Any]] = None
    decorative_objects: Optional[list[str]] = None
    is_hidden: Optional[bool] = None
    reveal_rule: Optional[str] = None


class StartSceneUpdateRequest(BaseModel):
    scene_id: str


class SceneCreateRequest(BaseModel):
    scene_id: str
    label: str
    description: str
    image_url: Optional[str] = None
    decorative_objects: Optional[list[str]] = None


class ExitCreateRequest(BaseModel):
    from_scene_id: str
    to_scene_id: str
    label: str
    exit_type: Literal["one_way", "bidirectional"] = "one_way"
    is_locked: bool = False
    lock_description: Optional[str] = None
    code_to_unlock: Optional[str] = None
    item_to_unlock: Optional[str] = None
    rule_to_unlock: Optional[str] = None


class EntityCreateRequest(BaseModel):
    entity_id: str
    entity_type: Literal["NPC", "OBJECT"]
    scene_id: str
    name: str
    description: str
    image_url: Optional[str] = None
    item_type: Optional[str] = None
    is_portable: Optional[bool] = None
    goal: Optional[str] = None
    character: Optional[str] = None
    hp: Optional[int] = None
    stamina: Optional[int] = None
    mana: Optional[int] = None
    is_killable: Optional[bool] = None
    metadata_json: Optional[dict[str, Any]] = None
    wearable_slots: Optional[list[str]] = None
    combination_ingredients: Optional[list[str]] = None
    stat_modifier_strength: Optional[int] = None
    inventory: Optional[list] = None
    is_hidden: Optional[bool] = None
    reveal_rule: Optional[str] = None


class QuestCreateRequest(BaseModel):
    id: str
    title: str
    description: str = ""
    goal: str = ""
    impact: str = ""
    exp_reward: int = 0
    is_main: bool = False


class AwardCreateRequest(BaseModel):
    key: str
    title: str
    description: str = ""
    tier: Literal["bronze", "silver", "gold"] = "bronze"
    requirement: str = ""
    is_earned: bool = False


EDITOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

def _serialize_model(obj):
    if not obj: return None
    data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

    if isinstance(obj, WorldScene):
        decor = data.get("decorative_objects")
        if not isinstance(decor, list):
            decor = []
        data["decorative_objects"] = [str(d) for d in decor if isinstance(d, (str, int, float))]
    
    # Group stats for easier frontend access
    if isinstance(obj, WorldEntity):
        if obj.entity_type == "NPC":
            data["stats"] = {
                "hp": obj.hp,
                "mana": obj.mana,
                "stamina": obj.stamina
            }
        elif obj.entity_type == "OBJECT":
            stats = {}
            if obj.stat_modifier_strength: stats["STR"] = obj.stat_modifier_strength
            if obj.stat_modifier_dexterity: stats["DEX"] = obj.stat_modifier_dexterity
            if obj.stat_modifier_intelligence: stats["INT"] = obj.stat_modifier_intelligence
            if obj.stat_modifier_wisdom: stats["WIS"] = obj.stat_modifier_wisdom
            if obj.stat_modifier_charisma: stats["CHA"] = obj.stat_modifier_charisma
            if obj.stat_modifier_armor_class: stats["AC"] = obj.stat_modifier_armor_class
            data["stats"] = stats
            metadata_json = dict(obj.metadata_json or {})
            data["code_to_unlock"] = str(metadata_json.get("code_to_unlock") or "")
            data["item_to_unlock"] = str(metadata_json.get("item_to_unlock") or "")
            data["rule_to_unlock"] = str(metadata_json.get("rule_to_unlock") or "")
            if isinstance(metadata_json.get("locked"), bool):
                data["locked"] = metadata_json.get("locked")
            else:
                data["locked"] = bool(metadata_json.get("code_to_unlock") or metadata_json.get("item_to_unlock") or metadata_json.get("rule_to_unlock"))
            
            # Serialize switch fields for the editor UI
            switch_config = metadata_json.get("switch") or {}
            data["switch_states"] = metadata_json.get("switch_states") or switch_config.get("states") or []
            data["switch_initial_state"] = metadata_json.get("switch_initial_state") or switch_config.get("initial_state") or ""
            data["switch_transitions"] = metadata_json.get("switch_transitions") or switch_config.get("transitions") or []
    return data

def _is_npc_entity(ent):
    return ent.entity_type == "NPC"

def _is_object_entity(ent):
    return ent.entity_type == "OBJECT"


OBJECT_ID_PATTERN = re.compile(r"^[A-Z0-9_]{1,30}$")

def _sanitize_object_id(raw_value: Optional[str], field_name: str) -> str:
    value = str(raw_value or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    if not OBJECT_ID_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must contain only uppercase letters, digits, and underscores, and be at most 30 characters",
        )
    return value


def _sanitize_editor_id(raw_value: Optional[str], field_name: str) -> str:
    value = str(raw_value or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    if not EDITOR_ID_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must match ^[A-Za-z0-9_-]{{1,128}}$",
        )
    return value


async def _get_owned_adventure_or_404(db: AsyncSession, template_id: str, user_id: str) -> AdventureTemplate:
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != user_id:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")
    return adv


async def _ensure_template_scene_exists(db: AsyncSession, template_id: str, scene_id: str) -> None:
    res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
            WorldScene.id == scene_id,
        )
    )
    if not res.scalars().first():
        raise HTTPException(status_code=400, detail=f"scene_id '{scene_id}' does not exist in this adventure")


async def _clone_entity_image(
    *,
    source_image_url: Optional[str],
    template_id: str,
    new_entity_id: str,
) -> Optional[str]:
    """Copy the source entity image into a new file under the same adventure's entities dir.

    Returns the new ``/data/...`` URL on success, or ``None`` when the source has no
    image, the image is not on disk, or the copy fails. The original image is preserved.
    """
    if not source_image_url:
        return None

    source_path = data_url_to_local_path(source_image_url)
    if not source_path or not os.path.isfile(source_path):
        return None

    target_dir = os.path.dirname(source_path)
    if not target_dir or not os.path.isdir(target_dir):
        return None

    # Restrict the extension to a hard-coded allowlist to satisfy the
    # path-traversal linter: a user-controlled image URL could otherwise inject
    # an arbitrary suffix into the constructed file name.
    _, raw_ext = os.path.splitext(source_path)
    safe_ext = raw_ext.lower() if raw_ext.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"} else ".png"

    safe_entity_id = re.sub(r"[^A-Za-z0-9_-]", "_", new_entity_id).strip("_") or "entity"
    data_root = os.path.realpath(settings.DATA_DIR)
    suffix = ""
    counter = 1
    while True:
        candidate_name = f"{safe_entity_id}_clone{suffix}{safe_ext}"
        candidate_path = os.path.realpath(os.path.join(target_dir, candidate_name))
        try:
            if os.path.commonpath([candidate_path, data_root]) != data_root:
                return None
        except ValueError:
            return None
        # Re-validate at the sink so static analysers (CodeQL) see the value
        # as verified-safe before we touch the filesystem.
        candidate_path = assert_within_data_dir(candidate_path)
        if not os.path.exists(candidate_path):
            break
        counter += 1
        suffix = f"_{counter}"

    try:
        shutil.copy2(source_path, candidate_path)
    except OSError as exc:
        logger.warning("Failed to clone image for entity %s: %s", new_entity_id, exc)
        return None

    return local_path_to_data_url(candidate_path)


def _normalize_lock_fields(
    *,
    code_to_unlock: Optional[str],
    item_to_unlock: Optional[str],
    rule_to_unlock: Optional[str],
) -> tuple[str, str, str]:
    code = str(code_to_unlock or "").strip()
    item = str(item_to_unlock or "").strip().upper()
    rule = str(rule_to_unlock or "").strip()

    if code:
        return code[:32], "", ""
    if item:
        from backend.utils.text_utils import slugify
        return "", slugify(item).upper().replace("-", "_")[:64], ""
    if rule:
        return "", "", rule[:500]
    return "", "", ""


def _public_data_to_local_path(path: str) -> Optional[str]:
    return data_url_to_local_path(path)


def _local_to_public_data_path(path: str) -> str:
    return local_path_to_data_url(path)


def _resolve_library_image_url(image_url: Optional[str]) -> Optional[str]:
    raw = str(image_url or "").strip()
    if not raw:
        return image_url

    local_path = _public_data_to_local_path(raw)
    if not local_path:
        return image_url

    if os.path.exists(local_path):
        return raw

    # Intentionally do not remap missing assets by basename across adventures.
    # Cross-adventure fallback causes confusing visuals when source adventures are deleted.
    return image_url


async def _get_template_avatar(db: AsyncSession, template_id: str) -> Optional[Avatar]:
    avatar_res = await db.execute(
        select(Avatar)
        .where(Avatar.template_id == template_id)
        .order_by(Avatar.created_at.asc(), Avatar.id.asc())
        .limit(1)
    )
    return avatar_res.scalars().first()


async def _restore_missing_template_avatar(
    db: AsyncSession,
    template_id: str,
    adventure: AdventureTemplate,
) -> Optional[Avatar]:
    manifest = adventure.original_manifest if isinstance(adventure.original_manifest, dict) else {}
    prot = manifest.get("protagonist") if isinstance(manifest, dict) else None
    if not isinstance(prot, dict):
        return None

    image_url = str(prot.get("profile_image") or "").strip() or None
    if image_url:
        image_url = AdventureLogic.resolve_existing_data_asset_url(image_url) or image_url

    avatar = Avatar(
        user_id=adventure.owner_id,
        template_id=template_id,
        name=str(prot.get("name") or "Hero"),
        role=(str(prot.get("role") or "").strip() or "Protagonist"),
        description=(str(prot.get("description") or "").strip() or None),
        goal=(str(prot.get("goal") or "").strip() or None),
        character=(str(prot.get("character") or "").strip() or None),
        profile_image=image_url,
        hp=int(prot.get("hp") or 200),
        max_hp=int(prot.get("hp") or 200),
        stamina=int(prot.get("stamina") or 200),
        max_stamina=int(prot.get("stamina") or 200),
        mana=int(prot.get("mana") or 200),
        max_mana=int(prot.get("mana") or 200),
        strength=int(prot.get("strength") or 10),
        dexterity=int(prot.get("dexterity") or 10),
        intelligence=int(prot.get("intelligence") or 10),
        wisdom=int(prot.get("wisdom") or 10),
        charisma=int(prot.get("charisma") or 10),
        armor_class=int(prot.get("armor_class") or 10),
        exp=int(prot.get("exp") or 0),
        stats=dict(prot.get("stats") or {}),
        inventory=list(prot.get("starting_inventory") or prot.get("inventory") or []),
        equipment=dict(
            prot.get("starting_equipment")
            or {
                "Head": None,
                "Chest": None,
                "Arms": None,
                "Legs": None,
                "Hands": None,
                "Feet": None,
                "Ring_1": None,
                "Ring_2": None,
                "Neck": None,
                "MainHand": None,
                "OffHand": None,
            }
        ),
        status_effects=list(prot.get("status_effects") or []),
    )
    db.add(avatar)
    await db.commit()
    return avatar

async def _build_adventure_editor_assets(template_id: str, db: AsyncSession) -> AdventureTemplateDebugResponse:
    """Builds full world/editor asset state for a specific adventure."""
    adv_res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == template_id))
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")

    try:
        await MediaEngine.ensure_thumbnails(template_id)
    except Exception as exc:
        logger.warning("Thumbnail ensure failed for adventure %s: %s", template_id, exc)
        
    scene_res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
        )
    )
    scenes = scene_res.scalars().all()
    
    exit_res = await db.execute(
        select(WorldExit).where(
            WorldExit.template_id == template_id,
            WorldExit.session_id.is_(None),
        )
    )
    exits = exit_res.scalars().all()
    
    entity_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
        )
    )
    entities = entity_res.scalars().all()

    # Heal stale library image URLs (e.g. slug changed after import/reuse) without failing the editor UI.
    for scene in scenes:
        scene.image_url = _resolve_library_image_url(getattr(scene, "image_url", None))
    for ent in entities:
        ent.image_url = _resolve_library_image_url(getattr(ent, "image_url", None))

    avatar = await _get_template_avatar(db, template_id)
    if not avatar:
        avatar = await _restore_missing_template_avatar(db, template_id, adventure)

    # Backfill avatar inventory/equipment dicts from template entities so debug view shows full item data.
    if avatar:
        entities_by_id = {ent.id: ent for ent in entities if getattr(ent, 'id', None)}
        if entities_by_id:
            _backfill_avatar_items_from_template_entities(avatar, entities_by_id)

    db_scenes = [_serialize_model(s) for s in scenes]
    db_npcs = [_serialize_model(ent) for ent in entities if _is_npc_entity(ent)]
    db_objects = [_serialize_model(ent) for ent in entities if _is_object_entity(ent)]
    db_exits = [_serialize_model(ex) for ex in exits]

    adventure_payload = _serialize_model(adventure) or {}
    adventure_payload["start_scene_id"] = await AdventureLogic.resolve_initial_scene_id(db, template_id)

    return AdventureTemplateDebugResponse(
        adventure=adventure_payload,
        protagonist=_serialize_model(avatar) if avatar else None,
        scenes=db_scenes,
        npcs=db_npcs,
        objects=db_objects,
        exits=db_exits,
        entities_all=[_serialize_model(ent) for ent in entities]
    )

@router.get("/{template_id}/editor/assets", response_model=AdventureTemplateDebugResponse)
async def get_adventure_editor_assets(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns full world/editor asset data for the AdventureTemplate Editor UI (owner only)."""
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    return await _build_adventure_editor_assets(template_id, db)

@router.get("/{template_id}/debug", response_model=AdventureTemplateDebugResponse)
async def get_adventure_debug(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Legacy debug endpoint (owner only)."""
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    return await _build_adventure_editor_assets(template_id, db)


def _summarize_for_ai(payload: dict, *, max_field_len: int = 1500) -> dict:
    """Trim large text fields on the editor payload before sending it to an LLM.

    Keeps the manifest shape but prevents a single oversized ``description``
    or ``walkthrough`` from blowing out the context window. Also converts
    ``datetime`` / ``date`` values to ISO-8601 strings so the result is
    JSON-serialisable (SQLAlchemy TimestampMixin fields otherwise break
    ``json.dumps``).
    """
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()

    def _coerce(value):
        # SQLAlchemy TimestampMixin exposes created_at / updated_at as
        # ``datetime`` instances that ``json.dumps`` cannot encode.
        import datetime as _dt

        if isinstance(value, _dt.datetime):
            return value.isoformat()
        if isinstance(value, _dt.date):
            return value.isoformat()
        if isinstance(value, _dt.time):
            return value.isoformat()
        if isinstance(value, _dt.timedelta):
            return value.total_seconds()
        if isinstance(value, str) and len(value) > max_field_len:
            return value[:max_field_len] + "..."
        return value

    def _walk(value):
        if isinstance(value, dict):
            return {k: _walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_walk(v) for v in value]
        if isinstance(value, tuple):
            return [_walk(v) for v in value]
        return _coerce(value)

    return _walk(payload)


@router.post(
    "/{template_id}/editor/validate",
    response_model=ValidationRunResponse,
)
async def run_editor_validation(
    template_id: str,
    payload: ValidationRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run structural validation, and optionally an AI logic-validation pass.

    On save, the editor calls this with ``include_ai=False`` for fast,
    deterministic feedback. The "Run full validation" button in the
    Validation tab uses ``include_ai=True`` and is the only path that
    triggers the LLM call.
    """
    import json
    from datetime import datetime, timezone

    await _get_owned_adventure_or_404(db, template_id, current_user.id)

    debug_payload = await _build_adventure_editor_assets(template_id, db)

    structural = validate_adventure(debug_payload)

    ai_findings: list[ValidationFinding] = []
    ai_skipped_reason: Optional[str] = None

    if not payload.include_ai:
        ai_skipped_reason = "ai_not_requested"
    else:
        scene_count = len(debug_payload.scenes or [])
        if scene_count > settings.MAX_AI_VALIDATION_SCENES:
            ai_skipped_reason = "scene_limit_exceeded"
            logger.info(
                "Skipping AI validation for %s: %d scenes exceeds limit of %d",
                template_id,
                scene_count,
                settings.MAX_AI_VALIDATION_SCENES,
            )
        else:
            try:
                llm_settings = current_user.llm_settings or {}
                provider = (
                    llm_settings.get("complex_model_provider")
                    or llm_settings.get("small_model_provider")
                    or "openai"
                )
                model = llm_settings.get("complex_model") or "gpt-4o"
                gm = GameMasterLLM(
                    user=current_user,
                    provider=provider,
                    model_category="complex",
                )

                summary = _summarize_for_ai(debug_payload)
                adventure = summary.get("adventure") or {}
                user_prompt = AI_VALIDATION_USER_PROMPT_TEMPLATE.format(
                    title=adventure.get("title", ""),
                    language=adventure.get("language", ""),
                    rule_enforcement_mode=adventure.get("rule_enforcement_mode", "rpg"),
                    teaser=adventure.get("teaser", "") or "",
                    plot=adventure.get("plot", "") or "",
                    rules=adventure.get("rules", "") or "",
                    intro_text=adventure.get("intro_text", "") or "",
                    walkthrough=adventure.get("walkthrough", "") or "",
                    scene_count=len(summary.get("scenes") or []),
                    scenes_json=json.dumps(summary.get("scenes") or [], ensure_ascii=False),
                    exit_count=len(summary.get("exits") or []),
                    exits_json=json.dumps(summary.get("exits") or [], ensure_ascii=False),
                    npc_count=len(summary.get("npcs") or []),
                    npcs_json=json.dumps(summary.get("npcs") or [], ensure_ascii=False),
                    object_count=len(summary.get("objects") or []),
                    objects_json=json.dumps(summary.get("objects") or [], ensure_ascii=False),
                    quest_count=len(adventure.get("quests") or []),
                    quests_json=json.dumps(adventure.get("quests") or [], ensure_ascii=False),
                )

                from backend.api.routes.adventures.schemas import (
                    AIValidationResponse as _AIValidationResponse,
                )

                response = await gm.aexecute_complex_task(
                    system_prompt=AI_VALIDATION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    response_model=_AIValidationResponse,
                    model=model,
                )
                for f in (response.findings if response else []):
                    ai_findings.append(
                        ValidationFinding(
                            severity="warn",  # AI may only emit warn-level findings
                            code=f.code,
                            message=f.message,
                            location=f.location,
                            context=f.context,
                        )
                    )
            except Exception as exc:
                logger.exception("AI validation failed for %s: %s", template_id, exc)
                ai_skipped_reason = "ai_error"

    run_at_dt = datetime.now(timezone.utc)
    structural_dicts = [f.model_dump() for f in structural]
    ai_dicts = [f.model_dump() for f in ai_findings]

    persisted = ValidationRun(
        template_id=template_id,
        user_id=current_user.id,
        include_ai=bool(payload.include_ai),
        structural_findings=structural_dicts,
        ai_findings=ai_dicts,
        ai_skipped_reason=ai_skipped_reason,
        structural_finding_count=len(structural_dicts),
        ai_finding_count=len(ai_dicts),
        error_count=sum(1 for f in structural_dicts + ai_dicts if f.get("severity") == "error"),
        warning_count=sum(1 for f in structural_dicts + ai_dicts if f.get("severity") == "warn"),
        run_at=run_at_dt,
    )
    db.add(persisted)
    try:
        await db.commit()
    except Exception as exc:
        logger.exception("Failed to persist validation run for %s: %s", template_id, exc)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to persist validation run.") from exc

    return ValidationRunResponse(
        structural_findings=structural,
        ai_findings=ai_findings,
        ai_skipped_reason=ai_skipped_reason,
        run_at=run_at_dt.isoformat(),
    )


@router.get(
    "/{template_id}/editor/validation/latest",
    response_model=None,
)
async def get_latest_validation_run(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the latest persisted ValidationRun for the (template, user) pair.

    Returns ``null`` when no validation has been run yet for this user on
    this adventure. The editor uses this to rehydrate the findings state on
    tab open without forcing the user to re-run validation.
    """

    await _get_owned_adventure_or_404(db, template_id, current_user.id)

    res = await db.execute(
        select(ValidationRun)
        .where(
            ValidationRun.template_id == template_id,
            ValidationRun.user_id == current_user.id,
        )
        .order_by(ValidationRun.run_at.desc(), ValidationRun.created_at.desc())
        .limit(1)
    )
    run = res.scalars().first()
    if run is None:
        return None

    return {
        "structural_findings": list(run.structural_findings or []),
        "ai_findings": list(run.ai_findings or []),
        "ai_skipped_reason": run.ai_skipped_reason,
        "run_at": run.run_at.isoformat() if run.run_at else None,
        "structural_finding_count": run.structural_finding_count,
        "ai_finding_count": run.ai_finding_count,
        "error_count": run.error_count,
        "warning_count": run.warning_count,
    }


def _recount_validation_findings(run: ValidationRun) -> None:
    """Recompute the *_count columns on the ValidationRun from its JSON arrays.

    Called after any in-place mutation (deletion of entries) so the response and
    badge counts stay accurate.
    """
    structural = list(run.structural_findings or [])
    ai_list = list(run.ai_findings or [])
    combined = structural + ai_list
    run.structural_finding_count = len(structural)
    run.ai_finding_count = len(ai_list)
    run.error_count = sum(1 for e in combined if str(e.get("severity", "")).lower() == "error")
    run.warning_count = sum(1 for e in combined if str(e.get("severity", "")).lower() == "warn")


@router.post(
    "/{template_id}/editor/validation/latest/findings/delete",
)
async def delete_validation_findings(
    template_id: str,
    payload: DeleteValidationFindingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently remove findings from the latest persisted ValidationRun.

    Unlike dismissals (which are UI-only state), this mutation persists so the
    next rehydrate via ``GET /validation/latest`` no longer returns the entries.
    The endpoint only touches the latest run for the (template, user) pair —
    previous runs remain intact for audit.
    """
    await _get_owned_adventure_or_404(db, template_id, current_user.id)

    res = await db.execute(
        select(ValidationRun)
        .where(
            ValidationRun.template_id == template_id,
            ValidationRun.user_id == current_user.id,
        )
        .order_by(ValidationRun.run_at.desc(), ValidationRun.created_at.desc())
        .limit(1)
    )
    run = res.scalars().first()

    if run is None:
        # No persisted state to mutate. Mirror the no-op shape so the client
        # can keep the in-memory state authoritative.
        return {
            "status": "success",
            "deleted": 0,
            "structural_remaining": 0,
            "ai_remaining": 0,
            "validation_run": None,
        }

    before_structural = list(run.structural_findings or [])
    before_ai = list(run.ai_findings or [])

    if payload.delete_all:
        run.structural_findings = []
        run.ai_findings = []
        flag_modified(run, "structural_findings")
        flag_modified(run, "ai_findings")
        deleted = len(before_structural) + len(before_ai)
    else:
        targets_structural: set[tuple[str, str]] = set()
        targets_ai: set[tuple[str, str]] = set()
        for ref in payload.findings:
            key = (str(ref.code or "").strip(), str(ref.location or "").strip())
            if not key[0]:
                continue
            if ref.source == "ai":
                targets_ai.add(key)
            else:
                targets_structural.add(key)

        def _matches(entry: Any, targets: set[tuple[str, str]]) -> bool:
            return (str(entry.get("code") or "").strip(), str(entry.get("location") or "").strip()) in targets

        new_structural = [e for e in before_structural if not _matches(e, targets_structural)]
        new_ai = [e for e in before_ai if not _matches(e, targets_ai)]
        deleted = (len(before_structural) - len(new_structural)) + (len(before_ai) - len(new_ai))
        run.structural_findings = new_structural
        run.ai_findings = new_ai
        flag_modified(run, "structural_findings")
        flag_modified(run, "ai_findings")

    _recount_validation_findings(run)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to persist validation deletion.") from exc

    await db.refresh(run)

    return {
        "status": "success",
        "deleted": deleted,
        "structural_remaining": run.structural_finding_count,
        "ai_remaining": run.ai_finding_count,
        "validation_run": {
            "structural_findings": list(run.structural_findings or []),
            "ai_findings": list(run.ai_findings or []),
            "ai_skipped_reason": run.ai_skipped_reason,
            "run_at": run.run_at.isoformat() if run.run_at else None,
            "structural_finding_count": run.structural_finding_count,
            "ai_finding_count": run.ai_finding_count,
            "error_count": run.error_count,
            "warning_count": run.warning_count,
        },
    }


# ---------------------------------------------------------------------------
# AI fix suggestions / apply
# ---------------------------------------------------------------------------


def _finding_signature(finding: ValidationFinding) -> str:
    """Stable signature used to round-trip a finding through the suggestion / apply pipeline."""
    location = (finding.location or "").strip()
    context = finding.context or {}
    payload = json.dumps(context, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"{finding.severity}|{finding.code}|{location}|{payload}"


def _short_state(value: Any, *, limit: int = 400) -> str:
    text = "" if value is None else str(value)
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _scene_summary(scene: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": scene.get("id"),
        "label": scene.get("label"),
        "description": _short_state(scene.get("description")),
        "decorative_objects": scene.get("decorative_objects") or [],
    }


def _exit_summary(exit_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": exit_row.get("id"),
        "from_scene_id": exit_row.get("from_scene_id"),
        "to_scene_id": exit_row.get("to_scene_id"),
        "label": exit_row.get("label"),
        "exit_type": exit_row.get("exit_type"),
        "is_locked": exit_row.get("is_locked"),
        "lock_description": _short_state(exit_row.get("lock_description"), limit=200),
        "code_to_unlock": exit_row.get("code_to_unlock"),
        "item_to_unlock": exit_row.get("item_to_unlock"),
        "rule_to_unlock": _short_state(exit_row.get("rule_to_unlock"), limit=200),
    }


def _npc_summary(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entity.get("id"),
        "name": entity.get("name"),
        "description": _short_state(entity.get("description")),
        "current_scene_id": entity.get("current_scene_id"),
        "goal": _short_state(entity.get("goal")),
        "character": _short_state(entity.get("character")),
        "is_killable": entity.get("is_killable"),
        "stats": entity.get("stats") or {},
    }


def _object_summary(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entity.get("id"),
        "name": entity.get("name"),
        "description": _short_state(entity.get("description")),
        "current_scene_id": entity.get("current_scene_id"),
        "item_type": entity.get("item_type"),
        "is_portable": entity.get("is_portable"),
        "locked": entity.get("locked"),
        "code_to_unlock": entity.get("code_to_unlock"),
        "item_to_unlock": entity.get("item_to_unlock"),
        "rule_to_unlock": _short_state(entity.get("rule_to_unlock"), limit=200),
        "text_log_content": _short_state(entity.get("text_log_content"), limit=400),
        "text_log_format": entity.get("text_log_format"),
        "stats": entity.get("stats") or {},
    }


def _summarize_world_for_fix(payload: Any) -> dict[str, Any]:
    """Build a trimmed JSON-friendly snapshot of the world for the fix prompts."""

    def _adventure_dict() -> dict[str, Any]:
        adventure_raw = getattr(payload, "adventure", None) or {}
        if isinstance(adventure_raw, dict):
            return adventure_raw
        return {}

    adventure = _adventure_dict()
    adventure_payload: dict[str, Any] = {}
    for key in (
        "id", "title", "teaser", "plot", "rules", "intro_text",
        "walkthrough", "tts_director_notes", "completed_condition",
        "gameover_condition", "language", "selected_tone",
        "rule_enforcement_mode",
    ):
        value = adventure.get(key)
        if isinstance(value, str):
            adventure_payload[key] = _short_state(value, limit=1500)
        else:
            adventure_payload[key] = value

    scenes = [s for s in (getattr(payload, "scenes", None) or []) if isinstance(s, dict)]
    exits = [e for e in (getattr(payload, "exits", None) or []) if isinstance(e, dict)]
    npcs = [n for n in (getattr(payload, "npcs", None) or []) if isinstance(n, dict)]
    objects = [o for o in (getattr(payload, "objects", None) or []) if isinstance(o, dict)]

    raw_quests = adventure.get("quests") or []
    if not isinstance(raw_quests, list):
        raw_quests = []
    quests = []
    for q in raw_quests:
        if not isinstance(q, dict):
            continue
        quests.append({
            "id": q.get("id"),
            "title": q.get("title"),
            "description": _short_state(q.get("description"), limit=400),
        })

    return {
        "adventure": adventure_payload,
        "scenes": [_scene_summary(s) for s in scenes],
        "exits": [_exit_summary(e) for e in exits],
        "npcs": [_npc_summary(n) for n in npcs],
        "objects": [_object_summary(o) for o in objects],
        "quests": quests,
    }


def _signing(finding_or_payload: AIFixSuggestionsRequest) -> str:
    context_blob = json.dumps(
        finding_or_payload.finding_context or {},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        f"{finding_or_payload.finding_severity}|{finding_or_payload.finding_code}"
        f"|{(finding_or_payload.finding_location or '').strip()}|{context_blob}"
    )


_FIX_PROTAGONIST_FIELDS = frozenset(
    {
        "name", "description", "goal", "character",
        "hp", "mana", "stamina", "strength", "intelligence", "wisdom",
        "dexterity", "charisma", "armor_class", "exp",
    }
)

_FIX_ADVENTURE_FIELDS = frozenset(
    {
        "title", "teaser", "plot", "rules", "intro_text",
        "walkthrough", "tts_director_notes",
        "completed_condition", "gameover_condition",
    }
)

_FIX_SCENE_FIELDS = frozenset(
    {"label", "description", "decorative_objects"}
)

_FIX_EXIT_FIELDS = frozenset(
    {
        "label", "lock_description", "exit_type", "locked",
        "code_to_unlock", "item_to_unlock", "rule_to_unlock",
    }
)

_FIX_NPC_FIELDS = frozenset(
    {
        "name", "description", "goal", "character",
        "is_killable", "current_scene_id",
    }
)

_FIX_OBJECT_FIELDS = frozenset(
    {
        "name", "description", "is_portable", "current_scene_id",
        "locked", "code_to_unlock", "item_to_unlock", "rule_to_unlock",
        "text_log_content", "text_log_format",
    }
)


def _allowed_fields_for(target_type: str) -> frozenset[str]:
    return {
        "scene": _FIX_SCENE_FIELDS,
        "exit": _FIX_EXIT_FIELDS,
        "npc": _FIX_NPC_FIELDS,
        "object": _FIX_OBJECT_FIELDS,
        "protagonist": _FIX_PROTAGONIST_FIELDS,
        "adventure": _FIX_ADVENTURE_FIELDS,
    }.get(target_type, frozenset())


def _normalize_field_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_field_value(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_normalize_field_value(v) for v in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if value is None:
        return None
    return str(value)


async def _resolve_exit_target(
    *,
    db: AsyncSession,
    template_id: str,
    raw_target_id: str,
) -> Optional[WorldExit]:
    """Resolve an exit target_id in multiple ways.

    The AI sometimes emits ``target_id`` as:
      * the exit's primary key UUID (e.g. ``019EFF1D-8885-...``)
      * the ``from_scene_id -> to_scene_id`` composite (``"A->B"``)
      * one of the two scene IDs alone
      * the exit's human-readable ``label`` (case-insensitive, unique)

    We try the most specific match first, then relax. This keeps the
    apply-fix resilient against stale cached proposals whose original
    UUID no longer exists, and against AI proposals that picked a more
    human-readable identifier.
    """
    raw = str(raw_target_id or "").strip()
    if not raw:
        return None

    base_filter = (
        WorldExit.template_id == template_id,
    )

    res = await db.execute(
        select(WorldExit)
        .where(*base_filter, WorldExit.id == raw)
        .limit(1)
    )
    match = res.scalars().first()
    if match is not None:
        return match

    if "->" in raw:
        left, right = raw.split("->", 1)
        from_id = left.strip().upper()
        to_id = right.strip().upper()
        res = await db.execute(
            select(WorldExit)
            .where(
                *base_filter,
                WorldExit.from_scene_id == from_id,
                WorldExit.to_scene_id == to_id,
            )
            .limit(1)
        )
        match = res.scalars().first()
        if match is not None:
            return match

    upper = raw.upper()
    res = await db.execute(
        select(WorldExit)
        .where(*base_filter, WorldExit.id == upper)
        .limit(1)
    )
    match = res.scalars().first()
    if match is not None:
        return match

    res = await db.execute(
        select(WorldExit)
        .where(
            *base_filter,
            WorldExit.from_scene_id == upper,
        )
        .limit(1)
    )
    match = res.scalars().first()
    if match is not None:
        return match

    res = await db.execute(
        select(WorldExit)
        .where(
            *base_filter,
            WorldExit.to_scene_id == upper,
        )
        .limit(1)
    )
    match = res.scalars().first()
    if match is not None:
        return match

    label_ci = raw.strip().lower()
    res = await db.execute(
        select(WorldExit)
        .where(*base_filter)
    )
    candidates = []
    for row in res.scalars().all():
        if (row.label or "").strip().lower() == label_ci:
            candidates.append(row)
    if len(candidates) == 1:
        return candidates[0]

    return None


async def _resolve_entity_target(
    *,
    db: AsyncSession,
    template_id: str,
    entity_type: str,
    raw_target_id: str,
) -> Optional[WorldEntity]:
    """Resolve a scene/object/npc target_id; matches by exact ID, label, or unique label."""
    raw = str(raw_target_id or "").strip()
    if not raw:
        return None

    upper = raw.upper()
    res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.id == upper,
        )
    )
    match = res.scalars().first()
    if match is not None and match.entity_type == entity_type.upper():
        return match

    if match is not None and match.entity_type != entity_type.upper():
        return None

    label_ci = raw.strip().lower()
    res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.entity_type == entity_type.upper(),
        )
    )
    candidates = []
    for row in res.scalars().all():
        if (row.name or "").strip().lower() == label_ci:
            candidates.append(row)
    if len(candidates) == 1:
        return candidates[0]

    return None


async def _resolve_scene_target(
    *,
    db: AsyncSession,
    template_id: str,
    raw_target_id: str,
) -> Optional[WorldScene]:
    """Resolve a scene target_id; matches by exact ID or unique label."""
    raw = str(raw_target_id or "").strip()
    if not raw:
        return None

    upper = raw.upper()
    res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
            WorldScene.id == upper,
        )
    )
    match = res.scalars().first()
    if match is not None:
        return match

    label_ci = raw.strip().lower()
    res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
        )
    )
    candidates = []
    for row in res.scalars().all():
        if (row.label or "").strip().lower() == label_ci:
            candidates.append(row)
    if len(candidates) == 1:
        return candidates[0]
    return None


async def _apply_proposal_patch(
    *,
    db: AsyncSession,
    template_id: str,
    adv: AdventureTemplate,
    patch: FixProposalEntityPatch,
) -> Optional[str]:
    """Apply a single FixProposalEntityPatch. Returns a 'type:id' tag on success."""

    allowed = _allowed_fields_for(patch.target_type)
    if not allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported target_type '{patch.target_type}'")

    updates: dict[str, Any] = {}
    for field, value in (patch.field_updates or {}).items():
        if field not in allowed:
            continue
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        updates[field] = value

    if not updates:
        return None

    target_tag = f"{patch.target_type}:{patch.target_id or ''}"

    if patch.target_type == "adventure":
        for field, value in updates.items():
            setattr(adv, field, _normalize_field_value(value))
        return target_tag

    if patch.target_type == "protagonist":
        avatar = await _get_template_avatar(db, template_id)
        if not avatar:
            avatar = await _restore_missing_template_avatar(db, template_id, adv)
        if not avatar:
            raise HTTPException(status_code=400, detail="Protagonist not found for AI fix")
        for field, value in updates.items():
            if field == "hp":
                avatar.hp = int(value)
                avatar.max_hp = int(value)
            elif field == "mana":
                avatar.mana = int(value)
                avatar.max_mana = int(value)
            elif field == "stamina":
                avatar.stamina = int(value)
                avatar.max_stamina = int(value)
            else:
                setattr(avatar, field, _normalize_field_value(value))
        return target_tag

    raw_target_id = str(patch.target_id or "").strip()
    if not raw_target_id:
        raise HTTPException(
            status_code=400,
            detail=f"{patch.target_type} patch is missing target_id",
        )

    if patch.target_type == "scene":
        scene = await _resolve_scene_target(
            db=db, template_id=template_id, raw_target_id=raw_target_id,
        )
        if scene is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"scene '{raw_target_id}' could not be resolved in this "
                    f"adventure. The AI reference is stale; please retry."
                ),
            )
        target_tag = f"scene:{scene.id}"
        if "label" in updates:
            scene.label = str(updates["label"]).strip()[:120]
        if "description" in updates:
            scene.description = str(updates["description"]).strip()
        if "decorative_objects" in updates:
            decor: list[str] = []
            for d in updates["decorative_objects"] or []:
                s = str(d).strip()
                if not s:
                    continue
                if len(s) > 100:
                    raise HTTPException(status_code=400, detail="decorative_objects entries must be <= 100 chars")
                decor.append(s)
            scene.decorative_objects = decor[:7] or None
            flag_modified(scene, "decorative_objects")
        return target_tag

    if patch.target_type == "exit":
        world_exit = await _resolve_exit_target(
            db=db, template_id=template_id, raw_target_id=raw_target_id,
        )
        if world_exit is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"exit '{raw_target_id}' could not be resolved in this "
                    f"adventure. The AI reference is stale; please retry."
                ),
            )
        target_tag = f"exit:{world_exit.id}"
        if "label" in updates:
            world_exit.label = str(updates["label"]).strip()[:120]
        if "lock_description" in updates:
            world_exit.lock_description = str(updates["lock_description"]).strip() or None
        if "exit_type" in updates:
            world_exit.exit_type = str(updates["exit_type"]).strip().lower()
        if "locked" in updates:
            world_exit.is_locked = bool(updates["locked"])

        lock_keys_present = any(
            k in updates for k in ("code_to_unlock", "item_to_unlock", "rule_to_unlock")
        )
        if lock_keys_present:
            code = str(updates.get("code_to_unlock", world_exit.code_to_unlock or "")).strip()
            item = str(updates.get("item_to_unlock", world_exit.item_to_unlock or "")).strip().upper()
            rule = str(updates.get("rule_to_unlock", world_exit.rule_to_unlock or "")).strip()

            if code:
                code = code[:32]; item = ""; rule = ""
            elif item:
                from backend.utils.text_utils import slugify
                item = slugify(item).upper().replace("-", "_")[:64]; code = ""; rule = ""
            elif rule:
                rule = rule[:500]; code = ""; item = ""
            else:
                code = ""; item = ""; rule = ""

            world_exit.code_to_unlock = code or None
            world_exit.item_to_unlock = item or None
            world_exit.rule_to_unlock = rule or None
            if "locked" not in updates:
                world_exit.is_locked = bool(code or item or rule)
        return target_tag

    if patch.target_type in ("npc", "object"):
        ent = await _resolve_entity_target(
            db=db, template_id=template_id,
            entity_type=patch.target_type, raw_target_id=raw_target_id,
        )
        if ent is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{patch.target_type} '{raw_target_id}' could not be "
                    f"resolved in this adventure. The AI reference is stale; "
                    f"please retry."
                ),
            )
        target_tag = f"{patch.target_type}:{ent.id}"

        if "name" in updates:
            ent.name = str(updates["name"]).strip()[:120]
        if "description" in updates:
            text = str(updates["description"]).strip()
            if ent.entity_type == "OBJECT":
                item_type = str(ent.item_type or "").upper()
                if item_type == "READABLE" and len(text) > 200:
                    raise HTTPException(status_code=400, detail="READABLE descriptions must be <= 200 chars")
            ent.description = text
        if "is_portable" in updates and ent.entity_type == "OBJECT":
            ent.is_portable = bool(updates["is_portable"])
        if "current_scene_id" in updates:
            new_scene = str(updates["current_scene_id"] or "").strip().upper()
            if not new_scene:
                raise HTTPException(status_code=400, detail="current_scene_id cannot be empty")
            await _ensure_template_scene_exists(db, template_id, new_scene)
            ent.current_scene_id = new_scene

        if ent.entity_type == "NPC":
            if "goal" in updates:
                ent.goal = str(updates["goal"]).strip() or None
            if "character" in updates:
                ent.character = str(updates["character"]).strip() or None
            if "is_killable" in updates:
                ent.is_killable = bool(updates["is_killable"])
        elif ent.entity_type == "OBJECT":
            item_type = str(ent.item_type or "").upper()
            is_container = item_type == "CONTAINER"
            is_readable = item_type == "READABLE"
            metadata_json = dict(ent.metadata_json or {})
            lock_keys_present = any(
                k in updates for k in ("locked", "code_to_unlock", "item_to_unlock", "rule_to_unlock")
            )
            if lock_keys_present and is_container:
                code = str(updates.get("code_to_unlock", metadata_json.get("code_to_unlock") or "")).strip()
                item = str(updates.get("item_to_unlock", metadata_json.get("item_to_unlock") or "")).strip().upper()
                rule = str(updates.get("rule_to_unlock", metadata_json.get("rule_to_unlock") or "")).strip()
                if code:
                    code = code[:32]; item = ""; rule = ""
                elif item:
                    from backend.utils.text_utils import slugify
                    item = slugify(item).upper().replace("-", "_")[:64]; code = ""; rule = ""
                elif rule:
                    rule = rule[:500]; code = ""; item = ""
                else:
                    code = ""; item = ""; rule = ""
                metadata_json["code_to_unlock"] = code
                metadata_json["item_to_unlock"] = item
                metadata_json["rule_to_unlock"] = rule
                if "locked" in updates:
                    metadata_json["locked"] = bool(updates["locked"])
                else:
                    metadata_json["locked"] = bool(code or item or rule)
            elif lock_keys_present and not is_container:
                metadata_json.pop("code_to_unlock", None)
                metadata_json.pop("item_to_unlock", None)
                metadata_json.pop("rule_to_unlock", None)
                metadata_json.pop("locked", None)

            if "text_log_content" in updates and is_readable:
                text = str(updates["text_log_content"]).strip()
                if len(text) > 1000:
                    raise HTTPException(status_code=400, detail="text_log_content must be <= 1000 chars")
                metadata_json["text_log_content"] = text
            if "text_log_format" in updates and is_readable:
                fmt = str(updates["text_log_format"]).strip().upper()
                if fmt not in {"DOCUMENT", "SCROLL", "BOOK", "SIGN"}:
                    raise HTTPException(status_code=400, detail="text_log_format invalid")
                metadata_json["text_log_format"] = fmt

            ent.metadata_json = metadata_json
            flag_modified(ent, "metadata_json")

        return target_tag

    raise HTTPException(status_code=400, detail=f"Unsupported target_type '{patch.target_type}'")


def _format_finding_context_block(payload: AIFixSuggestionsRequest) -> str:
    if not payload.finding_context:
        return ""
    try:
        formatted = json.dumps(payload.finding_context, ensure_ascii=False, indent=2)
    except TypeError:
        formatted = str(payload.finding_context)
    return f"- Context:\n```json\n{formatted}\n```"


def _format_proposal_patches_block(proposal: FixProposal) -> str:
    lines = []
    for i, patch in enumerate(proposal.patches or [], start=1):
        try:
            updates = json.dumps(patch.field_updates or {}, ensure_ascii=False, indent=2)
        except TypeError:
            updates = str(patch.field_updates)
        lines.append(
            f"Patch #{i}:\n"
            f"  target_type: {patch.target_type}\n"
            f"  target_id: {patch.target_id or ''}\n"
            f"  description: {patch.description}\n"
            f"  field_updates:\n{updates}"
        )
    return "\n\n".join(lines) if lines else "(no patches)"


def _format_world_context_block(summary: dict[str, Any]) -> str:
    """Return the shared adventure + world context block used by both AI fix prompts."""
    adventure = summary.get("adventure") or {}
    return (
        f"Adventure Title: {adventure.get('title', '')}\n"
        f"Language: {adventure.get('language', '')}\n"
        f"Rule Mode: {adventure.get('rule_enforcement_mode', 'rpg')}\n\n"
        f"=== STORY METADATA ===\n"
        f"Teaser: {adventure.get('teaser', '') or ''}\n"
        f"Plot: {adventure.get('plot', '') or ''}\n"
        f"Rules: {adventure.get('rules', '') or ''}\n"
        f"Intro Text: {adventure.get('intro_text', '') or ''}\n\n"
        f"=== SCENES ({len(summary.get('scenes') or [])}) ===\n"
        f"{json.dumps(summary.get('scenes') or [], ensure_ascii=False)}\n\n"
        f"=== EXITS ({len(summary.get('exits') or [])}) ===\n"
        f"{json.dumps(summary.get('exits') or [], ensure_ascii=False)}\n\n"
        f"=== NPCs ({len(summary.get('npcs') or [])}) ===\n"
        f"{json.dumps(summary.get('npcs') or [], ensure_ascii=False)}\n\n"
        f"=== OBJECTS ({len(summary.get('objects') or [])}) ===\n"
        f"{json.dumps(summary.get('objects') or [], ensure_ascii=False)}\n\n"
        f"=== QUESTS ({len(summary.get('quests') or [])}) ===\n"
        f"{json.dumps(summary.get('quests') or [], ensure_ascii=False)}\n\n"
        f"=== WALKTHROUGH ===\n"
        f"{adventure.get('walkthrough', '') or ''}\n"
    )


def _parse_finding_location(
    location: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """Return ``(target_type, target_id)`` from a finding location like ``'object:SAFE_01'``."""
    if not location or not isinstance(location, str):
        return None, None
    parts = location.split(":", 1)
    if len(parts) != 2:
        return None, None
    ttype = parts[0].strip().lower()
    tid = parts[1].strip()
    if ttype not in {"scene", "object", "npc", "exit"} or not tid:
        return None, None
    return ttype, tid


def _format_focused_world_block(
    summary: dict[str, Any],
    *,
    location: Optional[str],
) -> str:
    """Build a small world context focused on the targeted finding.

    Drops full entity lists and instead ships only the targeted entity plus a
    few neighbors. For large adventures this turns a multi-thousand-token
    prompt into a few hundred tokens, which is the difference between an
    instant response and a provider timeout.
    """
    adventure = summary.get("adventure") or {}
    target_type, target_id = _parse_finding_location(location)

    target_block = ""
    neighbors: list[tuple[str, Any]] = []

    if target_type == "scene":
        scene = next(
            (s for s in (summary.get("scenes") or []) if s.get("id") == target_id),
            None,
        )
        if scene:
            target_block = (
                f"=== TARGET SCENE ({scene.get('id')}) ===\n"
                f"{json.dumps(scene, ensure_ascii=False)}\n"
            )
            scene_id_upper = str(scene.get("id") or "").upper()
            for obj in summary.get("objects") or []:
                if str(obj.get("current_scene_id") or "").upper() == scene_id_upper:
                    neighbors.append(("object", obj))
            for npc in summary.get("npcs") or []:
                if str(npc.get("current_scene_id") or "").upper() == scene_id_upper:
                    neighbors.append(("npc", npc))
            for ex in summary.get("exits") or []:
                if (
                    str(ex.get("from_scene_id") or "").upper() == scene_id_upper
                    or str(ex.get("to_scene_id") or "").upper() == scene_id_upper
                ):
                    neighbors.append(("exit", ex))
    elif target_type in ("object", "npc"):
        entity_list = (
            summary.get("objects") if target_type == "object" else summary.get("npcs")
        ) or []
        target_entity = next(
            (e for e in entity_list if e.get("id") == target_id),
            None,
        )
        if target_entity:
            target_block = (
                f"=== TARGET {target_type.upper()} ({target_entity.get('id')}) ===\n"
                f"{json.dumps(target_entity, ensure_ascii=False)}\n"
            )
            scene_id = str(target_entity.get("current_scene_id") or "").upper()
            if scene_id:
                scene = next(
                    (s for s in (summary.get("scenes") or []) if str(s.get("id") or "").upper() == scene_id),
                    None,
                )
                if scene:
                    neighbors.append(("scene", scene))
    elif target_type == "exit":
        ex = next(
            (e for e in (summary.get("exits") or []) if e.get("id") == target_id),
            None,
        )
        if ex:
            target_block = (
                f"=== TARGET EXIT ({ex.get('id')}) ===\n"
                f"{json.dumps(ex, ensure_ascii=False)}\n"
            )
            from_id = str(ex.get("from_scene_id") or "").upper()
            to_id = str(ex.get("to_scene_id") or "").upper()
            for s in summary.get("scenes") or []:
                sid = str(s.get("id") or "").upper()
                if sid in (from_id, to_id):
                    neighbors.append(("scene", s))

    neighbor_block = ""
    if neighbors:
        grouped: dict[str, list[Any]] = {}
        for kind, ent in neighbors[:12]:
            grouped.setdefault(kind, []).append(ent)
        chunks: list[str] = []
        for kind, ents in grouped.items():
            chunks.append(
                f"--- {kind.upper()} ({len(ents)}) ---\n"
                f"{json.dumps(ents, ensure_ascii=False)}"
            )
        neighbor_block = "\n\n".join(chunks) + "\n"

    return (
        f"Adventure Title: {adventure.get('title', '')}\n"
        f"Language: {adventure.get('language', '')}\n"
        f"Rule Mode: {adventure.get('rule_enforcement_mode', 'rpg')}\n\n"
        f"=== STORY METADATA ===\n"
        f"Plot: {_short_state(adventure.get('plot') or '', limit=600)}\n"
        f"Rules: {_short_state(adventure.get('rules') or '', limit=400)}\n"
        f"Walkthrough: {_short_state(adventure.get('walkthrough') or '', limit=1200)}\n\n"
        f"{target_block}\n"
        f"=== ADJACENT ENTITIES ===\n"
        f"{neighbor_block or '(none)'}\n"
    )


class _AIAttemptOutcome:
    """Outcome class for a single AI provider attempt."""

    SKIPPED_MISSING_KEY = "missing_key"
    SKIPPED_INIT_ERROR = "init_error"
    TIMEOUT = "timeout"
    CALL_ERROR = "call_error"

    def __init__(self, reason: str, *, provider: str, detail: str = "") -> None:
        self.reason = reason
        self.provider = provider
        self.detail = detail


class _AllProvidersFailed(Exception):
    """Raised when every AI provider in the chain failed.

    The ``outcomes`` list records the reason each provider failed so the
    caller can craft a user-facing message tailored to the actual failure
    pattern (e.g. all-missing-keys vs all-timeouts).
    """

    def __init__(self, outcomes: list[_AIAttemptOutcome]) -> None:
        self.outcomes = outcomes
        summary = ", ".join(
            f"{o.provider}({o.reason})" for o in outcomes
        )
        super().__init__(f"All AI providers failed: {summary}")


def _summarize_outcomes(outcomes: list[_AIAttemptOutcome]) -> str:
    """Produce a short, anbieter-neutrale user-facing message."""
    if not outcomes:
        return "The AI service did not respond. Please retry in a moment."
    reasons = {o.reason for o in outcomes}
    if reasons == {_AIAttemptOutcome.SKIPPED_MISSING_KEY}:
        return (
            "No AI provider is fully configured with an API key. "
            "Please add one in the LLM provider settings, "
            "or ask an admin to set the AI_FIX_FALLBACK_PROVIDER."
        )
    if reasons == {_AIAttemptOutcome.TIMEOUT}:
        return (
            "All AI providers are slow to respond right now. "
            "Please retry in a moment."
        )
    return "The AI service is currently unavailable. Please retry in a moment."


async def _generate_llm_proposals(
    *,
    user_prompt: str,
    current_user: User,
    response_model: type,
    gm_kwargs: dict[str, Any],
    timeout_seconds: Optional[float] = None,
    allow_fallback: bool = True,
) -> tuple[Any, Optional[str]]:
    """Call the LLM with a hard wall-clock cap and an optional fallback chain.

    Builds a candidate list straight from ``user.llm_settings``:

    1. ``complex_model_provider`` / ``complex_model`` (best reasoning).
    2. ``small_model_provider`` / ``small_model`` (typically small, fast).
    3. ``AI_FIX_FALLBACK_PROVIDER`` / ``AI_FIX_FALLBACK_MODEL`` env defaults.

    Each candidate is tried in order; provider construction errors
    (missing API key, configuration problems, …) and per-call timeouts
    cause the next candidate to take over. The first success wins.

    Returns ``(response, provider_label)``.

    On total failure, raises ``_AllProvidersFailed`` whose ``outcomes`` list
    captures the reason for each skipped/timed-out provider. Callers use
    this to decide whether to surface "no provider configured" vs
    "all timeouts" vs "generic unavailable" to the user.
    """
    llm_settings = current_user.llm_settings or {}
    seen: set[tuple[str, str]] = set()
    attempts: list[tuple[str, str]] = []

    def _add(provider: Optional[str], model: Optional[str]) -> None:
        if not provider:
            return
        candidate = (str(provider), str(model) if model else "")
        if candidate in seen:
            return
        seen.add(candidate)
        attempts.append(candidate)

    _add(
        llm_settings.get("complex_model_provider"),
        llm_settings.get("complex_model") or "gpt-4o",
    )
    _add(
        llm_settings.get("small_model_provider"),
        llm_settings.get("small_model") or "gpt-4o-mini",
    )
    if allow_fallback:
        _add(
            settings.AI_FIX_FALLBACK_PROVIDER,
            settings.AI_FIX_FALLBACK_MODEL or None,
        )

    if not attempts:
        attempts.append(("openai", "gpt-4o"))

    import asyncio as _asyncio

    outcomes: list[_AIAttemptOutcome] = []
    last_error: Optional[BaseException] = None
    for idx, (provider, model) in enumerate(attempts):
        try:
            gm = GameMasterLLM(
                user=current_user, provider=provider, model_category="complex"
            )
        except ValueError as exc:
            last_error = exc
            outcomes.append(
                _AIAttemptOutcome(
                    _AIAttemptOutcome.SKIPPED_MISSING_KEY,
                    provider=provider,
                    detail=str(exc),
                )
            )
            logger.info(
                "Skipping AI provider '%s' (model '%s'): %s",
                provider, model or "<default>", exc,
            )
            continue
        except Exception as exc:
            last_error = exc
            outcomes.append(
                _AIAttemptOutcome(
                    _AIAttemptOutcome.SKIPPED_INIT_ERROR,
                    provider=provider,
                    detail=str(exc),
                )
            )
            logger.warning(
                "Skipping AI provider '%s' (model '%s'): %s",
                provider, model or "<default>", exc,
            )
            continue

        coro = gm.aexecute_complex_task(
            system_prompt=gm_kwargs["system_prompt"],
            user_prompt=user_prompt,
            response_model=response_model,
            model=model,
        )
        try:
            if timeout_seconds and timeout_seconds > 0:
                result = await _asyncio.wait_for(coro, timeout=timeout_seconds)
            else:
                result = await coro
            return result, provider
        except _asyncio.TimeoutError as exc:
            last_error = TimeoutError(
                f"AI request to '{provider}' exceeded the {timeout_seconds:.0f}s cap"
            )
            outcomes.append(
                _AIAttemptOutcome(
                    _AIAttemptOutcome.TIMEOUT,
                    provider=provider,
                    detail=str(last_error),
                )
            )
            logger.warning(
                "AI call to '%s' (model '%s') timed out after %.0fs",
                provider, model, timeout_seconds or 0,
            )
            if idx < len(attempts) - 1:
                continue
            raise last_error from exc
        except Exception as exc:
            last_error = exc
            outcomes.append(
                _AIAttemptOutcome(
                    _AIAttemptOutcome.CALL_ERROR,
                    provider=provider,
                    detail=str(exc),
                )
            )
            logger.warning(
                "AI call to '%s' (model '%s') raised: %s",
                provider, model, exc,
            )
            if idx < len(attempts) - 1:
                continue
            raise

    if outcomes:
        logger.info(
            "All %d AI provider attempt(s) failed for user '%s'; reasons=%s",
            len(outcomes),
            current_user.username,
            ";".join(f"{o.provider}({o.reason})" for o in outcomes),
        )
    if last_error is not None:
        if outcomes:
            raise _AllProvidersFailed(outcomes) from last_error
        raise last_error
    return None, None


AIFIX_CACHE_TTL_SECONDS = 60 * 60  # 1 hour


async def _get_cached_suggestions(
    *,
    db: AsyncSession,
    template_id: str,
    user_id: str,
    signature: str,
) -> Optional[dict[str, Any]]:
    from datetime import datetime, timezone

    res = await db.execute(
        select(AIFixCache).where(
            AIFixCache.template_id == template_id,
            AIFixCache.user_id == user_id,
            AIFixCache.finding_signature == signature,
        )
    )
    row = res.scalars().first()
    if row is None:
        return None
    expires = row.expires_at
    if expires is not None:
        now = datetime.now(timezone.utc)
        compare_to = expires if expires.tzinfo else expires.replace(tzinfo=timezone.utc)
        if compare_to < now:
            try:
                await db.delete(row)
                await db.commit()
            except Exception:
                await db.rollback()
            return None
    return dict(row.response or {})


async def _write_cached_suggestions(
    *,
    db: AsyncSession,
    template_id: str,
    user_id: str,
    signature: str,
    response_payload: dict[str, Any],
) -> None:
    from datetime import datetime, timedelta, timezone

    res = await db.execute(
        select(AIFixCache).where(
            AIFixCache.template_id == template_id,
            AIFixCache.user_id == user_id,
            AIFixCache.finding_signature == signature,
        )
    )
    row = res.scalars().first()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=AIFIX_CACHE_TTL_SECONDS)
    if row is None:
        row = AIFixCache(
            template_id=template_id,
            user_id=user_id,
            finding_signature=signature,
            response=response_payload,
            expires_at=expires_at,
        )
        db.add(row)
    else:
        row.response = response_payload
        row.expires_at = expires_at
    try:
        await db.commit()
    except Exception:
        await db.rollback()


async def _evict_cached_suggestions(
    *,
    db: AsyncSession,
    template_id: str,
    user_id: str,
    signature: str,
) -> None:
    res = await db.execute(
        select(AIFixCache).where(
            AIFixCache.template_id == template_id,
            AIFixCache.user_id == user_id,
            AIFixCache.finding_signature == signature,
        )
    )
    for row in res.scalars().all():
        try:
            await db.delete(row)
        except Exception:
            pass
    try:
        await db.commit()
    except Exception:
        await db.rollback()


@router.post(
    "/{template_id}/editor/validate/findings/suggest-fix",
    response_model=AIFixSuggestionsResponse,
)


async def ai_suggest_fix_for_finding(
    template_id: str,
    payload: AIFixSuggestionsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suggest up to 3 different fixes for an AI-detected validation finding.

    Fast-path on cache hit (per (template, user, finding_signature)).
    Otherwise: focused world context, hard watchdog, provider fallback,
    persist on success. Always returns HTTP 200 with either proposals or a
    short, anbieter-neutral ``error`` string.
    """

    from datetime import datetime, timezone

    from backend.api.routes.adventures.schemas import (
        AISuggestFixWrapperResponse,
    )

    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    user_id = current_user.id

    signature = _signing(payload)

    cached = await _get_cached_suggestions(
        db=db,
        template_id=template_id,
        user_id=user_id,
        signature=signature,
    )
    if cached:
        cached = dict(cached)
        cached.setdefault("error", None)
        return AIFixSuggestionsResponse(**cached)

    debug_payload = await _build_adventure_editor_assets(template_id, db)
    summary = _summarize_world_for_fix(debug_payload)

    base_kwargs = {"system_prompt": AI_FIX_SUGGESTIONS_SYSTEM_PROMPT}
    world_block = _format_focused_world_block(
        summary, location=payload.finding_location,
    )
    context_block = _format_finding_context_block(payload)
    finding_block = (
        f"=== ORIGINAL FINDING ===\n"
        f"- Code: {payload.finding_code}\n"
        f"- Severity: {payload.finding_severity}\n"
        f"- Location: {(payload.finding_location or '').strip()}\n"
        f"- Message: {payload.finding_message}\n"
        f"{context_block}\n\n"
        f"{world_block}\n"
        f"Produce up to 3 distinct, immediately applicable fix proposals for the finding above.\n"
        f"Return ONLY the JSON object with a top-level 'proposals' key."
    )
    generated_at = datetime.now(timezone.utc).isoformat()

    try:
        wrapper, served_provider = await _generate_llm_proposals(
            user_prompt=finding_block,
            current_user=current_user,
            response_model=AISuggestFixWrapperResponse,
            gm_kwargs=base_kwargs,
            timeout_seconds=settings.AI_FIX_SUGGEST_TIMEOUT_SECONDS,
            allow_fallback=True,
        )
    except _AllProvidersFailed as exc:
        logger.warning(
            "AI fix suggestion unavailable for %s: %s",
            template_id, exc,
        )
        return AIFixSuggestionsResponse(
            finding_signature=signature,
            proposals=[],
            generated_at=generated_at,
            error=_summarize_outcomes(exc.outcomes),
        )
    except TimeoutError as exc:
        logger.warning(
            "AI fix suggestion timed out for %s after %.0fs: %s",
            template_id, settings.AI_FIX_SUGGEST_TIMEOUT_SECONDS, exc,
        )
        return AIFixSuggestionsResponse(
            finding_signature=signature,
            proposals=[],
            generated_at=generated_at,
            error="The AI service did not respond in time. Please retry in a moment.",
        )
    except Exception as exc:
        logger.exception("AI fix suggestion failed for %s: %s", template_id, exc)
        return AIFixSuggestionsResponse(
            finding_signature=signature,
            proposals=[],
            generated_at=generated_at,
            error="The AI service is currently unavailable. Please retry in a moment.",
        )

    proposals_in = (wrapper.proposals if wrapper else []) or []

    def _as_dict(value: Any) -> Optional[dict[str, Any]]:
        if isinstance(value, dict):
            return value
        if value is None:
            return None
        if hasattr(value, "model_dump"):
            try:
                dumped = value.model_dump()
                return dumped if isinstance(dumped, dict) else None
            except Exception:
                return None
        fields = ("title", "summary", "rationale", "patches",
                  "target_type", "target_id", "description", "field_updates", "note")
        collected = {}
        for f in fields:
            if hasattr(value, f):
                collected[f] = getattr(value, f)
        return collected or None

    proposals: list[FixProposal] = []
    for raw in proposals_in[:3]:
        raw_dict = _as_dict(raw)
        if raw_dict is None:
            continue
        title = str(raw_dict.get("title") or "").strip()
        summary_text = str(raw_dict.get("summary") or "").strip()
        if not title or not summary_text:
            continue
        rationale = raw_dict.get("rationale")
        patches_in = raw_dict.get("patches") or []
        clean_patches: list[FixProposalEntityPatch] = []
        for p in patches_in:
            p_dict = _as_dict(p)
            if p_dict is None:
                continue
            target_type = str(p_dict.get("target_type") or "").strip()
            if target_type not in {"scene", "object", "npc", "exit", "protagonist", "adventure"}:
                continue
            field_updates = p_dict.get("field_updates") or {}
            if not isinstance(field_updates, dict) or not field_updates:
                continue
            clean_patches.append(
                FixProposalEntityPatch(
                    target_type=target_type,  # type: ignore[arg-type]
                    target_id=(str(p_dict.get("target_id")).strip() if p_dict.get("target_id") is not None else None),
                    description=str(p_dict.get("description") or "").strip()[:280],
                    field_updates={str(k): v for k, v in field_updates.items() if k in _allowed_fields_for(target_type)},
                )
            )
        if not clean_patches:
            continue
        proposals.append(
            FixProposal(
                title=title[:120],
                summary=summary_text[:600],
                rationale=(str(rationale).strip()[:400] if rationale else None),
                patches=clean_patches,
            )
        )

    response = AIFixSuggestionsResponse(
        finding_signature=signature,
        proposals=proposals,
        generated_at=generated_at,
    )
    if proposals:
        try:
            await _write_cached_suggestions(
                db=db,
                template_id=template_id,
                user_id=user_id,
                signature=signature,
                response_payload=response.model_dump(),
            )
        except Exception as cache_exc:
            logger.warning(
                "Failed to persist AI fix cache for %s/%s: %s",
                template_id, signature, cache_exc,
            )
    return response


@router.post(
    "/{template_id}/editor/validate/findings/apply-fix",
    response_model=AIFixApplyResponse,
)
async def ai_apply_fix_proposal(
    template_id: str,
    payload: AIFixApplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply the chosen fix proposal directly to the adventure template.

    The proposal's ``patches[]`` are treated as the authoritative source of
    truth; no second LLM call is made. Field updates that fall outside the
    per-target allowlist are silently dropped.
    """

    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    user_id = current_user.id

    proposal_patches = payload.proposal.patches or []
    if not proposal_patches:
        return AIFixApplyResponse(
            status="no_op",
            applied_targets=[],
            message="The selected proposal contained no patches to apply.",
        )

    applied_tags: list[str] = []
    seen_keys: set[tuple[str, str]] = set()
    failed_resolution = False

    for proposal_patch in proposal_patches:
        allowed = _allowed_fields_for(proposal_patch.target_type)
        if not allowed:
            continue
        clean_updates: dict[str, Any] = {}
        for field, value in (proposal_patch.field_updates or {}).items():
            if field not in allowed:
                continue
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            clean_updates[field] = value
        if not clean_updates:
            continue

        try:
            tag = await _apply_proposal_patch(
                db=db,
                template_id=template_id,
                adv=adv,
                patch=FixProposalEntityPatch(
                    target_type=proposal_patch.target_type,  # type: ignore[arg-type]
                    target_id=proposal_patch.target_id,
                    description=proposal_patch.description,
                    field_updates=clean_updates,
                ),
            )
        except HTTPException as exc:
            if exc.status_code == 400 and "could not be resolved" in str(exc.detail):
                failed_resolution = True
                continue
            raise
        if not tag:
            continue
        key = (str(proposal_patch.target_type), (proposal_patch.target_id or "").strip())
        if key in seen_keys:
            continue
        seen_keys.add(key)
        applied_tags.append(tag)

    if applied_tags:
        await db.commit()
        await _evict_cached_suggestions(
            db=db,
            template_id=template_id,
            user_id=user_id,
            signature=payload.finding_signature,
        )
    else:
        await db.rollback()
        if failed_resolution:
            await _evict_cached_suggestions(
                db=db,
                template_id=template_id,
                user_id=user_id,
                signature=payload.finding_signature,
            )

    if applied_tags and len(applied_tags) < len(proposal_patches):
        status: Literal["applied", "no_op", "partial"] = "partial"
    elif applied_tags:
        status = "applied"
    else:
        status = "no_op"

    message = (
        f"Applied {len(applied_tags)} patch(es) out of {len(proposal_patches)}."
        if applied_tags
        else "No changes were applied."
    )
    if failed_resolution and not applied_tags:
        message = (
            "The cached AI reference is out of date. "
            "Please click AI-Fix again to regenerate."
        )

    return AIFixApplyResponse(
        status=status,
        applied_targets=applied_tags,
        message=message,
    )



@router.post("/{template_id}/editor/scene")
async def create_editor_scene(
    template_id: str,
    payload: SceneCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _get_owned_adventure_or_404(db, template_id, current_user.id)

    scene_id = _sanitize_object_id(payload.scene_id, "scene_id")
    label = str(payload.label or "").strip()
    description = str(payload.description or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="label is required")
    if not description:
        raise HTTPException(status_code=400, detail="description is required")

    clean_decor: list[str] = []
    if payload.decorative_objects:
        for d in payload.decorative_objects:
            s = d.strip()
            if not s:
                continue
            if len(s) > 100:
                raise HTTPException(status_code=400, detail="Each decorative object must be at most 100 characters.")
            clean_decor.append(s)
        clean_decor = clean_decor[:7]

    existing_scene = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
            WorldScene.id == scene_id,
        )
    )
    if existing_scene.scalars().first():
        raise HTTPException(status_code=409, detail="scene_id already exists")

    existing_entity = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.id == scene_id,
        )
    )
    if existing_entity.scalars().first():
        raise HTTPException(status_code=409, detail="ID already exists as an entity")

    scene = WorldScene(
        id=scene_id,
        template_id=template_id,
        session_id=None,
        label=label,
        description=description,
        image_url=str(payload.image_url or "").strip() or None,
        decorative_objects=clean_decor or None,
    )
    db.add(scene)
    await db.commit()
    return {"status": "success", "scene": _serialize_model(scene)}


@router.delete("/{template_id}/editor/scene/{scene_id}")
async def delete_editor_scene(
    template_id: str,
    scene_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    scene_id = _sanitize_object_id(scene_id, "scene_id")

    scene_res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
            WorldScene.id == scene_id,
        )
    )
    scene = scene_res.scalars().first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    await db.execute(
        delete(WorldExit).where(
            WorldExit.template_id == template_id,
            WorldExit.session_id.is_(None),
            ((WorldExit.from_scene_id == scene_id) | (WorldExit.to_scene_id == scene_id)),
        )
    )
    await db.execute(
        delete(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.current_scene_id == scene_id,
        )
    )
    await db.delete(scene)

    manifest = deepcopy(adv.original_manifest or {})
    if (manifest.get("start_scene_id") or "") == scene_id:
        replacement_scene_res = await db.execute(
            select(WorldScene.id).where(
                WorldScene.template_id == template_id,
                WorldScene.session_id.is_(None),
                WorldScene.id != scene_id,
            )
        )
        replacement_scene_id = replacement_scene_res.scalars().first()
        if replacement_scene_id:
            manifest["start_scene_id"] = replacement_scene_id
        else:
            manifest.pop("start_scene_id", None)
        adv.original_manifest = manifest

    await db.commit()
    return {"status": "success", "deleted_scene_id": scene_id}


@router.post("/{template_id}/editor/exit")
async def create_editor_exit(
    template_id: str,
    payload: ExitCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _get_owned_adventure_or_404(db, template_id, current_user.id)

    from_scene_id = _sanitize_object_id(payload.from_scene_id, "from_scene_id")
    to_scene_id = _sanitize_object_id(payload.to_scene_id, "to_scene_id")
    if from_scene_id == to_scene_id:
        raise HTTPException(status_code=400, detail="from_scene_id and to_scene_id must differ")

    await _ensure_template_scene_exists(db, template_id, from_scene_id)
    await _ensure_template_scene_exists(db, template_id, to_scene_id)

    label = str(payload.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="label is required")

    code, item, rule = _normalize_lock_fields(
        code_to_unlock=payload.code_to_unlock,
        item_to_unlock=payload.item_to_unlock,
        rule_to_unlock=payload.rule_to_unlock,
    )

    world_exit = WorldExit(
        template_id=template_id,
        session_id=None,
        from_scene_id=from_scene_id,
        to_scene_id=to_scene_id,
        label=label,
        exit_type=payload.exit_type,
        is_locked=bool(payload.is_locked or code or item or rule),
        lock_description=str(payload.lock_description or "").strip() or None,
        code_to_unlock=code or None,
        item_to_unlock=item or None,
        rule_to_unlock=rule or None,
    )
    db.add(world_exit)
    await db.commit()
    return {"status": "success", "exit": _serialize_model(world_exit)}


@router.delete("/{template_id}/editor/exit/{exit_id}")
async def delete_editor_exit(
    template_id: str,
    exit_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _get_owned_adventure_or_404(db, template_id, current_user.id)

    exit_res = await db.execute(
        select(WorldExit).where(
            WorldExit.template_id == template_id,
            WorldExit.session_id.is_(None),
            WorldExit.id == exit_id,
        )
    )
    world_exit = exit_res.scalars().first()
    if not world_exit:
        raise HTTPException(status_code=404, detail="Exit not found")

    await db.delete(world_exit)
    await db.commit()
    return {"status": "success", "deleted_exit_id": exit_id}


@router.post("/{template_id}/editor/entity")
async def create_editor_entity(
    template_id: str,
    payload: EntityCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _get_owned_adventure_or_404(db, template_id, current_user.id)

    entity_id = _sanitize_object_id(payload.entity_id, "entity_id")
    scene_id = _sanitize_object_id(payload.scene_id, "scene_id")
    await _ensure_template_scene_exists(db, template_id, scene_id)

    name = str(payload.name or "").strip()
    description = str(payload.description or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not description:
        raise HTTPException(status_code=400, detail="description is required")

    existing_ent = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.id == entity_id,
        )
    )
    if existing_ent.scalars().first():
        raise HTTPException(status_code=409, detail="entity_id already exists")

    existing_scene = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
            WorldScene.id == entity_id,
        )
    )
    if existing_scene.scalars().first():
        raise HTTPException(status_code=409, detail="ID already exists as a scene")

    item_type = str(payload.item_type or "").strip().upper() if payload.entity_type == "OBJECT" else None
    entity = WorldEntity(
        id=entity_id,
        template_id=template_id,
        session_id=None,
        entity_type=payload.entity_type,
        name=name,
        description=description,
        current_scene_id=scene_id,
        image_url=str(payload.image_url or "").strip() or None,
        item_type=item_type,
        is_hidden=True if item_type == "CONSTRUCTABLE" else (bool(payload.is_hidden) if payload.is_hidden is not None else False),
        reveal_rule=str(payload.reveal_rule or "").strip() or None,
        is_portable=bool(payload.is_portable) if payload.is_portable is not None else True,
        goal=str(payload.goal or "").strip() or None,
        character=str(payload.character or "").strip() or None,
        hp=payload.hp,
        max_hp=payload.hp,
        mana=payload.mana,
        max_mana=payload.mana,
        stamina=payload.stamina,
        max_stamina=payload.stamina,
        is_killable=bool(payload.is_killable) if payload.is_killable is not None else True,
        metadata_json=dict(payload.metadata_json or {}),
        inventory=list(payload.inventory or []),
        wearable_slots=payload.wearable_slots,
        combination_ingredients=payload.combination_ingredients,
        stat_modifier_strength=payload.stat_modifier_strength,
    )
    db.add(entity)
    await db.commit()
    return {"status": "success", "entity": _serialize_model(entity)}


@router.delete("/{template_id}/editor/entity/{entity_id}")
async def delete_editor_entity(
    template_id: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    entity_id = _sanitize_object_id(entity_id, "entity_id")

    ent_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.id == entity_id,
        )
    )
    entity = ent_res.scalars().first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    await db.delete(entity)
    await db.commit()
    return {"status": "success", "deleted_entity_id": entity_id}


@router.post("/{template_id}/editor/entity/{entity_id}/clone")
async def clone_editor_entity(
    template_id: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    entity_id = _sanitize_object_id(entity_id, "entity_id")

    ent_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.id == entity_id,
        )
    )
    source = ent_res.scalars().first()
    if not source:
        raise HTTPException(status_code=404, detail="Entity not found")

    base_id = f"{entity_id}_1"
    new_id = base_id
    suffix = 1
    while True:
        exists = await db.execute(
            select(WorldEntity.id).where(
                WorldEntity.template_id == template_id,
                WorldEntity.session_id.is_(None),
                WorldEntity.id == new_id,
            )
        )
        if not exists.scalars().first():
            break
        suffix += 1
        new_id = f"{entity_id}_{suffix}"

    cloned_image_url = await _clone_entity_image(
        source_image_url=source.image_url,
        template_id=template_id,
        new_entity_id=new_id,
    )

    clone = WorldEntity(
        id=new_id,
        template_id=template_id,
        session_id=None,
        entity_type=source.entity_type,
        name=source.name,
        description=source.description,
        current_scene_id=source.current_scene_id,
        spatial_position=source.spatial_position,
        image_url=cloned_image_url,
        item_type=source.item_type,
        wearable_slots=list(source.wearable_slots) if source.wearable_slots is not None else None,
        is_in_inventory=source.is_in_inventory,
        is_hidden=source.is_hidden,
        reveal_rule=source.reveal_rule,
        unlock_rule=source.unlock_rule,
        is_portable=source.is_portable,
        combination_ingredients=list(source.combination_ingredients) if source.combination_ingredients is not None else None,
        reveals_item_id=None,
        is_final_state=source.is_final_state,
        state_comment=source.state_comment,
        npc_type=source.npc_type,
        movement_type=source.movement_type,
        goal=source.goal,
        character=source.character,
        hp=source.hp,
        max_hp=source.max_hp,
        mana=source.mana,
        max_mana=source.max_mana,
        stamina=source.stamina,
        max_stamina=source.max_stamina,
        voice=source.voice,
        stat_modifier_strength=source.stat_modifier_strength,
        stat_modifier_dexterity=source.stat_modifier_dexterity,
        stat_modifier_intelligence=source.stat_modifier_intelligence,
        stat_modifier_wisdom=source.stat_modifier_wisdom,
        stat_modifier_charisma=source.stat_modifier_charisma,
        stat_modifier_armor_class=source.stat_modifier_armor_class,
        is_attackable=source.is_attackable,
        is_killable=source.is_killable,
        inventory=[item if isinstance(item, str) else dict(item) for item in (source.inventory or [])],
        metadata_json=dict(source.metadata_json or {}),
    )
    db.add(clone)
    await db.commit()
    return {"status": "success", "entity": _serialize_model(clone), "source_id": entity_id, "new_id": new_id}


@router.post("/{template_id}/editor/quest")
async def create_editor_quest(
    template_id: str,
    payload: QuestCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)

    quest_id = _sanitize_editor_id(payload.id, "id")
    quests = list(adv.quests or [])
    if any(str(q.get("id") or "") == quest_id for q in quests):
        raise HTTPException(status_code=409, detail="quest id already exists")

    quest = {
        "id": quest_id,
        "title": str(payload.title or "").strip(),
        "description": str(payload.description or "").strip(),
        "goal": str(payload.goal or "").strip(),
        "impact": str(payload.impact or "").strip(),
        "exp_reward": int(payload.exp_reward or 0),
        "is_main": bool(payload.is_main),
        "status": "open",
    }
    if not quest["title"]:
        raise HTTPException(status_code=400, detail="title is required")

    quests.append(quest)
    adv.quests = quests
    await db.commit()
    return {"status": "success", "quest": quest}


@router.delete("/{template_id}/editor/quest/{quest_id}")
async def delete_editor_quest(
    template_id: str,
    quest_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    quest_id = _sanitize_editor_id(quest_id, "quest_id")

    quests = list(adv.quests or [])
    filtered = [q for q in quests if str(q.get("id") or "") != quest_id]
    if len(filtered) == len(quests):
        raise HTTPException(status_code=404, detail="Quest not found")

    adv.quests = filtered
    await db.commit()
    return {"status": "success", "deleted_quest_id": quest_id}


@router.post("/{template_id}/editor/award")
async def create_editor_award(
    template_id: str,
    payload: AwardCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)

    award_key = _sanitize_editor_id(payload.key, "key")
    awards = list(adv.awards or [])
    if any(str(a.get("key") or "") == award_key for a in awards):
        raise HTTPException(status_code=409, detail="award key already exists")

    award = {
        "key": award_key,
        "title": str(payload.title or "").strip(),
        "description": str(payload.description or "").strip(),
        "tier": payload.tier,
        "requirement": str(payload.requirement or "").strip(),
        "is_earned": bool(payload.is_earned),
    }
    if not award["title"]:
        raise HTTPException(status_code=400, detail="title is required")

    awards.append(award)
    adv.awards = awards
    await db.commit()
    return {"status": "success", "award": award}


@router.delete("/{template_id}/editor/award/{award_key}")
async def delete_editor_award(
    template_id: str,
    award_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    award_key = _sanitize_editor_id(award_key, "award_key")

    awards = list(adv.awards or [])
    filtered = [a for a in awards if str(a.get("key") or "") != award_key]
    if len(filtered) == len(awards):
        raise HTTPException(status_code=404, detail="Award not found")

    adv.awards = filtered
    await db.commit()
    return {"status": "success", "deleted_award_key": award_key}

@router.patch("/{template_id}/editor/entity")
async def update_editor_entity(
    template_id: str,
    payload: EntityUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")
        
    if payload.target_type == "cover":
        if payload.name is not None: adv.title = payload.name
        if payload.teaser is not None: adv.teaser = payload.teaser
        if payload.description is not None: adv.original_prompt = payload.description
    elif payload.target_type == "protagonist":
        avatar = await _get_template_avatar(db, template_id)
        if not avatar:
            avatar = await _restore_missing_template_avatar(db, template_id, adv)
        if avatar:
            if payload.name is not None: avatar.name = payload.name
            if payload.description is not None: avatar.description = payload.description
            if payload.goal is not None: avatar.goal = payload.goal
            if payload.character is not None: avatar.character = payload.character
            if payload.hp is not None: 
                avatar.hp = payload.hp
                avatar.max_hp = payload.hp
            if payload.mana is not None: 
                avatar.mana = payload.mana
                avatar.max_mana = payload.mana
            if payload.stamina is not None: 
                avatar.stamina = payload.stamina
                avatar.max_stamina = payload.stamina
            if payload.strength is not None: avatar.strength = payload.strength
            if payload.intelligence is not None: avatar.intelligence = payload.intelligence
            if payload.wisdom is not None: avatar.wisdom = payload.wisdom
            if payload.dexterity is not None: avatar.dexterity = payload.dexterity
            if payload.charisma is not None: avatar.charisma = payload.charisma
            if payload.armor_class is not None: avatar.armor_class = payload.armor_class
            if payload.exp is not None: avatar.exp = payload.exp
            if payload.inventory is not None:
                avatar.inventory = list(payload.inventory)
                flag_modified(avatar, "inventory")
            if payload.equipment is not None:
                avatar.equipment = dict(payload.equipment)
                flag_modified(avatar, "equipment")
    elif payload.target_type == "scene":
        sc_res = await db.execute(select(WorldScene).where(WorldScene.template_id == template_id, WorldScene.session_id.is_(None), WorldScene.id == payload.target_id))
        scene = sc_res.scalars().first()
        if scene:
            old_id = scene.id
            if payload.new_id is not None:
                new_id = payload.new_id.strip().upper()
                if not new_id:
                    raise HTTPException(status_code=400, detail="Scene ID cannot be empty")
                import re
                if not re.match(r"^[A-Z0-9_]+$", new_id):
                    raise HTTPException(status_code=400, detail="Scene ID must contain only uppercase letters, digits, and underscores.")
                if len(new_id) > 50:
                    raise HTTPException(status_code=400, detail="Scene ID must be at most 50 characters.")
                
                if new_id != old_id:
                    # check duplicate scene ID
                    dup_scene_res = await db.execute(select(WorldScene).where(WorldScene.template_id == template_id, WorldScene.session_id.is_(None), WorldScene.id == new_id))
                    if dup_scene_res.scalars().first():
                        raise HTTPException(status_code=409, detail=f"Scene ID '{new_id}' already exists")
                    
                    # check duplicate entity ID
                    dup_ent_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id, WorldEntity.session_id.is_(None), WorldEntity.id == new_id))
                    if dup_ent_res.scalars().first():
                        raise HTTPException(status_code=409, detail=f"ID '{new_id}' is already taken by an entity")
                    
                    # Apply scene ID update
                    scene.id = new_id
                    
                    # Cascade update exits
                    exits_res = await db.execute(select(WorldExit).where(WorldExit.template_id == template_id, WorldExit.session_id.is_(None)))
                    for world_exit in exits_res.scalars().all():
                        if world_exit.from_scene_id == old_id:
                            world_exit.from_scene_id = new_id
                        if world_exit.to_scene_id == old_id:
                            world_exit.to_scene_id = new_id
                    
                    # Cascade update entities positions
                    ents_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id, WorldEntity.session_id.is_(None)))
                    for ent in ents_res.scalars().all():
                        if ent.current_scene_id == old_id:
                            ent.current_scene_id = new_id
                    
                    # Cascade update start scene ID in manifest
                    manifest = deepcopy(adv.original_manifest or {})
                    if manifest.get("start_scene_id") == old_id:
                        manifest["start_scene_id"] = new_id
                        adv.original_manifest = manifest

            if payload.name is not None: scene.label = payload.name

            if payload.description is not None:
                scene.description = payload.description.strip()

            if payload.decorative_objects is not None:
                decor_list: list[str] = []
                for d in payload.decorative_objects:
                    s = d.strip()
                    if not s:
                        continue
                    if len(s) > 100:
                        raise HTTPException(status_code=400, detail="Each decorative object must be at most 100 characters.")
                    decor_list.append(s)
                scene.decorative_objects = decor_list[:7] or None
                flag_modified(scene, "decorative_objects")
    elif payload.target_type == "exit":
        ex_res = await db.execute(select(WorldExit).where(WorldExit.template_id == template_id, WorldExit.id == payload.target_id))
        world_exit = ex_res.scalars().first()
        if world_exit:
            if payload.name is not None: world_exit.label = payload.name
            if payload.locked is not None: world_exit.is_locked = bool(payload.locked)
            if payload.description is not None: world_exit.lock_description = payload.description
            if payload.exit_type is not None: world_exit.exit_type = payload.exit_type
            
            # Enforce mutual exclusivity and priority on exit lock attributes
            if payload.code_to_unlock is not None or payload.item_to_unlock is not None or payload.rule_to_unlock is not None:
                code = world_exit.code_to_unlock or ""
                item = world_exit.item_to_unlock or ""
                rule = world_exit.rule_to_unlock or ""
                if payload.code_to_unlock is not None:
                    code = str(payload.code_to_unlock or "").strip()
                if payload.item_to_unlock is not None:
                    item = str(payload.item_to_unlock or "").strip().upper()
                if payload.rule_to_unlock is not None:
                    rule = str(payload.rule_to_unlock or "").strip()

                if code:
                    code = code[:32]
                    item = ""
                    rule = ""
                elif item:
                    from backend.utils.text_utils import slugify
                    item = slugify(item).upper().replace("-", "_")[:64]
                    code = ""
                    rule = ""
                elif rule:
                    rule = rule[:500]
                    code = ""
                    item = ""
                else:
                    code = ""
                    item = ""
                    rule = ""

                world_exit.code_to_unlock = code
                world_exit.item_to_unlock = item
                world_exit.rule_to_unlock = rule
    else:
        en_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id, WorldEntity.session_id.is_(None), WorldEntity.id == payload.target_id))
        ent = en_res.scalars().first()
        if ent:
            old_id = ent.id
            if payload.new_id is not None:
                new_id = payload.new_id.strip().upper()
                if not new_id:
                    raise HTTPException(status_code=400, detail="Entity ID cannot be empty")
                import re
                if not re.match(r"^[A-Z0-9_]+$", new_id):
                    raise HTTPException(status_code=400, detail="Entity ID must contain only uppercase letters, digits, and underscores.")
                if len(new_id) > 30:
                    raise HTTPException(status_code=400, detail="Entity ID must be at most 30 characters.")
                
                if new_id != old_id:
                    # check duplicate entity ID
                    dup_ent_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id, WorldEntity.session_id.is_(None), WorldEntity.id == new_id))
                    if dup_ent_res.scalars().first():
                        raise HTTPException(status_code=409, detail=f"Entity ID '{new_id}' already exists")
                    
                    # check duplicate scene ID
                    dup_scene_res = await db.execute(select(WorldScene).where(WorldScene.template_id == template_id, WorldScene.session_id.is_(None), WorldScene.id == new_id))
                    if dup_scene_res.scalars().first():
                        raise HTTPException(status_code=409, detail=f"ID '{new_id}' is already taken by a scene")
                    
                    # Apply entity ID update
                    ent.id = new_id
                    
                    # Cascade update exits lock keys
                    exits_res = await db.execute(select(WorldExit).where(WorldExit.template_id == template_id, WorldExit.session_id.is_(None)))
                    for world_exit in exits_res.scalars().all():
                        if world_exit.item_to_unlock == old_id:
                            world_exit.item_to_unlock = new_id
                    
                    # Cascade update all entities combination_ingredients, reveals_item_id, and inventory
                    all_ents_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id, WorldEntity.session_id.is_(None)))
                    for other_ent in all_ents_res.scalars().all():
                        if other_ent.combination_ingredients:
                            ingredients = list(other_ent.combination_ingredients)
                            if old_id in ingredients:
                                other_ent.combination_ingredients = [new_id if x == old_id else x for x in ingredients]
                        
                        if other_ent.reveals_item_id == old_id:
                            other_ent.reveals_item_id = new_id
                        
                        if other_ent.inventory:
                            inv = list(other_ent.inventory)
                            updated_inv = []
                            changed = False
                            for item in inv:
                                if isinstance(item, str):
                                    if item == old_id:
                                        updated_inv.append(new_id)
                                        changed = True
                                    else:
                                        updated_inv.append(item)
                                elif isinstance(item, dict) and item.get("id") == old_id:
                                    item = dict(item)
                                    item["id"] = new_id
                                    updated_inv.append(item)
                                    changed = True
                                else:
                                    updated_inv.append(item)
                            if changed:
                                other_ent.inventory = updated_inv
                    
                    # Cascade update protagonist starting inventory and equipment
                    avatar = await _get_template_avatar(db, template_id)
                    if avatar:
                        if avatar.inventory:
                            inv = list(avatar.inventory)
                            updated_inv = []
                            changed = False
                            for item in inv:
                                if isinstance(item, str):
                                    if item == old_id:
                                        updated_inv.append(new_id)
                                        changed = True
                                    else:
                                        updated_inv.append(item)
                                elif isinstance(item, dict) and item.get("id") == old_id:
                                    item = dict(item)
                                    item["id"] = new_id
                                    updated_inv.append(item)
                                    changed = True
                                else:
                                    updated_inv.append(item)
                            if changed:
                                avatar.inventory = updated_inv
                        
                        if avatar.equipment:
                            eq = dict(avatar.equipment)
                            changed = False
                            for slot, eq_item in eq.items():
                                if isinstance(eq_item, str):
                                    if eq_item == old_id:
                                        eq[slot] = new_id
                                        changed = True
                                elif isinstance(eq_item, dict) and eq_item.get("id") == old_id:
                                    eq_item = dict(eq_item)
                                    eq_item["id"] = new_id
                                    eq[slot] = eq_item
                                    changed = True
                            if changed:
                                avatar.equipment = eq
            if payload.name is not None: ent.name = payload.name
            if payload.description is not None: ent.description = payload.description
            if payload.hp is not None: 
                ent.hp = payload.hp
                ent.max_hp = payload.hp
            if payload.mana is not None: 
                ent.mana = payload.mana
                ent.max_mana = payload.mana
            if payload.stamina is not None: 
                ent.stamina = payload.stamina
                ent.max_stamina = payload.stamina
            if ent.entity_type == "NPC":
                if payload.goal is not None: ent.goal = payload.goal
                if payload.character is not None: ent.character = payload.character
                if payload.is_killable is not None: ent.is_killable = payload.is_killable
                if payload.inventory is not None:
                    ent.inventory = list(payload.inventory)
                    flag_modified(ent, "inventory")
                if payload.current_scene_id is not None:
                    new_scene_id = str(payload.current_scene_id or "").strip().upper()
                    if not new_scene_id:
                        raise HTTPException(status_code=400, detail="current_scene_id cannot be empty")
                    if len(new_scene_id) > 50:
                        raise HTTPException(status_code=400, detail="current_scene_id must be at most 50 characters.")
                    if not _SAFE_SCENE_ID_RE.match(new_scene_id):
                        raise HTTPException(status_code=400, detail="current_scene_id must contain only uppercase letters, digits, and underscores.")
                    await _ensure_template_scene_exists(db, template_id, new_scene_id)
                    ent.current_scene_id = new_scene_id
            if ent.entity_type == "OBJECT":
                if payload.current_scene_id is not None:
                    new_scene_id = str(payload.current_scene_id or "").strip().upper()
                    if not new_scene_id:
                        raise HTTPException(status_code=400, detail="current_scene_id cannot be empty")
                    if len(new_scene_id) > 50:
                        raise HTTPException(status_code=400, detail="current_scene_id must be at most 50 characters.")
                    if not _SAFE_SCENE_ID_RE.match(new_scene_id):
                        raise HTTPException(status_code=400, detail="current_scene_id must contain only uppercase letters, digits, and underscores.")
                    await _ensure_template_scene_exists(db, template_id, new_scene_id)
                    ent.current_scene_id = new_scene_id
                # Apply type change first so the cascade branches below run against
                # the NEW type. The old code computed `is_readable_object` etc.
                # against the pre-PATCH value, which silently dropped the user's
                # choice when changing e.g. CONTAINER -> READABLE.
                new_item_type_value: Optional[str] = None
                if payload.item_type is not None:
                    normalized_new_type = str(payload.item_type or "").strip().upper()
                    if normalized_new_type and normalized_new_type != str(ent.item_type or "").upper():
                        if normalized_new_type not in {
                            "DEFAULT",
                            "CONSUMABLE",
                            "WEARABLE",
                            "WEAPON",
                            "COMBINABLE",
                            "CONSTRUCTABLE",
                            "READABLE",
                            "CONTAINER",
                            "SWITCH",
                        }:
                            raise HTTPException(
                                status_code=400,
                                detail=(
                                    "item_type must be one of DEFAULT, CONSUMABLE, WEARABLE, "
                                    "WEAPON, COMBINABLE, CONSTRUCTABLE, READABLE, CONTAINER, SWITCH."
                                ),
                            )
                        new_item_type_value = normalized_new_type
                        ent.item_type = normalized_new_type
                item_type = str(ent.item_type or "").upper()
                is_readable_object = item_type == "READABLE"
                is_container_object = item_type == "CONTAINER"
                is_switch_object = item_type == "SWITCH"
                is_consumable_object = item_type == "CONSUMABLE"

                if payload.description is not None and is_readable_object and len(payload.description) > 200:
                    raise HTTPException(status_code=400, detail="description must be at most 200 characters for READABLE objects.")
                if payload.is_portable is not None:
                    ent.is_portable = bool(payload.is_portable)

                metadata_json = dict(ent.metadata_json or {})

                # 1. Container locks (only for CONTAINER items)
                if is_container_object:
                    if payload.code_to_unlock is not None or payload.item_to_unlock is not None or payload.rule_to_unlock is not None or payload.locked is not None:
                        code = metadata_json.get("code_to_unlock") or ""
                        item = metadata_json.get("item_to_unlock") or ""
                        rule = metadata_json.get("rule_to_unlock") or ""
                        
                        if payload.code_to_unlock is not None:
                            code = str(payload.code_to_unlock or "").strip()
                        if payload.item_to_unlock is not None:
                            item = str(payload.item_to_unlock or "").strip().upper()
                        if payload.rule_to_unlock is not None:
                            rule = str(payload.rule_to_unlock or "").strip()

                        if code:
                            code = code[:32]
                            item = ""
                            rule = ""
                        elif item:
                            from backend.utils.text_utils import slugify
                            item = slugify(item).upper().replace("-", "_")[:64]
                            code = ""
                            rule = ""
                        elif rule:
                            rule = rule[:500]
                            code = ""
                            item = ""
                        else:
                            code = ""
                            item = ""
                            rule = ""

                        metadata_json["code_to_unlock"] = code
                        metadata_json["item_to_unlock"] = item
                        metadata_json["rule_to_unlock"] = rule
                        if payload.locked is not None:
                            metadata_json["locked"] = bool(payload.locked)
                        else:
                            metadata_json["locked"] = bool(code or item or rule)
                        
                        ent.unlock_rule = None
                else:
                    # Clean up unlock fields if the item is not a CONTAINER anymore
                    metadata_json.pop("code_to_unlock", None)
                    metadata_json.pop("item_to_unlock", None)
                    metadata_json.pop("rule_to_unlock", None)
                    metadata_json.pop("locked", None)

                if payload.inventory is not None:
                    ent.inventory = payload.inventory
                    flag_modified(ent, "inventory")

                # 2. Readable log content (only for READABLE items)
                if is_readable_object:
                    if payload.text_log_content is not None:
                        if len(payload.text_log_content) > 1000:
                            raise HTTPException(status_code=400, detail="text_log_content must be at most 1000 characters.")
                        metadata_json["text_log_content"] = payload.text_log_content.strip()
                    if payload.text_log_format is not None:
                        normalized_format = str(payload.text_log_format).strip().upper()
                        allowed_formats = {"DOCUMENT", "SCROLL", "BOOK", "SIGN"}
                        if normalized_format not in allowed_formats:
                            raise HTTPException(status_code=400, detail="text_log_format must be one of DOCUMENT, SCROLL, BOOK, SIGN.")
                        metadata_json["text_log_format"] = normalized_format
                else:
                    # Clean up readable fields
                    metadata_json.pop("text_log_content", None)
                    metadata_json.pop("text_log_format", None)

                if payload.wearable_slots is not None:
                    ent.wearable_slots = payload.wearable_slots
                    flag_modified(ent, "wearable_slots")
                if payload.combination_ingredients is not None:
                    ent.combination_ingredients = payload.combination_ingredients
                    flag_modified(ent, "combination_ingredients")
                if payload.stat_modifier_strength is not None:
                    ent.stat_modifier_strength = payload.stat_modifier_strength

                # COMBINABLE-specific metadata columns. Applied regardless of
                # current item_type so the field can be edited (or cleared) before
                # the user switches type — the value is dropped on type change if
                # it becomes irrelevant.
                if payload.reveal_rule is not None:
                    normalized = str(payload.reveal_rule or "").strip()
                    ent.reveal_rule = normalized[:500] if normalized else None
                if payload.is_hidden is not None:
                    ent.is_hidden = bool(payload.is_hidden)
                if payload.spatial_position is not None:
                    normalized = str(payload.spatial_position or "").strip()
                    ent.spatial_position = normalized[:255] if normalized else None
                if payload.reveals_item_id is not None:
                    normalized = str(payload.reveals_item_id or "").strip().upper()
                    ent.reveals_item_id = normalized or None
                
                # 3. Switch logic (only for SWITCH items)
                if is_switch_object:
                    if payload.switch_states is not None or payload.switch_initial_state is not None or payload.switch_transitions is not None:
                        switch_config = metadata_json.get("switch")
                        if not isinstance(switch_config, dict):
                            switch_config = {}
                        if payload.switch_states is not None:
                            switch_config["states"] = payload.switch_states
                        if payload.switch_initial_state is not None:
                            switch_config["initial_state"] = payload.switch_initial_state
                        if payload.switch_transitions is not None:
                            switch_config["transitions"] = payload.switch_transitions
                        metadata_json["switch"] = switch_config
                    
                    # Clean up flat switch keys that were previously written as pollution
                    metadata_json.pop("switch_states", None)
                    metadata_json.pop("switch_initial_state", None)
                    metadata_json.pop("switch_transitions", None)
                else:
                    # Clean up switch config
                    metadata_json.pop("switch", None)
                    metadata_json.pop("switch_states", None)
                    metadata_json.pop("switch_initial_state", None)
                    metadata_json.pop("switch_transitions", None)

                # 4. Consumable effects (only for CONSUMABLE items)
                if is_consumable_object:
                    if payload.effects is not None:
                        metadata_json["effects"] = payload.effects
                else:
                    metadata_json.pop("effects", None)

                ent.metadata_json = metadata_json
                flag_modified(ent, "metadata_json")

                if ent.item_type == "CONSTRUCTABLE":
                    ent.is_hidden = True
                    ent.reveal_rule = None
                else:
                    if payload.is_hidden is not None:
                        ent.is_hidden = bool(payload.is_hidden)
                    elif new_item_type_value is not None:
                        ent.is_hidden = False
                    
                    if payload.reveal_rule is not None:
                        ent.reveal_rule = str(payload.reveal_rule or "").strip() or None
            
    await db.commit()
    return {"status": "success"}


@router.patch("/{template_id}/editor/start-scene")
async def update_editor_start_scene(
    template_id: str,
    payload: StartSceneUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")

    scene_id = str(payload.scene_id or "").strip()
    if not scene_id:
        raise HTTPException(status_code=400, detail="scene_id is required")

    sc_res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
            WorldScene.id == scene_id,
        )
    )
    scene = sc_res.scalars().first()
    if not scene:
        raise HTTPException(status_code=400, detail="scene_id does not exist in this adventure")

    manifest = deepcopy(adv.original_manifest or {})
    manifest["start_scene_id"] = scene_id
    adv.original_manifest = manifest

    await db.commit()
    return {"status": "success", "start_scene_id": scene_id}

@router.post("/{template_id}/editor/generate-traits", response_model=TraitGenerationResponse)
async def generate_entity_traits(
    template_id: str,
    payload: TraitGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates NPC/Protagonist goal and character traits based on description/bio."""
    # Verify ownership
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")

    llm_settings = current_user.llm_settings or {}
    provider = llm_settings.get("small_model_provider") or "openai"
    model = llm_settings.get("small_model") or "gpt-4o-mini"
    
    gm = GameMasterLLM(user=current_user, provider=provider, model_category="small")
    
    field_instruction = ""
    if payload.target_field == "goal":
        field_instruction = "IMPORTANT: Focus specifically on generating a compelling Goal/Motivation."
    elif payload.target_field == "character":
        field_instruction = "IMPORTANT: Focus specifically on generating evocative Personality/Traits."

    base_prompt = TRAIT_GENERATION_USER_PROMPT_TEMPLATE.format(
        name=payload.name,
        description=payload.description,
        adventure_theme=payload.adventure_theme or adv.original_prompt or 'Fantasy Adventure'
    )
    user_prompt = f"{base_prompt}\n{field_instruction}"
    
    try:
        result = await gm.aexecute_complex_task(
            system_prompt=TRAIT_GENERATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=TraitGenerationResponse,
            model=model
        )
        return result
    except Exception as e:
        logger.error(f"Failed to generate traits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/editor/generate-quest-description", response_model=QuestDescriptionGenerationResponse)
async def generate_quest_description(
    template_id: str,
    payload: QuestDescriptionGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(AdventureTemplate).where(AdventureTemplate.id == template_id)
    res = await db.execute(stmt)
    adv = res.scalars().first()
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")

    llm_settings = current_user.llm_settings or {}
    provider = llm_settings.get("small_model_provider") or "openai"
    model = llm_settings.get("small_model") or "gpt-4o-mini"
    
    gm = GameMasterLLM(user=current_user, provider=provider, model_category="small")
    
    # Format other quests to prevent duplication
    other_quests_text = ""
    if payload.other_quests:
        lines = []
        for q in payload.other_quests:
            q_title = q.get("title") or "Unnamed Quest"
            q_desc = q.get("description") or "No description."
            q_type = "Main" if q.get("is_main") else "Side"
            lines.append(f"- [{q_type}] {q_title}: {q_desc}")
        other_quests_text = "\n".join(lines)
    else:
        other_quests_text = "No other quests defined yet."

    user_prompt = QUEST_DESCRIPTION_GENERATION_USER_PROMPT_TEMPLATE.format(
        title=payload.title,
        quest_type="Main" if payload.is_main else "Side",
        adventure_title=adv.title or "Untitled Adventure",
        adventure_plot=adv.plot or adv.original_prompt or "No description provided.",
        adventure_tone=adv.selected_tone or "Standard",
        other_quests_text=other_quests_text,
    )
    
    try:
        result = await gm.aexecute_complex_task(
            system_prompt=QUEST_DESCRIPTION_GENERATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=QuestDescriptionGenerationResponse,
            model=model
        )
        return result
    except Exception as e:
        logger.error(f"Failed to generate quest description: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/editor/generate-new-quest", response_model=QuestGenerationResponse)
async def generate_new_quest(
    template_id: str,
    payload: QuestGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(AdventureTemplate).where(AdventureTemplate.id == template_id)
    res = await db.execute(stmt)
    adv = res.scalars().first()
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")

    llm_settings = current_user.llm_settings or {}
    provider = llm_settings.get("small_model_provider") or "openai"
    model = llm_settings.get("small_model") or "gpt-4o-mini"
    
    gm = GameMasterLLM(user=current_user, provider=provider, model_category="small")
    
    # Format other quests to prevent duplication
    other_quests_text = ""
    if payload.other_quests:
        lines = []
        for q in payload.other_quests:
            q_title = q.get("title") or "Unnamed Quest"
            q_desc = q.get("description") or "No description."
            q_type = "Main" if q.get("is_main") else "Side"
            lines.append(f"- [{q_type}] {q_title}: {q_desc}")
        other_quests_text = "\n".join(lines)
    else:
        other_quests_text = "No other quests defined yet."

    user_prompt = QUEST_GENERATION_USER_PROMPT_TEMPLATE.format(
        quest_type="Main" if payload.is_main else "Side",
        adventure_title=adv.title or "Untitled Adventure",
        adventure_plot=adv.plot or adv.original_prompt or "No description provided.",
        adventure_tone=adv.selected_tone or "Standard",
        other_quests_text=other_quests_text,
    )
    
    try:
        result = await gm.aexecute_complex_task(
            system_prompt=QUEST_GENERATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=QuestGenerationResponse,
            model=model
        )
        return result
    except Exception as e:
        logger.error(f"Failed to generate new quest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/editor/generate-biography", response_model=BiographyGenerationResponse)
async def generate_entity_biography(
    template_id: str,
    payload: BiographyGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates NPC/Protagonist description/biography based on name, goal, and character traits."""
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")

    llm_settings = current_user.llm_settings or {}
    provider = llm_settings.get("small_model_provider") or "openai"
    model = llm_settings.get("small_model") or "gpt-4o-mini"

    gm = GameMasterLLM(user=current_user, provider=provider, model_category="small")

    system_prompt = BIOGRAPHY_GENERATION_SYSTEM_PROMPT

    theme = payload.adventure_theme or adv.original_prompt or 'Fantasy Adventure'
    user_prompt = BIOGRAPHY_GENERATION_USER_PROMPT_TEMPLATE.format(
        name=payload.name,
        goal=payload.goal,
        character=payload.character,
        theme=theme,
    )

    try:
        generated_text = await gm.aexecute_simple_task(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model
        )
        cleaned = generated_text.strip()
        if cleaned.startswith('"') and cleaned.endswith('"'):
            cleaned = cleaned[1:-1].strip()
        cleaned = cleaned[:1000]
        return BiographyGenerationResponse(description=cleaned)
    except Exception as e:
        logger.error(f"Failed to generate biography: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/editor/generate-scene-description", response_model=SceneDescriptionGenerationResponse)
async def generate_scene_description(
    template_id: str,
    payload: SceneDescriptionGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates a scene description based on scene name and adventure theme context."""
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")

    llm_settings = current_user.llm_settings or {}
    provider = llm_settings.get("small_model_provider") or "openai"
    model = llm_settings.get("small_model") or "gpt-4o-mini"

    gm = GameMasterLLM(user=current_user, provider=provider, model_category="small")

    system_prompt = SCENE_DESCRIPTION_GENERATION_SYSTEM_PROMPT

    theme = payload.adventure_theme or adv.original_prompt or 'Fantasy Adventure'
    user_prompt = SCENE_DESCRIPTION_GENERATION_USER_PROMPT_TEMPLATE.format(
        name=payload.name,
        theme=theme,
    )

    try:
        generated_text = await gm.aexecute_simple_task(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model
        )
        cleaned = generated_text.strip()
        if cleaned.startswith('"') and cleaned.endswith('"'):
            cleaned = cleaned[1:-1].strip()
        cleaned = cleaned[:1000]
        return SceneDescriptionGenerationResponse(description=cleaned)
    except Exception as e:
        logger.error(f"Failed to generate scene description: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/editor/generate-decorative-items", response_model=DecorativeItemsGenerationResponse)
async def generate_decorative_items(
    template_id: str,
    payload: DecorativeItemsGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates a list of decorative background details fitting a scene using the Simple LLM.

    The result is a JSON array of short noun-phrase strings (e.g. "metal table", "flickering torch").
    Existing items in `payload.existing_items` are excluded from the result and the total is capped
    so the merged list does not exceed 7 entries.
    """
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")

    existing = [str(item).strip() for item in (payload.existing_items or []) if str(item or "").strip()]
    existing_lower = {item.lower() for item in existing}
    max_new = max(0, 7 - len(existing))

    llm_settings = current_user.llm_settings or {}
    provider = llm_settings.get("small_model_provider") or "openai"
    model = llm_settings.get("small_model") or "gpt-4o-mini"

    gm = GameMasterLLM(user=current_user, provider=provider, model_category="small")

    system_prompt = DECORATIVE_ITEMS_GENERATION_SYSTEM_PROMPT

    theme = payload.adventure_theme or adv.original_prompt or "Fantasy Adventure"
    existing_block = "\n".join(f"- {item}" for item in existing) or "- (none)"

    user_prompt = DECORATIVE_ITEMS_GENERATION_USER_PROMPT_TEMPLATE.format(
        name=payload.name,
        theme=theme,
        description=payload.description or "(no description available)",
        existing_block=existing_block,
        max_new=max_new,
    )

    if max_new == 0:
        return DecorativeItemsGenerationResponse(items=[])

    try:
        generated_text = await gm.aexecute_simple_task(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model
        )
    except Exception as e:
        logger.error(f"Failed to generate decorative items: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    parsed_items: list[str] = []
    try:
        cleaned = generated_text.strip()
        # Strip optional code fences the model sometimes wraps the JSON in.
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        data = json.loads(cleaned)
        raw_items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(raw_items, list):
            raise ValueError("LLM response did not contain an 'items' array.")
        for raw in raw_items:
            if not isinstance(raw, str):
                continue
            value = raw.strip().rstrip(",.;:!?").strip().lower()
            if not value:
                continue
            if len(value) > 100:
                value = value[:100]
            if value in existing_lower:
                continue
            existing_lower.add(value)
            parsed_items.append(value)
            if len(parsed_items) >= max_new:
                break
    except Exception as e:
        logger.error(f"Failed to parse decorative items response: {e}; raw=%r", generated_text)
        raise HTTPException(status_code=500, detail="LLM returned an invalid response for decorative items.")

    return DecorativeItemsGenerationResponse(items=parsed_items)




