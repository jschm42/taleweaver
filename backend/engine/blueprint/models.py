"""Data structures produced by the blueprint parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

FieldMode = Literal["fixed", "hint"]
IssueSeverity = Literal["error", "warning"]


@dataclass
class BlueprintValue:
    """One parsed ``key: value`` line.

    ``fixed`` values are written back over the LLM output after generation,
    ``hint`` values (``key: ~value``) are only passed to the LLM as suggestions.
    """

    value: Any
    mode: FieldMode = "fixed"
    line: int = 0


@dataclass
class BlueprintBlock:
    """A single ``[Kind: REF] Name`` tag together with its body."""

    kind: str
    ref: str
    name: str
    line: int
    fields: dict[str, BlueprintValue] = field(default_factory=dict)
    open_fields: list[str] = field(default_factory=list)
    prose: list[str] = field(default_factory=list)
    children: list[BlueprintBlock] = field(default_factory=list)

    @property
    def description(self) -> str:
        return "\n".join(self.prose).strip()

    def fixed(self) -> dict[str, Any]:
        return {key: val.value for key, val in self.fields.items() if val.mode == "fixed"}

    def hints(self) -> dict[str, Any]:
        return {key: val.value for key, val in self.fields.items() if val.mode == "hint"}

    def child_blocks(self, kind: str) -> list[BlueprintBlock]:
        return [child for child in self.children if child.kind == kind]


@dataclass
class BlueprintIssue:
    line: int
    message: str
    severity: IssueSeverity = "error"

    def as_dict(self) -> dict[str, Any]:
        return {"line": self.line, "message": self.message, "severity": self.severity}


@dataclass
class Blueprint:
    """Parsed Story Idea: free premise text plus structured blocks."""

    premise: str = ""
    blocks: list[BlueprintBlock] = field(default_factory=list)
    issues: list[BlueprintIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[BlueprintIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[BlueprintIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def is_empty(self) -> bool:
        return not self.blocks

    def of_kind(self, kind: str) -> list[BlueprintBlock]:
        return [block for block in self.blocks if block.kind == kind]

    def first(self, kind: str) -> BlueprintBlock | None:
        matches = self.of_kind(kind)
        return matches[0] if matches else None

    def declared_ids(self) -> set[str]:
        """IDs declared by entity blocks (scenes, NPCs, items, quests, awards, scripts)."""
        id_kinds = {"scene", "npc", "item", "sidequest", "award", "script"}
        ids = {block.ref for block in self.blocks if block.kind in id_kinds and block.ref}
        for block in self.blocks:
            ids.update(child.ref for child in block.children if child.ref)
        return ids

    def add_issue(self, line: int, message: str, severity: IssueSeverity = "error") -> None:
        self.issues.append(BlueprintIssue(line=line, message=message, severity=severity))
