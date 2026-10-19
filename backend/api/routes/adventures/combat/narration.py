"""LLM-driven combat flavor: aftermath narration and random special events."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

import backend.api.routes.adventures.gameplay_logic as gl
from backend.core.prompts import (
    COMBAT_SPECIAL_EVENT_SYSTEM_PROMPT,
    COMBAT_SPECIAL_EVENT_USER_PROMPT_TEMPLATE,
)
from backend.engine.rule_engine import GameOverException

logger = logging.getLogger(__name__)

SPECIAL_EVENT_CHANCE = 0.25
FALLBACK_SPECIAL_DAMAGE = 20


def _parse_json_candidate(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


class CombatNarrationMixin:
    """Aftermath narration and the occasional dramatic special event."""

    def _complex_llm(self) -> tuple[Any, str] | None:
        llm_settings = self.user.llm_settings or {}
        provider = (
            llm_settings.get("complex_model_provider")
            or llm_settings.get("small_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        model = llm_settings.get("complex_model") or "gpt-4o"
        try:
            return gl.GameMasterLLM(self.user, provider=provider, model_category="complex"), model
        except ValueError:
            return None

    async def _emit_combat_aftermath_narration(
        self, combat: dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        outcome = str(combat.get("outcome") or "").lower()
        if outcome not in {"victory", "escaped"}:
            return
        llm_info = self._complex_llm()
        if not llm_info:
            return
        llm, model = llm_info

        names = [e.get("name") for e in combat.get("enemies") or [] if e.get("engaged")]
        enemy_names = ", ".join(n for n in names if n) or (combat.get("enemy") or {}).get(
            "name", "the enemy"
        )
        prompt = (
            "You are the Game Master. Write a short aftermath narration after combat ends. "
            "Use 2-4 sentences, stay in-world, no mechanics, no bullet points, no command suggestions."
        )
        if self.turn_language:
            prompt += f" Respond only in {self.turn_language.upper()}."
        user_prompt = (
            f"Protagonist: {self.avatar.name}. Enemies: {enemy_names}. "
            f"Combat outcome: {outcome}. "
            f"Outcome note: {combat.get('status_note') or 'The combat has ended.'}. "
            "Narrate the immediate atmosphere and next beat from the Game Master's perspective."
        )

        yield f"event: status\ndata: {json.dumps({'content': 'Game Master reflects on the battle outcome...'})}\n\n"
        response_text = ""
        stream = await llm.stream_simple_task(prompt, user_prompt, model)
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                response_text += delta
                yield f"event: chunk\ndata: {json.dumps({'content': delta})}\n\n"

        response_text = response_text.strip()
        if not response_text:
            return
        await self._save_chat_message("assistant", response_text)
        # Only log when combat still exists, otherwise a cleared combat would be resurrected.
        if self._read_combat_state():
            self._append_combat_log(combat, response_text, "aftermath")
            self._set_combat_state(combat)

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any] | None:
        text = (raw or "").strip()
        if not text:
            return None
        data = _parse_json_candidate(text)
        if data is not None:
            return data
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.IGNORECASE | re.DOTALL)
        if fence:
            data = _parse_json_candidate(fence.group(1))
            if data is not None:
                return data
        obj_match = re.search(r"(\{.*\})", text, re.DOTALL)
        return _parse_json_candidate(obj_match.group(1)) if obj_match else None

    async def _request_llm_combat_special_event(
        self, combat: dict[str, Any]
    ) -> dict[str, Any] | None:
        llm_info = self._complex_llm()
        if not llm_info:
            return None
        llm, model = llm_info

        enemy = combat.get("enemy") or {}
        player = combat.get("player") or {}
        enemy_name = str(enemy.get("name") or "Enemy")
        enemy_hp = int(enemy.get("hp") or 0)
        player_hp = int(player.get("hp") or self.avatar.hp or 0)
        system_prompt = COMBAT_SPECIAL_EVENT_SYSTEM_PROMPT
        if self.turn_language:
            system_prompt += f" Text must be in {self.turn_language.upper()}."
        user_prompt = COMBAT_SPECIAL_EVENT_USER_PROMPT_TEMPLATE.format(
            round=int(combat.get("round") or 1),
            enemy_name=enemy_name,
            enemy_hp=enemy_hp,
            enemy_max_hp=int(enemy.get("max_hp") or max(enemy_hp, 1)),
            player_name=str(player.get("name") or self.avatar.name or "Protagonist"),
            player_hp=player_hp,
            player_max_hp=int(player.get("max_hp") or self.avatar.max_hp or max(player_hp, 1)),
        )
        try:
            raw = await llm.aexecute_simple_task(
                system_prompt,
                user_prompt,
                model,
                adventure_id=self.state.template_id,
                game_id=self.game_id,
                operation="combat.special_event",
                phase="decision",
            )
        except Exception as exc:
            logger.warning("[Turn %s] Special-event LLM call failed: %s", self.game_id, exc)
            return None

        data = self._parse_json_object(raw) if isinstance(raw, str) else None
        mode = str((data or {}).get("mode") or "").strip().lower()
        if mode not in {"story", "special_attack"}:
            logger.warning("[Turn %s] Special-event LLM returned unusable payload", self.game_id)
            return None
        text = str(data.get("text") or "").strip()
        damage_raw = data.get("damage")
        damage = int(damage_raw) if isinstance(damage_raw, (int, float)) else 0
        if mode == "special_attack":
            return {
                "mode": mode,
                "damage": max(5, min(40, damage)),
                "text": text
                or f"Special Event: {enemy_name} unleashes a sudden devastating strike!",
            }
        return {
            "mode": mode,
            "damage": 0,
            "text": text
            or f"Special Event: {enemy_name} alters the tone of battle with a chilling presence.",
        }

    def _special_event_damage(self, combat: dict[str, Any], text: str, damage: int) -> str:
        self.avatar.hp = max(0, self.avatar.hp - damage)
        data = {
            "kind": "event",
            "actor": (combat.get("enemy") or {}).get("id"),
            "effects": [
                {"entity": "PLAYER", "name": self.avatar.name, "stat": "hp", "delta": -damage}
            ],
        }
        self._append_combat_log(combat, text, "special", data)
        if self.avatar.hp <= 0:
            raise GameOverException(f"{self.avatar.name} has fallen! Game Over.")
        return text

    async def _maybe_trigger_special_event(self, combat: dict[str, Any]) -> str | None:
        """At most once per round the GM may spice up the fight with a special event."""
        if combat.get("special_event_round") == combat.get("round"):
            return None
        if gl.random.random() > SPECIAL_EVENT_CHANCE:
            return None
        combat["special_event_round"] = combat.get("round")

        enemy_name = (combat.get("enemy") or {}).get("name", "Enemy")
        if not bool(getattr(self.adventure, "npcs_can_damage_protagonist", True)):
            text = f"Special Event: {enemy_name} shifts the pressure of battle, but no direct damage is dealt."
            self._append_combat_log(combat, text, "special")
            return text

        event_data = await self._request_llm_combat_special_event(combat)
        if not event_data:
            if gl.random.random() < 0.5:
                text = f"Special Event: {enemy_name} performs a special attack for {FALLBACK_SPECIAL_DAMAGE} damage!"
                return self._special_event_damage(combat, text, FALLBACK_SPECIAL_DAMAGE)
            event_data = {
                "mode": "story",
                "text": f"Special Event: {enemy_name} bends the battlefield mood to its advantage.",
            }

        if event_data.get("mode") == "special_attack":
            return self._special_event_damage(
                combat, str(event_data["text"]), int(event_data.get("damage") or 0)
            )
        text = str(event_data["text"])
        self._append_combat_log(combat, text, "special")
        return text
