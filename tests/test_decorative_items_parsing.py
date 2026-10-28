"""Parsing the model's answer for AI-generated decorative scene details."""

import pytest

from backend.api.routes.adventures.editing.generation import _parse_decorative_items


@pytest.mark.parametrize(
    "raw",
    [
        '{"items": ["Metal Table", "bookshelf."]}',
        # Seen from openai/gpt-6.1-sol: stray characters after the array.
        '{"items":["metal table","bookshelf"] "}"',
        '["metal table", "bookshelf"]',
        'Here you go: {"items": ["metal table", "bookshelf"]} hope this helps',
        '```json\n{"items": ["metal table", "bookshelf"]}\n```',
    ],
)
def test_parses_items_despite_malformed_wrapping(raw):
    # Act
    items = _parse_decorative_items(raw, set(), 7)

    # Assert
    assert items == ["metal table", "bookshelf"]


def test_skips_existing_items_and_caps_count():
    # Act
    items = _parse_decorative_items('{"items": ["rug", "lamp", "sofa", "clock"]}', {"rug"}, 2)

    # Assert
    assert items == ["lamp", "sofa"]


def test_answer_without_items_array_is_rejected():
    # Act / Assert
    with pytest.raises(ValueError):
        _parse_decorative_items("I cannot help with that.", set(), 7)
