"""Sequence-scoped soft rules: narrative conditions judged by the GM, effects run by the engine.

A soft rule pairs a natural-language ``condition`` (judged by Pass 1) with a deterministic
``script``. Only the rules of the active sequence are offered to the GM, which reports the
rules a player action fulfilled via ``GameEvent.triggered_soft_rule_ids``. Pass 1.5 then
validates each reported rule (sequence scope, trigger limit, ``guard_expression``) before
running its script, so the LLM never mutates game state directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

# Session-state key (inside ``entity_states``) holding how often each rule has fired.
SOFT_RULE_COUNTS_KEY = "__soft_rule_counts__"


@dataclass(frozen=True)
class SoftRule:
    id: str
    condition: str
    script: str = ""
    text: str = ""
    guard_expression: str = ""
    max_triggers: int | None = None

    @classmethod
    def from_dict(cls, raw: Any) -> SoftRule | None:
        if not isinstance(raw, dict):
            return None
        rule_id = str(raw.get("id") or "").strip()
        condition = str(raw.get("condition") or "").strip()
        if not rule_id or not condition:
            return None
        max_triggers = raw.get("max_triggers")
        return cls(
            id=rule_id,
            condition=condition,
            script=str(raw.get("script") or ""),
            text=str(raw.get("text") or "").strip(),
            guard_expression=str(raw.get("guard_expression") or "").strip(),
            max_triggers=int(max_triggers) if max_triggers else None,
        )


def sequence_soft_rules(sequence: dict[str, Any] | None) -> list[SoftRule]:
    """Returns the valid soft rules declared on a sequence, in declaration order."""
    if not isinstance(sequence, dict):
        return []
    rules = (SoftRule.from_dict(raw) for raw in sequence.get("soft_rules") or [])
    return [rule for rule in rules if rule is not None]


def fired_counts(entity_states: dict[str, Any] | None) -> dict[str, int]:
    counts = (entity_states or {}).get(SOFT_RULE_COUNTS_KEY)
    return dict(counts) if isinstance(counts, dict) else {}


def is_exhausted(rule: SoftRule, counts: dict[str, int]) -> bool:
    if rule.max_triggers is None:
        return False
    return counts.get(rule.id, 0) >= rule.max_triggers


def build_soft_rules_prompt_block(rules: list[SoftRule], counts: dict[str, int]) -> str:
    """Pass 1 prompt block listing the open rules; scripts and guards are never exposed."""
    open_rules = [
        {"id": rule.id, "condition": rule.condition}
        for rule in rules
        if not is_exhausted(rule, counts)
    ]
    if not open_rules:
        return ""
    return (
        "\n\nACTIVE SOFT RULES (CURRENT SEQUENCE):\n"
        "- If the player's action in THIS message clearly fulfills a rule's condition, add its "
        "exact `id` to `triggered_soft_rule_ids`.\n"
        "- Judge only what actually happens this message; never trigger a rule speculatively "
        "or because the player merely claims the outcome.\n"
        f"SOFT_RULES_JSON: {json.dumps(open_rules, ensure_ascii=False, separators=(',', ':'))}"
    )
