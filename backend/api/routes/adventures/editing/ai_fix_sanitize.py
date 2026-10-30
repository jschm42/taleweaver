"""Sanitizes raw LLM fix proposals into applicable ``FixProposal`` objects.

Drops patches for unsupported targets/fields and whole proposals whose values
exceed the editor's field length limits or carry scripts / guards with invalid
syntax, recording why so the user is told instead of seeing an unexplained
empty result.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, get_args

from backend.api.routes.adventures.editing.ai_fix_create import (
    creation_problems,
    is_allowed_create_field,
    is_create_type,
    limits_type,
)
from backend.api.routes.adventures.editing.ai_fix_limits import length_violations
from backend.api.routes.adventures.editing.ai_fix_scripts import script_violations
from backend.api.routes.adventures.editing.ai_fix_targets import is_allowed_field
from backend.schemas.validation import FixProposal, FixProposalEntityPatch, FixTargetType

_PATCH_TARGET_TYPES = frozenset(get_args(FixTargetType))
_MAX_REJECTED_LISTED = 5
_PROPOSAL_FIELDS = (
    "title",
    "summary",
    "rationale",
    "patches",
    "target_type",
    "target_id",
    "description",
    "field_updates",
    "note",
)
_DROPPED_MESSAGE = (
    "The AI proposed changes the editor cannot apply automatically ({rejected}). "
    "Try fixing it manually or request new suggestions."
)
_DROPPED_FALLBACK = "incomplete proposals without applicable patches"


def _as_dict(value: Any) -> Optional[dict[str, Any]]:
    """Normalize an LLM-returned proposal/patch (dict, pydantic model, or object) to a dict."""
    if value is None or isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
        except Exception:
            return None
        return dumped if isinstance(dumped, dict) else None
    collected = {f: getattr(value, f) for f in _PROPOSAL_FIELDS if hasattr(value, f)}
    return collected or None


def _object_item_types(summary: dict[str, Any]) -> dict[str, str]:
    """Object ``item_type`` keyed by upper-cased id and name (the AI may use either)."""
    item_types: dict[str, str] = {}
    for obj in summary.get("objects") or []:
        item_type = str(obj.get("item_type") or "").upper()
        for key in (obj.get("id"), obj.get("name")):
            item_types[str(key or "").strip().upper()] = item_type
    return item_types


@dataclass
class SanitizedProposals:
    proposals: list[FixProposal]
    rejected: list[str] = field(default_factory=list)

    def error_message(self) -> str:
        listed = ", ".join(self.rejected[:_MAX_REJECTED_LISTED]) or _DROPPED_FALLBACK
        return _DROPPED_MESSAGE.format(rejected=listed)


class _Sanitizer:
    def __init__(self, summary: dict[str, Any], allow_create: bool) -> None:
        self._summary = summary
        self._item_types = _object_item_types(summary)
        self._allow_create = allow_create
        self._create_failed = False
        self.rejected: list[str] = []

    def _reject(self, reasons: list[str]) -> None:
        self.rejected += [r for r in reasons if r not in self.rejected]

    def _value_violations(self, p_dict: dict[str, Any]) -> list[str]:
        target_type = str(p_dict.get("target_type") or "").strip()
        updates = p_dict.get("field_updates")
        if not isinstance(updates, dict):
            return []
        target_id = str(p_dict.get("target_id") or "").strip().upper()
        item_type = self._item_types.get(target_id) or updates.get("item_type")
        limit_type = limits_type(target_type)
        return length_violations(limit_type, updates, item_type) + script_violations(
            limit_type, updates
        )

    def _is_allowed(self, target_type: str, field_name: str) -> bool:
        if is_create_type(target_type):
            return is_allowed_create_field(target_type, field_name)
        return is_allowed_field(target_type, field_name)

    def _create_rejected(self, target_type: str, target_id: Any, updates: dict) -> bool:
        """True (and recorded) when a create patch is not allowed here or cannot be applied."""
        if not is_create_type(target_type):
            return False
        problems = (
            creation_problems(target_type, str(target_id or ""), updates, self._summary)
            if self._allow_create
            else [f"{target_type} (creating entities)"]
        )
        self._reject(problems)
        self._create_failed = self._create_failed or bool(problems)
        return bool(problems)

    def _clean_patch(self, p_dict: dict[str, Any]) -> Optional[FixProposalEntityPatch]:
        target_type = str(p_dict.get("target_type") or "").strip()
        field_updates = p_dict.get("field_updates") or {}
        if target_type not in _PATCH_TARGET_TYPES or not isinstance(field_updates, dict):
            self._reject([target_type or "?"])
            return None
        allowed = {str(k) for k in field_updates if self._is_allowed(target_type, str(k))}
        self._reject([f"{target_type}.{k}" for k in field_updates if k not in allowed])
        kept_updates = {str(k): v for k, v in field_updates.items() if k in allowed}
        target_id = p_dict.get("target_id")
        if self._create_rejected(target_type, target_id, kept_updates) or not kept_updates:
            return None
        return FixProposalEntityPatch(
            target_type=target_type,  # type: ignore[arg-type]
            target_id=str(target_id).strip() if target_id is not None else None,
            description=str(p_dict.get("description") or "").strip()[:280],
            field_updates=kept_updates,
        )

    def clean_proposal(self, raw: Any) -> Optional[FixProposal]:
        raw_dict = _as_dict(raw)
        if raw_dict is None:
            return None
        title = str(raw_dict.get("title") or "").strip()
        summary_text = str(raw_dict.get("summary") or "").strip()
        if not title or not summary_text:
            return None
        raw_patches = [d for d in (_as_dict(x) for x in raw_dict.get("patches") or []) if d]
        invalid = [v for d in raw_patches for v in self._value_violations(d)]
        if invalid:
            # A shortened or repaired value would change the fix's meaning, so drop the option.
            self._reject(invalid)
            return None
        self._create_failed = False
        patches = [p for p in (self._clean_patch(d) for d in raw_patches) if p]
        if not patches or self._create_failed:
            # Later patches may build on a creation, so a failed one drops the whole option.
            return None
        rationale = raw_dict.get("rationale")
        return FixProposal(
            title=title[:120],
            summary=summary_text[:600],
            rationale=(str(rationale).strip()[:400] if rationale else None),
            patches=patches,
        )


def sanitize_proposals(
    raw_proposals: list[Any], summary: dict[str, Any], allow_create: bool = False
) -> SanitizedProposals:
    """Clean raw LLM proposals against the allowlists and length limits of the world.

    ``allow_create`` admits ``new_npc`` / ``new_object`` patches (World-Builder only).
    """
    sanitizer = _Sanitizer(summary, allow_create)
    proposals = [p for p in (sanitizer.clean_proposal(raw) for raw in raw_proposals) if p]
    return SanitizedProposals(proposals=proposals, rejected=sanitizer.rejected)
