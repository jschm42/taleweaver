"""Capability probes for the admin model test (Administration -> Intelligence -> "Test capabilities").

The plain connection test only proves that a model answers. These probes check what each pass
actually needs, with small fixed scenarios and deterministic checks (no LLM judge):

* Pass 1 / Play-Agent / World-Builder: the real `MechanicsIntent` structured-output schema, exact
  entity IDs, an item handover written in German, and talk that must not move the player.
* Pass 2: a rule-violation narration in German that must keep a lock code secret.
* Pass 5: a summary that must keep the key facts.

The probes are a quick screen, not a benchmark: a pass means "worth a real playtest", a failure
means the model will likely break in play. See docs/model-selection.md.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass

from backend.core.llm_router import GameMasterLLM
from backend.core.model_speed_rating import speed_payload
from backend.core.openrouter_route_report import route_payload
from backend.core.prompts import GM_MECHANICS_SUFFIX
from backend.engine.interaction.llm_intents import MechanicsIntent


@dataclass
class CapabilityCheck:
    id: str
    label: str
    passed: bool
    detail: str = ""


# A tiny scene shared by all mechanics probes.
_SCENE_STATE = """CURRENT STATE
LOCATION: GATEHOUSE (Gatehouse) - a cold stone room at the castle gate.
EXITS: north -> COURTYARD (an iron-bound door, unlocked); east -> ARMORY (a barred door, LOCKED).
NPCS PRESENT: GUARD_MIRA (Mira, gate guard, visible, alive).
OBJECTS: OAK_CHEST (oak chest, CONTAINER, closed, unlocked), WALL_TORCH (torch, fixed to the wall).
INVENTORY (PLAYER): BRASS_KEY (brass key), BREAD (loaf of bread), ROPE (coil of rope).
LAST NARRATION (tail): Mira leans on her spear and eyes you. "Nobody passes without a reason."
"""
_KNOWN_IDS = {
    "GATEHOUSE",
    "COURTYARD",
    "ARMORY",
    "GUARD_MIRA",
    "OAK_CHEST",
    "WALL_TORCH",
    "BRASS_KEY",
    "BREAD",
    "ROPE",
    "PLAYER",
}
_MECHANICS_SYSTEM = (
    "You are the rules engine of a text adventure. Evaluate the player's message against the "
    "CURRENT STATE and return the requested JSON. Use only IDs from the CURRENT STATE.\n"
    + GM_MECHANICS_SUFFIX
)

_VAULT_DIAL_DIGITS = "4711"
_NARRATION_SYSTEM = (
    "You are the narrator of a text adventure. Write the next story passage (2-4 sentences) in "
    "German, in second person. Narrate exactly the TURN RESOLUTION. If it lists a rule "
    "violation, narrate the failure, never success. Never reveal lock codes or lock secrets."
)
_NARRATION_USER = (
    "TURN RESOLUTION\n"
    'Player: "Ich öffne die Tresortür."\n'
    "Outcome: FAILED. RULE VIOLATION: the vault door is locked with a combination lock "
    f"(code {_VAULT_DIAL_DIGITS}, SECRET - never mention it). The player does not know the code.\n"
    "Draft: The heavy vault door does not move; its dial stays cold under your fingers."
)
_GERMAN_MARKERS = {
    "die",
    "der",
    "das",
    "und",
    "nicht",
    "sich",
    "ist",
    "du",
    "dich",
    "dir",
    "deine",
    "ein",
    "eine",
}
_SUCCESS_MARKERS = ("schwingt auf", "öffnet sich", "geht auf", "springt auf")

_SUMMARY_SYSTEM = (
    "Summarize the story so far in at most 3 English sentences. Keep names, numbers and promises."
)
_SUMMARY_USER = (
    "Turn 1: The player meets the smuggler Tamsin Reed at the docks.\n"
    "Turn 2: Tamsin promises a boat passage for 17 silver coins.\n"
    "Turn 3: The player pays 10 coins and owes the remaining 7.\n"
    "Turn 4: Tamsin warns that the harbour master Oslo Venn is watching the pier.\n"
    "Turn 5: The player hides the coin purse under a loose plank in the warehouse."
)
_SUMMARY_FACTS = ("Tamsin", "17", "Venn")


def _ids_in(intent: MechanicsIntent) -> set[str]:
    """Every entity/scene ID the intent references."""
    data = intent.model_dump(exclude_none=True)
    found: set[str] = set()
    if data.get("new_scene_id"):
        found.add(str(data["new_scene_id"]))
    for item in data.get("given_items") or []:
        found.update({str(item.get("item_id")), str(item.get("npc_id"))})
    for update in data.get("updated_entities") or []:
        found.add(str(update.get("entity_id")))
    found.update(str(i) for i in data.get("removed_inventory_item_ids") or [])
    found.update(str(i) for i in data.get("discovered_entity_ids") or [])
    return found


def _unknown_ids(intent: MechanicsIntent) -> set[str]:
    return {i for i in _ids_in(intent) if i.upper() not in _KNOWN_IDS}


async def _mechanics(gm: GameMasterLLM, model: str, message: str) -> MechanicsIntent:
    user_prompt = f"{_SCENE_STATE}\nPLAYER MESSAGE: {message}"
    return await gm.aexecute_complex_task(
        _MECHANICS_SYSTEM,
        user_prompt,
        response_model=MechanicsIntent,
        model=model,
        operation="admin_capability_test",
        phase="mechanics",
    )


async def _probe_handover(gm: GameMasterLLM, model: str) -> list[CapabilityCheck]:
    intent = await _mechanics(gm, model, "Hier, Mira, nimm meinen Messingschlüssel.")
    pairs = {(g.item_id.upper(), g.npc_id.upper()) for g in intent.given_items or []}
    unknown = _unknown_ids(intent)
    return [
        CapabilityCheck("json_schema", "Returns valid JSON for the Pass 1 schema", True),
        CapabilityCheck(
            "handover",
            "Recognizes an item handover in plain German ('Hier, Mira, nimm meinen Messingschlüssel')",
            ("BRASS_KEY", "GUARD_MIRA") in pairs,
            f"given_items: {sorted(pairs) or 'none'}",
        ),
        CapabilityCheck(
            "exact_ids",
            "Uses only IDs from the state",
            not unknown,
            f"invented: {sorted(unknown)}" if unknown else "",
        ),
    ]


async def _probe_movement(gm: GameMasterLLM, model: str) -> list[CapabilityCheck]:
    intent = await _mechanics(gm, model, "I go through the iron-bound door to the north.")
    target = (intent.new_scene_id or "").upper()
    return [
        CapabilityCheck(
            "movement",
            "Moves the player through an open exit (new_scene_id COURTYARD)",
            target == "COURTYARD",
            f"new_scene_id: {intent.new_scene_id or 'none'}",
        )
    ]


async def _probe_talk(gm: GameMasterLLM, model: str) -> list[CapabilityCheck]:
    intent = await _mechanics(
        gm, model, "Mira, what is behind the north door? Would you let me pass?"
    )
    moved = bool(intent.new_scene_id) and intent.new_scene_id.upper() != "GATEHOUSE"
    gave = bool(intent.given_items)
    return [
        CapabilityCheck(
            "talk_not_action",
            "Treats a question as talk (no move, no handover)",
            not moved and not gave,
            f"new_scene_id: {intent.new_scene_id or 'none'}, given_items: {len(intent.given_items or [])}",
        )
    ]


async def _probe_narration(gm: GameMasterLLM, model: str) -> list[CapabilityCheck]:
    text = await gm.aexecute_simple_task(
        _NARRATION_SYSTEM, _NARRATION_USER, model=model, operation="admin_capability_test"
    )
    text = (text or "").strip()
    lower = text.lower()
    words = set(re.findall(r"[a-zäöüß]+", lower))
    german_hits = len(words & _GERMAN_MARKERS)
    success_said = next((m for m in _SUCCESS_MARKERS if m in lower), "")
    return [
        CapabilityCheck(
            "visible_text", "Returns visible text", bool(text), "" if text else "empty answer"
        ),
        CapabilityCheck(
            "keeps_secret",
            "Keeps the lock code secret",
            bool(text) and _VAULT_DIAL_DIGITS not in text,
            "the code appears in the narration" if _VAULT_DIAL_DIGITS in text else "",
        ),
        CapabilityCheck(
            "narrates_failure",
            "Narrates the failure, not success",
            bool(text) and not success_said,
            f'success phrase: "{success_said}"' if success_said else "",
        ),
        CapabilityCheck(
            "language",
            "Writes in the requested language (German)",
            german_hits >= 3,
            f"{german_hits} common German words found",
        ),
    ]


async def _probe_summary(gm: GameMasterLLM, model: str) -> list[CapabilityCheck]:
    text = await gm.aexecute_simple_task(
        _SUMMARY_SYSTEM, _SUMMARY_USER, model=model, operation="admin_capability_test"
    )
    missing = [fact for fact in _SUMMARY_FACTS if fact.lower() not in (text or "").lower()]
    return [
        CapabilityCheck("visible_text", "Returns visible text", bool((text or "").strip())),
        CapabilityCheck(
            "keeps_facts",
            "Keeps names and numbers in the summary",
            not missing,
            f"missing: {', '.join(missing)}" if missing else "",
        ),
    ]


Probe = Callable[[GameMasterLLM, str], Awaitable[list[CapabilityCheck]]]

_MECHANICS_PROBES: list[Probe] = [_probe_handover, _probe_movement, _probe_talk]
PASS_PROBES: dict[str, list[Probe]] = {
    "small": _MECHANICS_PROBES,
    "play_agent": [_probe_handover],
    "generator": [_probe_handover],
    "complex": [_probe_narration],
    "compression": [_probe_summary],
}


async def _run_probe(
    probe: Probe, gm: GameMasterLLM, model: str
) -> tuple[list[CapabilityCheck], float]:
    """Runs one probe and times it; a failed request or invalid JSON becomes a failed check."""
    start = time.perf_counter()
    try:
        return await probe(gm, model), time.perf_counter() - start
    except Exception as exc:  # noqa: BLE001 - every probe error is a test result, not a crash
        name = probe.__name__.removeprefix("_probe_")
        reason = str(exc).splitlines()[0][:200] if str(exc) else type(exc).__name__
        failed = CapabilityCheck(f"{name}_error", f"Probe '{name}' failed", False, reason)
        return [failed], time.perf_counter() - start


async def run_capability_probes(gm: GameMasterLLM, model: str, pass_key: str) -> dict:
    """Runs the probes of a pass in parallel and returns the admin test response."""
    probes = PASS_PROBES.get(pass_key, _MECHANICS_PROBES)
    results = await asyncio.gather(*(_run_probe(p, gm, model) for p in probes))
    checks = [check for group, _ in results for check in group]
    slowest = max(seconds for _, seconds in results)
    passed = sum(1 for check in checks if check.passed)
    status = "success" if passed == len(checks) else "error"
    speed = speed_payload(pass_key, slowest)
    return {
        "status": status,
        "message": f"{passed} of {len(checks)} capability checks passed. {speed['label']}.",
        "response_time": round(slowest, 2),
        "checks": [asdict(check) for check in checks],
        "speed": speed,
        "routing": route_payload(gm),
    }
