"""NPC battle banter: a short in-character line at the end of every few rounds."""

from __future__ import annotations

import logging
from typing import Any

import backend.api.routes.adventures.gameplay_logic as gl
from backend.api.routes.adventures.combat.context import engaged_enemies

logger = logging.getLogger(__name__)

BANTER_MIN_GAP = 3
BANTER_MAX_GAP = 4
MAX_BANTER_CHARS = 160
PERSONALITY_KEYS = ("character", "personality", "goal")

BANTER_SYSTEM_PROMPT = (
    "You write a single line of battle banter for a fantasy RPG fight. Speak as the given NPC, "
    "in character, directly to the protagonist or about the fight. Comment on how the battle "
    "is going or mock the protagonist. At most 18 words, no quotation marks, no stage "
    "directions, no game mechanics or numbers."
)

# Used when no LLM is configured or the call fails, keyed by who is winning.
FALLBACK_LINES = {
    "winning": (
        "Is that all you have? I expected more.",
        "Kneel now and I might make it quick.",
        "You are already bleeding. This ends soon.",
    ),
    "losing": (
        "Lucky strikes. They will not save you.",
        "You think a few scratches frighten me?",
        "Enough games. Now I fight for real.",
    ),
    "even": (
        "Not bad. But not good enough.",
        "Keep dancing. You will tire before I do.",
        "Every swing you miss is a gift to me.",
    ),
}


def _hp_ratio(entry: dict[str, Any]) -> float:
    max_hp = int(entry.get("max_hp") or 0)
    return int(entry.get("hp") or 0) / max_hp if max_hp > 0 else 0.0


def battle_mood(speaker: dict[str, Any], player: dict[str, Any]) -> str:
    """Rough read of the fight from the speaker's side: winning, losing or even."""
    diff = _hp_ratio(speaker) - _hp_ratio(player)
    if diff > 0.2:
        return "winning"
    if diff < -0.2:
        return "losing"
    return "even"


def clean_banter_line(raw: str) -> str:
    line = " ".join((raw or "").split()).strip().strip("\"'“”„«»")
    if len(line) <= MAX_BANTER_CHARS:
        return line
    return line[: MAX_BANTER_CHARS - 1].rstrip() + "…"


class CombatBanterMixin:
    """Lets a random engaged NPC taunt the protagonist every 3-4 rounds."""

    @staticmethod
    def _schedule_next_banter(combat: dict[str, Any], after_round: int) -> None:
        gap = gl.random.randint(BANTER_MIN_GAP, BANTER_MAX_GAP)
        combat["next_banter_round"] = after_round + gap

    def _banter_due(self, combat: dict[str, Any]) -> bool:
        if "next_banter_round" not in combat:
            # The first line comes at the end of round 3 or 4.
            self._schedule_next_banter(combat, 0)
        return int(combat.get("round") or 1) >= int(combat["next_banter_round"])

    def _small_llm(self) -> tuple[Any, str] | None:
        llm_settings = self.user.llm_settings or {}
        provider = (
            llm_settings.get("small_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        model = llm_settings.get("small_model") or "gpt-4o-mini"
        try:
            return gl.GameMasterLLM(self.user, provider=provider, model_category="small"), model
        except ValueError:
            return None

    async def _speaker_profile(self, speaker: dict[str, Any]) -> str:
        npc = await self._load_session_entity(speaker["id"])
        if not npc:
            return ""
        meta = npc.metadata_json if isinstance(npc.metadata_json, dict) else {}
        traits = [str(meta[key]) for key in PERSONALITY_KEYS if meta.get(key)]
        if npc.description:
            traits.insert(0, str(npc.description))
        return " ".join(traits)[:600]

    async def _llm_banter_line(
        self, combat: dict[str, Any], speaker: dict[str, Any], mood: str
    ) -> str:
        llm_info = self._small_llm()
        if not llm_info:
            return ""
        llm, model = llm_info
        system_prompt = BANTER_SYSTEM_PROMPT
        if self.turn_language:
            system_prompt += f" Respond only in {self.turn_language.upper()}."
        recent = [e.get("text", "") for e in (combat.get("log") or [])[-4:]]
        user_prompt = (
            f"NPC: {speaker['name']}. Personality: {await self._speaker_profile(speaker) or 'unknown'}.\n"
            f"Protagonist: {self.avatar.name}. Round {combat.get('round', 1)}. "
            f"The NPC is currently {mood}.\n"
            "Recent events:\n- " + "\n- ".join(t for t in recent if t)
        )
        try:
            raw = await llm.aexecute_simple_task(
                system_prompt,
                user_prompt,
                model,
                adventure_id=self.state.template_id,
                game_id=self.game_id,
                operation="combat.banter",
                phase="narration",
            )
        except Exception as exc:
            logger.warning("[Turn %s] Combat banter LLM call failed: %s", self.game_id, exc)
            return ""
        return clean_banter_line(raw) if isinstance(raw, str) else ""

    async def _maybe_round_banter(self, combat: dict[str, Any]) -> None:
        """Called when a round ends; adds a banter log entry when one is due."""
        speakers = engaged_enemies(combat)
        if not combat.get("active") or not speakers or not self._banter_due(combat):
            return
        self._schedule_next_banter(combat, int(combat.get("round") or 1))
        speaker = gl.random.choice(speakers)
        mood = battle_mood(speaker, combat.get("player") or {})
        line = await self._llm_banter_line(combat, speaker, mood)
        line = line or gl.random.choice(FALLBACK_LINES[mood])
        self._append_combat_log(
            combat,
            f'{speaker["name"]}: "{line}"',
            "banter",
            {"kind": "banter", "actor": speaker["id"], "line": line},
        )
