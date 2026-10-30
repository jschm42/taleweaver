"""Prompts for the script editor's AI assistant (optimize / generate scripts and guards)."""

from backend.engine.world.world_scripting_prompt import TW_API_REFERENCE

# Editor context key -> when the code runs (or what it is).
SCRIPT_CONTEXTS: dict[str, str] = {
    "guard_expression": "a deterministic guard: ONE boolean expression that allows an action",
    "init_script": (
        "the adventure's init_script / a helpers_script: only `def` statements and constant "
        "assignments are loaded, every other statement never runs"
    ),
    "on_enter_scene": "runs when the protagonist enters the scene",
    "on_leave_scene": "runs when the protagonist leaves the scene",
    "on_interact": "runs when the protagonist examines, uses or talks to the entity",
    "on_pickup": "runs when the item is taken into the inventory",
    "on_drop": "runs when the item is dropped",
    "on_equip": "runs when the WEAPON/WEARABLE item is equipped",
    "on_unequip": "runs when the WEAPON/WEARABLE item is unequipped",
    "on_read": "runs when the READABLE item is read",
    "on_defeat": "runs when the NPC is defeated",
    "on_protagonist_enters_scene": "runs when the protagonist enters the NPC's scene",
    "on_open_exit": "runs when the exit is opened",
    "exit_used": "runs when the protagonist goes through the exit",
    "exit_unlock_success": "runs when the exit is unlocked",
    "exit_unlock_failure": "runs when unlocking the exit fails or its guard blocks it",
    "container_unlock_success": "runs when the container is unlocked",
    "container_unlock_failure": "runs when unlocking the container fails or its guard blocks it",
    "constructable_success": "runs when the recipe is crafted",
    "constructable_failure": "runs when crafting fails or its guard blocks it",
    "switch_success": "runs after a successful switch state change",
    "switch_failure": "runs after a failed switch state change",
    "transition_success": "runs after this switch transition succeeds",
    "transition_failure": "runs after this switch transition fails",
    "start_sequence": "runs when the chapter sequence starts",
    "end_sequence": "runs when the chapter sequence ends",
    "soft_rule": "runs when the GM reports the sequence soft rule's condition as fulfilled",
    "special_action": "runs after a special attack's success roll (`special` dict in scope)",
    "protagonist_hp_change": "runs when the protagonist's HP changes",
    "protagonist_status_change": "runs when the protagonist's status effects change",
}

_MODES = {
    "optimize": (
        "OPTIMIZE the author's code: fix errors and API misuse, simplify it, keep its "
        "behaviour and intent. Every comment that is a placeholder for missing logic (e.g. "
        "'# TODO: give the key', '# open the door here') must be REPLACED by working code. "
        "Keep explanatory comments. If an author hint is given, follow it."
    ),
    "generate": (
        "GENERATE code that does what the author's instruction asks. Build on the existing "
        "code: keep what still fits and change or extend it, unless the instruction asks for "
        "a rewrite."
    ),
}

SCRIPT_ASSIST_SYSTEM_PROMPT = (
    """You are the scripting assistant of TaleWeaver's adventure editor. You write sandboxed
Python for the `tw` scripting API.

SANDBOX RULES (code breaking them is rejected)
- Allowed: assignments, if/elif/else, for loops (with break/continue), def/return, lambda,
  inline `a if c else b`, f-strings, list/set/dict comprehensions and generator expressions.
- Not allowed: import, while, try/except, with, class, global, async, del.
- No names or attributes starting with "_" (no dunders).
- Builtins: abs, all, any, bool, dict, float, int, len, list, max, min, print, range, round,
  str, sum, tuple.
- Methods must be CALLED, never assigned: npc.add_trait("angry"), not npc.add_trait = "angry".
- A guard expression is ONE boolean expression (no statements, no tw.llm, no side effects).
- Keep scripts short and readable; use 4 spaces for indentation.
- Only use scene/NPC/object ids that exist in the world context, unless the author
  explicitly names a new one.
- Messages shown to the player (narrate, say, system texts) use the adventure language from
  the context (English when it is empty). Code, identifiers, `tw.vars` keys and comments are
  always English.

"""
    + TW_API_REFERENCE
    + """
OUTPUT
Return ONLY a JSON object: {"code": "<the complete new code>", "summary": "<1-3 sentences in
English on what you changed and why>"}. "code" is the FULL code for the editor, not a diff.
"""
)


def describe_context(context: str, label: str) -> str:
    """Human-readable description of where the edited code runs."""
    known = SCRIPT_CONTEXTS.get(context, "an event script")
    return f"{label or context}: {known}" if label else known


def mode_instructions(mode: str) -> str:
    return _MODES.get(mode, _MODES["optimize"])
