"""World-Builder blueprint syntax: parse, validate, prompt and merge.

See ``docs/world-builder-syntax.md`` for the user-facing reference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.engine.blueprint.merge import apply_blueprint
from backend.engine.blueprint.models import Blueprint, BlueprintBlock, BlueprintIssue
from backend.engine.blueprint.parser import has_blueprint_tags, parse_blueprint
from backend.engine.blueprint.prompt import blueprint_sequences, render_blueprint_prompt
from backend.engine.blueprint.validator import validate_blueprint


class BlueprintError(ValueError):
    """Raised when a blueprint has errors that would break generation."""

    def __init__(self, issues: list[BlueprintIssue]):
        self.issues = issues
        details = "; ".join(f"line {issue.line}: {issue.message}" for issue in issues)
        super().__init__(f"The Story Idea blueprint has errors: {details}")


@dataclass
class PreparedBlueprint:
    """Everything the world generator needs from a Story Idea text."""

    blueprint: Blueprint
    premise: str
    sequences: list[dict[str, Any]] = field(default_factory=list)
    missing_ids: list[str] = field(default_factory=list)

    def prompt_section(self, generation_strictness: str) -> str:
        return render_blueprint_prompt(self.blueprint, self.missing_ids, generation_strictness)


def analyze_blueprint(text: str) -> tuple[Blueprint, list[str]]:
    """Parse and validate ``text``. Returns the blueprint and undeclared referenced IDs."""
    blueprint = parse_blueprint(text)
    missing_ids = validate_blueprint(blueprint)
    return blueprint, missing_ids


def prepare_blueprint(text: str) -> PreparedBlueprint | None:
    """Return the prepared blueprint, or ``None`` when the text uses no tags at all."""
    if not has_blueprint_tags(text):
        return None
    blueprint, missing_ids = analyze_blueprint(text)
    if blueprint.errors:
        raise BlueprintError(blueprint.errors)
    return PreparedBlueprint(
        blueprint=blueprint,
        premise=blueprint.premise,
        sequences=blueprint_sequences(blueprint),
        missing_ids=missing_ids,
    )


__all__ = [
    "Blueprint",
    "BlueprintBlock",
    "BlueprintError",
    "BlueprintIssue",
    "PreparedBlueprint",
    "analyze_blueprint",
    "apply_blueprint",
    "has_blueprint_tags",
    "parse_blueprint",
    "prepare_blueprint",
]
