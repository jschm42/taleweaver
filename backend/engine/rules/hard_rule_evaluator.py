"""
Deterministic hard rule evaluation service.

Evaluates structured hard conditions (required item, required scene,
required defeated NPC, and deterministic Python guard expressions)
across Sequences, Quests, and Awards.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.engine.scripting.context import GameContext
from backend.engine.switch_service import SwitchService
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState

logger = logging.getLogger(__name__)


@dataclass
class RuleEvaluationContext:
    """Evaluation context for hard rules, supporting direct test invocation."""

    current_scene_id: str = ""
    inventory_item_ids: set[str] = field(default_factory=set)
    defeated_npc_ids: set[str] = field(default_factory=set)
    active_sequence_id: str = ""
    custom_variables: dict[str, Any] = field(default_factory=dict)


class HardRuleEvaluator:
    """Evaluates deterministic item, scene, NPC defeat, and scripting guards."""

    @staticmethod
    def has_hard_rules(rule_dict: dict[str, Any] | Any) -> bool:
        """Returns True if any deterministic hard rule is configured."""
        if not rule_dict:
            return False
        getter = (
            rule_dict.get
            if isinstance(rule_dict, dict)
            else lambda k, d=None: getattr(rule_dict, k, d)
        )
        req_item = str(getter("required_item_id") or "").strip()
        req_scene = str(getter("required_scene_id") or "").strip()
        req_npc = str(getter("required_defeated_npc_id") or "").strip()
        req_guard = str(
            getter("guard_expression") or getter("completion_guard_expression") or ""
        ).strip()
        return bool(req_item or req_scene or req_npc or req_guard)

    @classmethod
    def check_item_rule(
        cls,
        required_item_id: str,
        avatar: Avatar,
        state: SessionState,
        new_inventory_items: Optional[list[Any]] = None,
    ) -> bool:
        """Checks if the protagonist has acquired the required item."""
        req_item = str(required_item_id or "").strip()
        if not req_item:
            return True

        req_item_norm = req_item.upper()
        inv_ids: set[str] = set()
        inv_names: set[str] = set()

        for item in getattr(avatar, "inventory", None) or []:
            if isinstance(item, dict):
                if item.get("id"):
                    inv_ids.add(str(item["id"]).strip().upper())
                if item.get("name"):
                    inv_names.add(str(item["name"]).strip().upper())
            elif isinstance(item, str) and item.strip():
                inv_ids.add(item.strip().upper())
            elif getattr(item, "id", None):
                inv_ids.add(str(item.id).strip().upper())
            elif getattr(item, "name", None):
                inv_names.add(str(item.name).strip().upper())

        for item in new_inventory_items or []:
            if isinstance(item, dict):
                if item.get("id"):
                    inv_ids.add(str(item["id"]).strip().upper())
                if item.get("name"):
                    inv_names.add(str(item["name"]).strip().upper())
            elif isinstance(item, str) and item.strip():
                inv_ids.add(item.strip().upper())
            elif getattr(item, "id", None):
                inv_ids.add(str(item.id).strip().upper())
            elif getattr(item, "name", None):
                inv_names.add(str(item.name).strip().upper())

        states = getattr(state, "entity_states", None) or {}
        in_inv_states = {
            str(eid).strip().upper()
            for eid, st in states.items()
            if isinstance(st, dict) and st.get("is_in_inventory")
        }

        return (
            req_item_norm in inv_ids or req_item_norm in inv_names or req_item_norm in in_inv_states
        )

    @classmethod
    def check_scene_rule(
        cls,
        required_scene_id: str,
        state: SessionState,
        new_scene_id: Optional[str] = None,
    ) -> bool:
        """Checks if the protagonist is currently in the required scene."""
        req_scene = str(required_scene_id or "").strip()
        if not req_scene:
            return True
        req_scene_norm = req_scene.upper()
        curr_scene = str(getattr(state, "current_scene_id", "") or "").strip().upper()
        new_scene = str(new_scene_id or "").strip().upper()
        return curr_scene == req_scene_norm or new_scene == req_scene_norm

    @classmethod
    def check_defeated_npc_rule(
        cls,
        required_defeated_npc_id: str,
        state: SessionState,
        updated_entities: Optional[list[Any]] = None,
    ) -> bool:
        """Checks if the required NPC has been defeated."""
        req_npc = str(required_defeated_npc_id or "").strip()
        if not req_npc:
            return True

        req_npc_norm = req_npc.upper()
        states = getattr(state, "entity_states", None) or {}
        npc_st = states.get(req_npc) or {}
        if not npc_st:
            for k, v in states.items():
                if str(k).strip().upper() == req_npc_norm and isinstance(v, dict):
                    npc_st = v
                    break

        if isinstance(npc_st, dict):
            if npc_st.get("is_defeated") is True:
                return True
            if npc_st.get("hp") is not None and npc_st.get("hp") <= 0:
                return True

        for upd in updated_entities or []:
            ent_id = (
                getattr(upd, "entity_id", None)
                if not isinstance(upd, dict)
                else upd.get("entity_id")
            )
            if str(ent_id or "").strip().upper() != req_npc_norm:
                continue
            upd_def = (
                getattr(upd, "is_defeated", None)
                if not isinstance(upd, dict)
                else upd.get("is_defeated")
            )
            upd_hp = getattr(upd, "hp", None) if not isinstance(upd, dict) else upd.get("hp")
            if upd_def is True or (upd_hp is not None and upd_hp <= 0):
                return True

        return False

    @classmethod
    def check_guard_expression(
        cls,
        guard_expression: str,
        avatar: Avatar,
        state: SessionState,
        script_context: Optional[Any] = None,
    ) -> tuple[bool, Optional[str]]:
        """Evaluates a deterministic Python boolean guard expression against GameContext."""
        expr = str(guard_expression or "").strip()
        if not expr:
            return True, None

        ctx = script_context
        if ctx is None:
            avatar_dict = {
                "name": getattr(avatar, "name", "Protagonist") or "Protagonist",
                "hp": getattr(avatar, "hp", 100) or 100,
                "mana": getattr(avatar, "mana", 100) or 100,
                "stamina": getattr(avatar, "stamina", 100) or 100,
                "inventory": list(getattr(avatar, "inventory", None) or []),
            }
            session_overrides = dict(getattr(state, "entity_states", None) or {})
            script_vars = dict(
                session_overrides.get("__script_vars__", {})
                or getattr(state, "custom_variables", None)
                or {}
            )
            story_flags = dict(session_overrides.get("__switch_story_flags__", {}))
            ctx = GameContext(
                avatar_data=avatar_dict,
                current_scene_id=str(getattr(state, "current_scene_id", "") or ""),
                entities={},
                exit_states=dict(getattr(state, "exit_states", None) or {}),
                quests=list(getattr(state, "quests", None) or []),
                script_vars=script_vars,
                in_game_time=getattr(state, "in_game_time", 0) or 0,
                story_flags=story_flags,
            )

        passed, reason = SwitchService.evaluate_gate_expression(expr, ctx)
        return bool(passed), reason

    @classmethod
    def evaluate_hard_rules(
        cls,
        rule_dict: dict[str, Any] | Any,
        avatar: Avatar,
        state: SessionState,
        new_inventory_items: Optional[list[Any]] = None,
        new_scene_id: Optional[str] = None,
        updated_entities: Optional[list[Any]] = None,
        script_context: Optional[Any] = None,
    ) -> tuple[bool, Optional[str]]:
        """Evaluates all configured hard rules. Returns (is_met, failure_reason)."""
        if not cls.has_hard_rules(rule_dict):
            return False, "No hard rules configured"

        getter = (
            rule_dict.get
            if isinstance(rule_dict, dict)
            else lambda k, d=None: getattr(rule_dict, k, d)
        )
        req_item = str(getter("required_item_id") or "").strip()
        req_scene = str(getter("required_scene_id") or "").strip()
        req_npc = str(getter("required_defeated_npc_id") or "").strip()
        req_guard = str(
            getter("guard_expression") or getter("completion_guard_expression") or ""
        ).strip()

        if req_item and not cls.check_item_rule(req_item, avatar, state, new_inventory_items):
            return False, f"Missing required item: {req_item}"

        if req_scene and not cls.check_scene_rule(req_scene, state, new_scene_id):
            return False, f"Not in required scene: {req_scene}"

        if req_npc and not cls.check_defeated_npc_rule(req_npc, state, updated_entities):
            return False, f"NPC not defeated: {req_npc}"

        if req_guard:
            passed, err = cls.check_guard_expression(req_guard, avatar, state, script_context)
            if not passed:
                return False, f"Guard expression unmet: {err or req_guard}"

        return True, None

    @classmethod
    def evaluate_target(
        cls,
        rule_dict: dict[str, Any] | Any,
        ctx: RuleEvaluationContext,
    ) -> bool:
        """Evaluates a rule dict or object against a RuleEvaluationContext."""
        getter = (
            rule_dict.get
            if isinstance(rule_dict, dict)
            else lambda k, d=None: getattr(rule_dict, k, d)
        )
        req_item = str(getter("required_item_id") or "").strip()
        if req_item:
            inv_upper = {str(i).upper() for i in ctx.inventory_item_ids}
            if req_item.upper() not in inv_upper:
                return False

        req_scene = str(getter("required_scene_id") or "").strip()
        if req_scene and req_scene.upper() != str(ctx.current_scene_id).upper():
            return False

        req_npc = str(getter("required_defeated_npc_id") or "").strip()
        if req_npc:
            defeated_upper = {str(n).upper() for n in ctx.defeated_npc_ids}
            if req_npc.upper() not in defeated_upper:
                return False

        req_guard = str(
            getter("guard_expression") or getter("completion_guard_expression") or ""
        ).strip()
        if req_guard:
            from backend.engine.scripting.context import GameContext

            game_ctx = GameContext(
                avatar_data={
                    "hp": 100,
                    "max_hp": 100,
                    "inventory": [
                        {"id": item_id, "name": item_id} for item_id in ctx.inventory_item_ids
                    ],
                },
                current_scene_id=ctx.current_scene_id,
                script_vars=dict(ctx.custom_variables),
            )
            passed, _ = SwitchService.evaluate_gate_expression(req_guard, game_ctx)
            if not passed:
                return False

        return True

    @classmethod
    def is_rule_satisfied(
        cls,
        rule_dict: dict[str, Any] | Any,
        ctx: RuleEvaluationContext,
    ) -> bool:
        """Alias for evaluate_target."""
        return cls.evaluate_target(rule_dict, ctx)
