# Area-of-Effect (AoE) Abilities

> **Status:** Implemented for protagonist special actions (engine, blueprint keys, editor, combat UI).
> Section 7 lists what is still open.

## 1. Goal

A normal special action resolves against **one** combatant: the caster (`self`) or the
selected enemy (`target`). In a multi-enemy encounter a *Fireball* can hit every enemy, and a
*Cleave* can hit the target plus its neighbours. Area attacks stay deterministic, readable in
the Battle Chronicle and animated in the arena.

## 2. Data model

Four optional fields on a special action (`SpecialActionSchema`, normalized in
`backend/engine/combat/special_attacks.py`):

| Field | Values | Default | Meaning |
| --- | --- | --- | --- |
| `target_scope` | `SINGLE`, `SPLASH`, `ALL_ENEMIES` | `SINGLE` | Which combatants receive the `target` effects. |
| `splash_radius` | `1`-`2` | `1` | `SPLASH` only: neighbours before and after the primary target in the encounter order. |
| `save_stat` | `strength` ... `charisma` | none | Optional saving throw for every target (see 3.2). |
| `spares_passive` | `true` / `false` | `false` | Leaves passive encounter NPCs out. By default an area attack also hits them: attackable NPCs in the scene that are part of the encounter with `engaged: false` (PASSIVE tag on their card, no initiative roll). A hit passive NPC is engaged and joins the fight, exactly like attacking it directly (`_engage` in `player_actions.py`). |

`self` effects are applied exactly once, and only when at least one target is affected.
An area scope only matters for abilities with at least one `target` effect.

```jsonc
{
  "id": "FIREBALL",
  "name": "Fireball",
  "category": "MAGIC",
  "cost_type": "mana",
  "cost": 12,
  "difficulty": 13,              // DC of the saving throw (default 12)
  "target_scope": "ALL_ENEMIES",
  "save_stat": "dexterity",
  "effects": [{ "target": "target", "stat": "hp", "amount": "-3d6" }]
}
```

### Blueprint syntax

Inside an `[Ability: ID]` block (World-Builder syntax, see `world-builder-syntax.md`):

```text
[Ability: FIREBALL] Fireball
kind: ATTACK
category: MAGIC
cost: mana 12
dc: 13
damage: 3d6
area: all            # single | splash | splash 2 | all  (target_scope + splash_radius)
save: dex            # optional saving throw (str, dex, int, wis, cha or the full name)
spare_passive: no    # optional, default no (passive NPCs are hit too)
```

## 3. Resolution rules (`backend/engine/combat/area_attacks.py`)

### 3.1 Picking the targets

1. `SINGLE`: the normal single-target path (`resolve_special_attack`).
2. `SPLASH`: the selected target is the **primary** target. Secondary targets are the alive
   enemies (passive ones included unless `spares_passive`) up to `splash_radius` positions
   before and after it in the encounter order.
   They receive **half** of every target effect.
3. `ALL_ENEMIES`: every alive enemy card in the stack, passive encounter NPCs included unless
   `spares_passive` is set.

The primary target always counts, even when it was passive. The cost is paid **once** and
every target effect amount is rolled **once**, then shared by all targets.

### 3.2 Rolling

Two modes, chosen by `save_stat`:

* **Attack roll (no `save_stat`)**: the caster rolls **one** d20 + `success_stat` modifier.
  That total is compared against every target's AC (or the ability's `difficulty`). A natural
  20 hits every target and doubles the effects, a natural 1 misses everyone.
* **Saving throw (`save_stat` set)**: the spell always goes off. Every target rolls
  d20 + its `save_stat` modifier against `difficulty` (default **12**). A failed save takes the
  full amount, a successful save takes **half** (rounded toward zero). A target's natural 20
  always saves, a natural 1 always fails.

### 3.3 Balance guard rails

* An AoE should cost noticeably more than a single-target ability. Rule of thumb: about
  1.5x the cost of a single-target ability with the same dice. The world-builder prompt asks
  the LLM to follow this.
* At most `MAX_ENCOUNTER_ENEMIES` (6) enemies can be in an encounter, which caps the targets.
* Defeat checks (`_resolve_casualties`) loop over all enemies, so several enemies can fall in
  one turn. The low-HP flee check only runs for the primary target.

## 4. Event and log format

The combat log entry's `data` contains the usual special-attack fields plus `scope`,
`save_stat` and a `targets` list. `target` stays the primary target.

```jsonc
{
  "kind": "special",
  "action_id": "FIREBALL",
  "scope": "ALL_ENEMIES",
  "save_stat": "dexterity",
  "actor": "PLAYER",
  "target": "GUARD_HARLAN",
  "targets": [
    { "id": "GUARD_HARLAN", "name": "Guard Harlan", "save": { "d20": 6, "modifier": 1, "total": 7, "dc": 13, "success": false } },
    { "id": "LYRA", "name": "Lyra", "save": { "d20": 17, "modifier": 3, "total": 20, "dc": 13, "success": true } }
  ],
  "effects": [
    { "entity": "GUARD_HARLAN", "stat": "hp", "delta": -11, "roll": "3d6 (4+3+4) = 11" },
    { "entity": "LYRA", "stat": "hp", "delta": -5, "roll": "3d6 (4+3+4) = 11" }
  ]
}
```

In attack-roll mode every `targets` entry has `hit` and `dc` instead of `save`. The Chronicle
line lists the results compactly:

```text
Alex Vale uses Fireball (Mana -12). Guard Harlan fails the Dexterity save (7 vs DC 13): Guard Harlan HP -11.
Lyra makes the Dexterity save (20 vs DC 13): Lyra HP -5.
```

## 5. Frontend

* **Editor** (`SpecialAttackForm.vue`, protagonist only): *Area* select (Single / Splash / All
  enemies), *Radius* for Splash, optional *Saving throw* and *Spare passive NPCs*. The
  *Fireball* preset is an all-enemies DEX-save attack.
* **Ability card**: type line `Magic — Area Attack`, the check (`DEX save vs DC 13`) and the
  scope in the footer (`→ All enemies`, `→ Harlan + 1 each side`).
* **Animation** (`eventPlayer.ts`): one projectile to every hit card at once, then the
  per-target damage numbers from `effects`, plus a `SAVED` / `MISS` label on targets that
  resisted.

## 6. NPC use

NPCs only fight the protagonist, so an NPC area attack would hit just one target. NPC
specials always resolve like `SINGLE`; the editor hides the area settings for NPCs and drops
them on save.

## 7. Open points

* **Hover preview**: highlight every card an AoE would hit while the pointer is on its card.
  The arena stack reorders cards when the target changes, so this preview is the best way to
  show which neighbours a splash reaches.
* **Per-target flee check**: run the low-HP flee roll for every hit target, not only the primary.
* **Custom splash share**: an optional per-effect `splash_amount` instead of the fixed half.
