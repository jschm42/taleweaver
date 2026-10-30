"""CONSTRUCTABLE recipes: meta items that turn ingredients into separate result items.

A recipe is never a physical object. It lists ``combination_ingredients`` (>= 2), the
``result_item_ids`` it produces (any regular item type) and the ``kept_ingredients`` that
survive the crafting. The ingredient list is a column; results and kept ingredients live
in ``metadata_json``. Results start hidden and are revealed when the recipe is crafted.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

RECIPE_TYPE = "CONSTRUCTABLE"
RESULT_FIELD = "result_item_ids"
KEPT_FIELD = "kept_ingredients"


def normalize_ids(raw: Any) -> list[str]:
    """Upper-cased, de-duplicated ids in their original order."""
    if not isinstance(raw, (list, tuple)):
        return []
    ids: list[str] = []
    for value in raw:
        token = str(value or "").strip().upper()
        if token and token not in ids:
            ids.append(token)
    return ids


def is_recipe(entity: Any) -> bool:
    return str(getattr(entity, "item_type", "") or "").upper() == RECIPE_TYPE


def _metadata(entity: Any) -> dict[str, Any]:
    metadata = getattr(entity, "metadata_json", None)
    return metadata if isinstance(metadata, dict) else {}


def recipe_ingredients(entity: Any) -> set[str]:
    return set(normalize_ids(getattr(entity, "combination_ingredients", None)))


def recipe_results(entity: Any) -> list[str]:
    return normalize_ids(_metadata(entity).get(RESULT_FIELD))


def recipe_kept(entity: Any) -> set[str]:
    return set(normalize_ids(_metadata(entity).get(KEPT_FIELD))) & recipe_ingredients(entity)


def all_result_ids(entities: Iterable[Any]) -> set[str]:
    return {rid for ent in entities if is_recipe(ent) for rid in recipe_results(ent)}


def craft_only_result_ids(entities: Iterable[Any]) -> set[str]:
    """Results without a reveal path of their own; only crafting may produce them.

    A ``reveal_rule`` on the result or another item's ``reveals_item_id`` pointing at it
    is such a path, so those results may also appear by the regular reveal logic.
    """
    entities = list(entities)
    results = all_result_ids(entities)
    revealed_elsewhere = {
        str(ent.reveals_item_id).strip().upper()
        for ent in entities
        if getattr(ent, "reveals_item_id", None) and not is_recipe(ent)
    }
    with_rule = {
        str(ent.id).upper()
        for ent in entities
        if ent.id and str(getattr(ent, "reveal_rule", "") or "").strip()
    }
    return results - revealed_elsewhere - with_rule


def used_up_ingredient_ids(entities: Iterable[Any], is_hidden: Callable[[Any], bool]) -> set[str]:
    """Consumed ingredients of recipes that were already crafted (a result is out in the world).

    Crafting hides used-up scene ingredients; without this they look like undiscovered items
    and the reveal logic could bring them back when the narration mentions them.
    """
    entities = list(entities)
    by_id = {str(ent.id).upper(): ent for ent in entities if getattr(ent, "id", None)}
    used_up: set[str] = set()
    for recipe in (ent for ent in entities if is_recipe(ent)):
        results = [by_id.get(rid) for rid in recipe_results(recipe)]
        if not any(res is not None and not is_hidden(res) for res in results):
            continue
        used_up |= recipe_ingredients(recipe) - recipe_kept(recipe)
    return used_up
