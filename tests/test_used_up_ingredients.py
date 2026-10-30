"""Ingredients a crafting used up must never be rediscovered by the reveal logic."""

from types import SimpleNamespace

from backend.engine.rules.crafting_recipes import used_up_ingredient_ids


def _item(item_id, hidden=False):
    return SimpleNamespace(id=item_id, item_type="PICKABLE", is_hidden=hidden, metadata_json={})


def _recipe(ingredients, results, kept=()):
    return SimpleNamespace(
        id="RECIPE",
        item_type="CONSTRUCTABLE",
        is_hidden=True,
        combination_ingredients=list(ingredients),
        metadata_json={"result_item_ids": list(results), "kept_ingredients": list(kept)},
    )


def _hidden(ent):
    return bool(ent.is_hidden)


def test_ingredients_are_used_up_once_the_result_exists():
    # Arrange
    entities = [
        _item("BATTERIES", hidden=True),
        _item("BROKEN_REMOTE", hidden=True),
        _item("REMOTE", hidden=False),
        _recipe(["BATTERIES", "BROKEN_REMOTE"], ["REMOTE"]),
    ]

    # Act
    used_up = used_up_ingredient_ids(entities, _hidden)

    # Assert
    assert used_up == {"BATTERIES", "BROKEN_REMOTE"}


def test_nothing_is_used_up_before_crafting():
    # Arrange
    entities = [
        _item("BATTERIES", hidden=True),
        _item("BROKEN_REMOTE"),
        _item("REMOTE", hidden=True),
        _recipe(["BATTERIES", "BROKEN_REMOTE"], ["REMOTE"]),
    ]

    # Act
    used_up = used_up_ingredient_ids(entities, _hidden)

    # Assert
    assert used_up == set()


def test_kept_ingredients_are_not_used_up():
    # Arrange
    entities = [
        _item("SCREWDRIVER"),
        _item("PARTS", hidden=True),
        _item("RADIO"),
        _recipe(["SCREWDRIVER", "PARTS"], ["RADIO"], kept=["SCREWDRIVER"]),
    ]

    # Act
    used_up = used_up_ingredient_ids(entities, _hidden)

    # Assert
    assert used_up == {"PARTS"}
