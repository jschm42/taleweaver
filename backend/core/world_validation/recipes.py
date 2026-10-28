"""CONSTRUCTABLE recipe checks: ingredients, results and kept ingredients."""

from __future__ import annotations

from typing import Any

from backend.core.world_validation.context import (
    ValidationContext,
    entity_field,
    entity_id,
    finding,
    item_type,
    ref_ids,
)
from backend.schemas.validation import ValidationFinding

MIN_INGREDIENTS = 2


def _clean_ids(raw: Any) -> list[str]:
    return [i.strip() for i in (raw or []) if isinstance(i, str) and i.strip()]


def _entity_finding(severity: str, code: str, eid: str, message: str, **extra: Any):
    return finding(severity, code, message, location=f"entity:{eid}", entity_id=eid, **extra)


def _ingredient_findings(
    ctx: ValidationContext, eid: str, ingredients: list[str]
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if len(ingredients) < MIN_INGREDIENTS:
        findings.append(
            _entity_finding(
                "error",
                "constructable_needs_ingredients",
                eid,
                f"CONSTRUCTABLE '{eid}' requires at least 2 combination_ingredients "
                f"(found {len(ingredients)}).",
                count=len(ingredients),
            )
        )
    elif len(set(ingredients)) != len(ingredients):
        findings.append(
            _entity_finding(
                "warn",
                "constructable_duplicate_ingredients",
                eid,
                f"CONSTRUCTABLE '{eid}' has duplicate ingredient ids.",
                ingredients=ingredients,
            )
        )
    findings.extend(
        _entity_finding(
            "error",
            "constructable_ingredient_missing",
            eid,
            f"CONSTRUCTABLE '{eid}' references unknown ingredient '{ref}'.",
            missing_ref=ref,
        )
        for ref in ingredients
        if ref not in ctx.object_ids
    )
    return findings


def _result_finding(
    ctx: ValidationContext, eid: str, ref: str, ingredients: list[str]
) -> ValidationFinding | None:
    if ref not in ctx.object_ids:
        return _entity_finding(
            "error",
            "constructable_result_missing",
            eid,
            f"CONSTRUCTABLE '{eid}' produces unknown item '{ref}'.",
            missing_ref=ref,
        )
    if item_type(ctx.entities_by_id.get(ref) or {}) == "CONSTRUCTABLE":
        return _entity_finding(
            "error",
            "constructable_result_is_recipe",
            eid,
            f"CONSTRUCTABLE '{eid}' produces '{ref}', which is a recipe itself. "
            "Results must be regular items.",
            result_id=ref,
        )
    if ref in ingredients:
        return _entity_finding(
            "error",
            "constructable_result_is_ingredient",
            eid,
            f"CONSTRUCTABLE '{eid}' lists '{ref}' as both ingredient and result.",
            result_id=ref,
        )
    if not ctx.entities_by_id[ref].get("is_hidden"):
        return _entity_finding(
            "warn",
            "constructable_result_not_hidden",
            eid,
            f"Result '{ref}' of CONSTRUCTABLE '{eid}' should start is_hidden=true "
            "(it is hidden automatically on import and revealed by crafting).",
            result_id=ref,
        )
    return None


def _result_findings(
    ctx: ValidationContext, eid: str, entity: dict[str, Any], ingredients: list[str]
) -> list[ValidationFinding]:
    results = _clean_ids(entity_field(entity, "result_item_ids"))
    if not results:
        return [
            _entity_finding(
                "error",
                "constructable_needs_result",
                eid,
                f"CONSTRUCTABLE '{eid}' is a recipe and needs at least one result_item_ids entry "
                "(the item(s) the crafting produces).",
            )
        ]
    found = (_result_finding(ctx, eid, ref, ingredients) for ref in dict.fromkeys(results))
    return [f for f in found if f is not None]


def _kept_findings(eid: str, entity: dict[str, Any], ingredients: list[str]):
    kept = _clean_ids(entity_field(entity, "kept_ingredients"))
    return [
        _entity_finding(
            "warn",
            "constructable_kept_not_ingredient",
            eid,
            f"CONSTRUCTABLE '{eid}' keeps '{ref}', which is not one of its ingredients.",
            missing_ref=ref,
        )
        for ref in kept
        if ref not in ingredients
    ]


def check_constructable_recipes(ctx: ValidationContext) -> list[ValidationFinding]:
    """CONSTRUCTABLE recipes turn >= 2 existing ingredients into >= 1 existing, hidden result."""
    findings: list[ValidationFinding] = []
    for entity in ctx.entities_of("OBJECT"):
        if item_type(entity) != "CONSTRUCTABLE":
            continue
        eid = entity_id(entity) or "?"
        ingredients = ref_ids(entity.get("combination_ingredients"))
        findings += _ingredient_findings(ctx, eid, _clean_ids(ingredients))
        findings += _result_findings(ctx, eid, entity, ingredients)
        findings += _kept_findings(eid, entity, ingredients)
    return findings
