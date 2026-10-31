"""Applies an agent-written change set to an adventure template through the editor endpoints.

Every operation runs the same endpoint code as the Adventure Editor (field checks, manifest
sync, renames), all inside one transaction: a ``DeferredCommitSession`` turns the endpoints'
commits into flushes, so the caller decides at the end whether to commit or roll back.
Structural validation runs before and after, and only the findings the change set
introduced are reported.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.ai_fix_scripts import script_violations
from backend.api.routes.adventures.editing.entity_update.routes import update_editor_entity
from backend.api.routes.adventures.editing.payload import _build_adventure_editor_assets
from backend.api.routes.adventures.editing.schemas import (
    AwardCreateRequest,
    EntityCreateRequest,
    EntityUpdateRequest,
    ExitCreateRequest,
    QuestCreateRequest,
    SceneCreateRequest,
    ScriptCreateRequest,
    StartSceneUpdateRequest,
)
from backend.api.routes.adventures.editing.story_crud import (
    create_editor_award,
    create_editor_quest,
    delete_editor_award,
    delete_editor_quest,
    delete_editor_script,
    save_editor_script,
)
from backend.api.routes.adventures.editing.validation import _finding_signature
from backend.api.routes.adventures.editing.world_crud import (
    create_editor_entity,
    create_editor_exit,
    create_editor_scene,
    delete_editor_entity,
    delete_editor_exit,
    delete_editor_scene,
    update_editor_start_scene,
)
from backend.api.routes.adventures.schemas import AdventureTemplateUpdate
from backend.api.routes.adventures.templates import update_adventure
from backend.core.world_validator import validate_adventure
from backend.engine.scripting.sandbox import SafeAstInterpreter
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldExit
from backend.schemas.validation import ValidationFinding

MAX_OPERATIONS = 200
REF_PREFIX = "$"
_FILE_KEY = "$file"
_ROUTE_SEPARATOR = "->"


class ChangeSetError(Exception):
    """A change set operation was rejected; nothing of the change set is kept."""


class DeferredCommitSession(AsyncSession):
    """Session whose ``commit()`` only flushes, so several endpoint calls form one transaction."""

    async def commit(self) -> None:
        await self.flush()

    async def commit_for_real(self) -> None:
        await AsyncSession.commit(self)


@dataclass
class ChangeSetResult:
    applied: list[str] = field(default_factory=list)
    refs: dict[str, str] = field(default_factory=dict)
    new_findings: list[ValidationFinding] = field(default_factory=list)

    @property
    def new_errors(self) -> list[ValidationFinding]:
        return [f for f in self.new_findings if f.severity == "error"]


@dataclass
class _OpContext:
    db: AsyncSession
    template_id: str
    user: User
    base_dir: Path
    refs: dict[str, str]

    async def resolve_exit(self, raw: str) -> str:
        """``$ref`` of an exit created earlier, ``FROM->TO`` route, or a plain exit id."""
        value = raw.strip()
        if value.startswith(REF_PREFIX):
            if value[1:] not in self.refs:
                raise ChangeSetError(f"Unknown reference '{value}'.")
            return self.refs[value[1:]]
        if _ROUTE_SEPARATOR not in value:
            return value
        from_id, to_id = (part.strip() for part in value.split(_ROUTE_SEPARATOR, 1))
        rows = await self.db.execute(
            select(WorldExit.id).where(
                WorldExit.template_id == self.template_id,
                WorldExit.session_id.is_(None),
                WorldExit.from_scene_id == from_id,
                WorldExit.to_scene_id == to_id,
            )
        )
        exit_ids = list(rows.scalars().all())
        if len(exit_ids) != 1:
            raise ChangeSetError(f"Route '{value}' matches {len(exit_ids)} exits, expected 1.")
        return exit_ids[0]


_Handler = Callable[[_OpContext, dict[str, Any]], Awaitable[str]]


def _build(model: type[BaseModel], fields: dict[str, Any]) -> Any:
    unknown = sorted(set(fields) - set(model.model_fields))
    if unknown:
        raise ChangeSetError(f"Unknown field(s) {unknown}; allowed: {sorted(model.model_fields)}")
    try:
        return model(**fields)
    except ValidationError as exc:
        raise ChangeSetError(str(exc)) from exc


def _check_script_syntax(op_name: str, fields: dict[str, Any]) -> None:
    violations = script_violations(op_name, fields)
    if violations:
        raise ChangeSetError(violations[0])


def _payload_op(model: type[BaseModel], endpoint: Callable[..., Awaitable[Any]]) -> _Handler:
    async def run(ctx: _OpContext, fields: dict[str, Any]) -> str:
        payload = _build(model, fields)
        await endpoint(ctx.template_id, payload, db=ctx.db, current_user=ctx.user)
        return _describe(fields)

    return run


def _delete_op(endpoint: Callable[..., Awaitable[Any]], key: str) -> _Handler:
    async def run(ctx: _OpContext, fields: dict[str, Any]) -> str:
        if set(fields) != {key}:
            raise ChangeSetError(f"Expected exactly the field '{key}'.")
        target = str(fields[key])
        if key == "exit_id":
            target = await ctx.resolve_exit(target)
        await endpoint(ctx.template_id, target, db=ctx.db, current_user=ctx.user)
        return target

    return run


async def _create_exit(ctx: _OpContext, fields: dict[str, Any]) -> str:
    ref = str(fields.pop("ref", "") or "").strip()
    payload = _build(ExitCreateRequest, fields)
    result = await create_editor_exit(ctx.template_id, payload, db=ctx.db, current_user=ctx.user)
    exit_id = result["exit"]["id"]
    if ref:
        ctx.refs[ref] = exit_id
    return f"{payload.from_scene_id}->{payload.to_scene_id} (id {exit_id})"


async def _update(ctx: _OpContext, fields: dict[str, Any]) -> str:
    if fields.get("target_type") == "exit":
        fields["target_id"] = await ctx.resolve_exit(str(fields.get("target_id") or ""))
    payload = _build(EntityUpdateRequest, fields)
    await update_editor_entity(ctx.template_id, payload, db=ctx.db, current_user=ctx.user)
    changed = sorted(k for k in fields if k not in ("target_type", "target_id"))
    return f"{payload.target_type} {payload.target_id}: {', '.join(changed)}"


async def _update_adventure(ctx: _OpContext, fields: dict[str, Any]) -> str:
    payload = _build(AdventureTemplateUpdate, fields)
    await update_adventure(ctx.template_id, payload, db=ctx.db, current_user=ctx.user)
    return ", ".join(sorted(fields))


def _init_script_op(append: bool) -> _Handler:
    async def run(ctx: _OpContext, fields: dict[str, Any]) -> str:
        if set(fields) != {"code"}:
            raise ChangeSetError("Expected exactly the field 'code'.")
        code = str(fields["code"] or "")
        errors = SafeAstInterpreter.check_syntax(code)
        if errors:
            raise ChangeSetError(f"init_script has invalid syntax ({errors[0]})")
        adv = await ctx.db.get(AdventureTemplate, ctx.template_id)
        current = str(adv.init_script or "").rstrip() if append else ""
        adv.init_script = f"{current}\n\n{code.strip()}" if current else code
        return f"{len(code.splitlines())} line(s)"

    return run


OPERATIONS: dict[str, _Handler] = {
    "create_scene": _payload_op(SceneCreateRequest, create_editor_scene),
    "create_exit": _create_exit,
    "create_entity": _payload_op(EntityCreateRequest, create_editor_entity),
    "update": _update,
    "set_script": _payload_op(ScriptCreateRequest, save_editor_script),
    "set_init_script": _init_script_op(append=False),
    "append_init_script": _init_script_op(append=True),
    "create_quest": _payload_op(QuestCreateRequest, create_editor_quest),
    "create_award": _payload_op(AwardCreateRequest, create_editor_award),
    "set_start_scene": _payload_op(StartSceneUpdateRequest, update_editor_start_scene),
    "update_adventure": _update_adventure,
    "delete_scene": _delete_op(delete_editor_scene, "scene_id"),
    "delete_exit": _delete_op(delete_editor_exit, "exit_id"),
    "delete_entity": _delete_op(delete_editor_entity, "entity_id"),
    "delete_script": _delete_op(delete_editor_script, "script_id"),
    "delete_quest": _delete_op(delete_editor_quest, "quest_id"),
    "delete_award": _delete_op(delete_editor_award, "award_key"),
}

# Pydantic request model per operation, for the CLI's field reference.
OPERATION_MODELS: dict[str, Optional[type[BaseModel]]] = {
    "create_scene": SceneCreateRequest,
    "create_exit": ExitCreateRequest,
    "create_entity": EntityCreateRequest,
    "update": EntityUpdateRequest,
    "set_script": ScriptCreateRequest,
    "create_quest": QuestCreateRequest,
    "create_award": AwardCreateRequest,
    "set_start_scene": StartSceneUpdateRequest,
    "update_adventure": AdventureTemplateUpdate,
}


def _describe(fields: dict[str, Any]) -> str:
    for key in ("entity_id", "scene_id", "id", "key"):
        if fields.get(key):
            return str(fields[key])
    return ", ".join(sorted(fields))


def _read_file(raw_path: Any, base_dir: Path) -> str:
    """Reads a ``{"$file": ...}`` value; only files inside the change set's folder are allowed."""
    root = base_dir.resolve()
    path = (root / str(raw_path)).resolve()
    if not path.is_relative_to(root):
        raise ChangeSetError(f"File '{raw_path}' lies outside the change set's folder.")
    if not path.is_file():
        raise ChangeSetError(f"File '{raw_path}' not found.")
    return path.read_text(encoding="utf-8")


def _resolve_files(value: Any, base_dir: Path) -> Any:
    if isinstance(value, dict) and set(value) == {_FILE_KEY}:
        return _read_file(value[_FILE_KEY], base_dir)
    if isinstance(value, dict):
        return {k: _resolve_files(v, base_dir) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_files(v, base_dir) for v in value]
    return value


async def structural_findings(db: AsyncSession, template_id: str) -> list[ValidationFinding]:
    return validate_adventure(await _build_adventure_editor_assets(template_id, db))


async def _run_operation(ctx: _OpContext, index: int, operation: Any) -> str:
    if not isinstance(operation, dict) or "op" not in operation:
        raise ChangeSetError(f"Operation #{index} needs an 'op' key.")
    fields = _resolve_files(dict(operation), ctx.base_dir)
    op_name = str(fields.pop("op"))
    handler = OPERATIONS.get(op_name)
    if handler is None:
        raise ChangeSetError(f"Operation #{index}: unknown op '{op_name}'.")
    _check_script_syntax(op_name, fields)
    try:
        summary = await handler(ctx, fields)
    except HTTPException as exc:
        raise ChangeSetError(f"Operation #{index} ({op_name}): {exc.detail}") from exc
    except ChangeSetError as exc:
        raise ChangeSetError(f"Operation #{index} ({op_name}): {exc}") from exc
    return f"{op_name}: {summary}"


async def apply_change_set(
    db: AsyncSession,
    template_id: str,
    operations: list[Any],
    base_dir: Path,
) -> ChangeSetResult:
    """Runs all operations as the adventure owner. Raises ``ChangeSetError``; never commits."""
    if not operations:
        raise ChangeSetError("The change set has no operations.")
    if len(operations) > MAX_OPERATIONS:
        raise ChangeSetError(f"At most {MAX_OPERATIONS} operations per change set.")
    adv = await db.get(AdventureTemplate, template_id)
    owner = await db.get(User, adv.owner_id) if adv and adv.owner_id else None
    if owner is None:
        raise ChangeSetError(f"Adventure '{template_id}' not found or it has no owner.")

    baseline = {_finding_signature(f) for f in await structural_findings(db, template_id)}
    ctx = _OpContext(db=db, template_id=template_id, user=owner, base_dir=base_dir, refs={})
    result = ChangeSetResult(refs=ctx.refs)
    for index, operation in enumerate(operations, start=1):
        result.applied.append(await _run_operation(ctx, index, operation))
    after = await structural_findings(db, template_id)
    result.new_findings = [f for f in after if _finding_signature(f) not in baseline]
    return result
