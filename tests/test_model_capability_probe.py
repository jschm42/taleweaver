"""Capability probes of the admin model test (backend/core/model_capability_probe.py)."""

import asyncio

from backend.core import model_capability_probe as probe
from backend.engine.interaction.llm_intents import MechanicsIntent


class _ScriptedGM:
    """Answers each probe like a capable (or, with `weak=True`, a weak) model."""

    def __init__(self, weak: bool = False) -> None:
        self.weak = weak

    async def aexecute_complex_task(self, system, user, response_model, model, **_):
        message = user.split("PLAYER MESSAGE:", 1)[1]
        if self.weak:
            return MechanicsIntent(new_scene_id="DUNGEON")
        if "Messingschl" in message:
            return MechanicsIntent(given_items=[{"item_id": "BRASS_KEY", "npc_id": "GUARD_MIRA"}])
        if "iron-bound" in message:
            return MechanicsIntent(new_scene_id="COURTYARD")
        return MechanicsIntent()

    async def aexecute_simple_task(self, system, user, model, **_):
        if "Summarize" in system:
            return (
                "Tamsin wants 17 coins."
                if self.weak
                else "Tamsin wants 17 coins; Oslo Venn watches."
            )
        if self.weak:
            return "The vault door swings open: the code was 4711."
        return "Die schwere Tür bewegt sich nicht, und du spürst, dass sie dir nicht nachgibt."


def _run(gm: _ScriptedGM, pass_key: str) -> dict:
    return asyncio.run(probe.run_capability_probes(gm, "test-model", pass_key))


def _failed(result: dict) -> set[str]:
    return {check["id"] for check in result["checks"] if not check["passed"]}


def test_capable_model_passes_every_pass():
    # Arrange / Act
    results = {key: _run(_ScriptedGM(), key) for key in probe.PASS_PROBES}

    # Assert
    for key, result in results.items():
        assert result["status"] == "success", (key, _failed(result))


def test_weak_mechanics_model_fails_handover_ids_and_talk():
    # Act
    result = _run(_ScriptedGM(weak=True), "small")

    # Assert
    assert result["status"] == "error"
    assert {"handover", "exact_ids", "movement", "talk_not_action"} <= _failed(result)


def test_weak_narration_leaks_secret_and_misses_language():
    # Act
    result = _run(_ScriptedGM(weak=True), "complex")

    # Assert
    assert {"keeps_secret", "language"} <= _failed(result)


def test_weak_summary_loses_facts():
    assert "keeps_facts" in _failed(_run(_ScriptedGM(weak=True), "compression"))


def test_request_error_becomes_failed_check():
    # Arrange
    class _Broken(_ScriptedGM):
        async def aexecute_complex_task(self, *args, **kwargs):
            raise ValueError("LLM returned JSON that does not match expected schema")

    # Act
    result = _run(_Broken(), "play_agent")

    # Assert
    assert result["status"] == "error"
    assert result["checks"][0]["id"] == "handover_error"
    assert "does not match" in result["checks"][0]["detail"]


def test_capability_result_carries_a_speed_rating():
    # Act
    result = _run(_ScriptedGM(), "small")

    # Assert
    assert result["speed"]["rating"] == "fast"
    assert "Speed: fast" in result["message"]


def test_speed_limits_depend_on_the_pass():
    # Arrange
    from backend.core.model_speed_rating import rate_speed

    # Act / Assert
    assert rate_speed("small", 1.5).rating == "fast"
    assert rate_speed("small", 4.0).rating == "ok"
    assert rate_speed("small", 6.0).rating == "slow"
    assert rate_speed("complex", 6.0).rating == "ok"
    assert rate_speed("generator", 15.0).rating == "ok"
    assert rate_speed("unknown-pass", 6.0).rating == "slow"
