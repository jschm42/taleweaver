---
description: Gameplay guardrail rules - no language-keyword gating, server-side visibility authority, fail-safe behavior, and state-based Pass 1.5 enforcement over text parsing.
trigger: model_decision
paths:
  - "backend/api/routes/adventures/**/*.py"
  - "backend/engine/**/*.py"
---

# Gameplay Guardrails (Scene Visibility & Language-Agnostic Intents)

1. **No Language-Keyword Gating For Core Mechanics**:
   * Do **not** gate gameplay-critical decisions (inspect/search target validation, scene transition, generation confirmation/retry) behind hardcoded language keywords.
   * Prefer intent classification (LLM or parser abstraction) that works across languages and phrasing variants.
2. **Server-Side Visibility Authority**:
   * The backend is the final authority on what the GM can act on.
   * For inspect/search, only allow targets that are currently visible/accessible: current scene entities, protagonist inventory, and inventory of NPCs present in the current scene.
   * If a target is outside this scope, block the action before downstream GM/mechanics processing.
3. **Fail-Safe Behavior**:
   * If intent extraction is uncertain or unavailable, fall back to deterministic safeguards and prefer the safe outcome (no state-advancing side effects).
4. **State-Based Enforcement (Pass 1.5) Over Text Parsing**:
   * Do **not** pre-parse or guess which entity (container, switch, ...) the player interacts with by searching for its name/ID in the raw user message.
   * Inspect the state updates requested by the LLM in Pass 1 instead (e.g. `update.locked = False` for containers, `update.switch_state` for switches).
   * Validate them against the DB rules/gates (required items, codes, story flags) and the player's inventory/state. Revert illegal changes to their pre-turn state and pass the revert notices to the Pass 2 narration prompt as `rule_violations`, so the narration describes the failure.
5. **Verification**:
   * Changes to intent routing or visibility guard logic must pass targeted regression tests in `tests/test_game_loop.py` covering:
     * blocking off-scene inspect/search exploits,
     * not blocking unrelated mention-only text,
     * preserving hypothetical (non-explicit) scene-transition behavior,
     * preserving generator confirmation/retry behavior.
