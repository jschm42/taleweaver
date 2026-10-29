# Concept: Area-of-Effect (AoE) Abilities

> **Status:** Proposal, not implemented. Describes how special actions such as *Fireball* could hit
> several combatants in one turn. Nothing in this document is available in blueprints or the UI yet.

## 1. Goal

Today every special action resolves against **one** combatant: the caster (`self`) or the
selected enemy (`target`). In a multi-enemy encounter a *Fireball* should be able to hit
every enemy, and a *Cleave* should hit the target plus its neighbours. All of this
must stay deterministic, readable in the Battle Chronicle and animatable in the arena.

## 2. Data model

A special action gets one new, optional field: `target_scope`. Effects get an optional
`splash_amount` for secondary targets.

| Field | Values | Default | Meaning |
| --- | --- | --- | --- |
| `target_scope` | `SINGLE`, `SPLASH`, `ALL_ENEMIES` | `SINGLE` | Which combatants receive the `target` effects. |
| `splash_radius` | `1`-`2` | `1` | `SPLASH` only: neighbours before and after the primary target in the encounter order. |
| `hits_passive` | `true` / `false` | `false` | Whether passive encounter NPCs are hit too: attackable NPCs in the scene that are part of the encounter with `engaged: false` (PASSIVE tag on their card, no initiative roll). A hit passive NPC is engaged and joins the fight, exactly like attacking it directly does today (`_engage` in `player_actions.py`). |
| `save_stat` | `strength` ... `charisma` | none | Optional saving throw for every target (see 3.2). |
| effect `splash_amount` | amount expression | half of `amount` | `SPLASH` only: what secondary targets receive instead of `amount`. |

`self` effects are always applied exactly once, regardless of the scope.

```jsonc
{
  "id": "FIREBALL",
  "name": "Fireball",
  "category": "MAGIC",
  "cost_type": "mana",
  "cost": 12,
  "success_stat": "intelligence",
  "difficulty": 13,              // caster's spell DC for the saving throw
  "target_scope": "ALL_ENEMIES",
  "save_stat": "dexterity",
  "effects": [{ "target": "target", "stat": "hp", "amount": "-3d6" }]
}
```

### Blueprint syntax

Inside a `[Ability: ID]` block (World-Builder syntax), three new keys:

```text
[Ability: FIREBALL] Fireball
kind: ATTACK
category: MAGIC
cost: mana 12
dc: 13
damage: 3d6
area: all            # single | splash | all  (maps to target_scope)
save: dexterity      # optional saving throw
hit_passive: no      # optional, default no
```

`area: splash 1` sets `splash_radius`. The blueprint analyzer must reject `save` without `dc`
and `area` on abilities without `target` effects.

## 3. Resolution rules

### 3.1 Picking the targets

1. `SINGLE`: unchanged.
2. `SPLASH`: the selected target is the **primary** target. Secondary targets are the alive
   enemies up to `splash_radius` positions before and after it in the encounter order. The
   arena stack reorders cards when the target changes, so the hover preview (section 5) is
   what tells the player who gets hit.
3. `ALL_ENEMIES`: every engaged, alive enemy. With `hits_passive`, passive encounter NPCs too.

The cost is paid **once**. Targets that are defeated or fled are skipped.

### 3.2 Rolling

There are two modes, chosen by the presence of `save_stat`:

* **Attack roll (no `save_stat`)**: the caster rolls **one** d20 + modifier. That single total is
  compared against every target's own AC (or the ability's `dc`). One roll keeps the
  Chronicle short and makes a crit or a fumble affect the whole spell.
* **Saving throw (`save_stat` set)**: the spell always goes off. Every target rolls
  d20 + its `save_stat` modifier against the ability's `dc`. A failed save takes the full
  amount, a successful save takes **half** (rounded down). This is the classic *Fireball*
  behaviour and the recommended default for area spells.

A natural 20 on the caster's attack roll doubles target effects (as today). In save mode a
target's natural 1 counts as a failed save, a natural 20 as a success.

### 3.3 Balance guard rails

* An AoE should cost noticeably more than a single-target ability. Suggested rule of thumb:
  about 1.5x the cost of a single-target ability with the same dice.
* A server-side cap of `MAX_ENCOUNTER_ENEMIES` (6) targets already applies through the
  encounter size.
* Defeat checks (`_resolve_casualties`) already loop over all enemies, so several enemies
  falling in one turn need no new logic. Only the flee check needs to run per hit target
  instead of only for `data["target"]`.

## 4. Event and log format

`resolve_special_attack` returns a `targets` list in addition to the existing fields. The
existing `target` field stays as the primary target so old clients keep working.

```jsonc
{
  "kind": "special",
  "action_id": "FIREBALL",
  "scope": "ALL_ENEMIES",
  "actor": "PLAYER",
  "target": "GUARD_HARLAN",            // primary target (unchanged field)
  "targets": [
    { "id": "GUARD_HARLAN", "save": { "d20": 6, "total": 7, "dc": 13, "success": false } },
    { "id": "LYRA",         "save": { "d20": 17, "total": 20, "dc": 13, "success": true } }
  ],
  "effects": [
    { "entity": "GUARD_HARLAN", "stat": "hp", "delta": -11, "roll": "3d6 (4+3+4) = 11" },
    { "entity": "LYRA",         "stat": "hp", "delta": -5,  "roll": "half of 11" }
  ]
}
```

The Chronicle line lists the results compactly:

```text
Alex Vale casts Fireball (Mana -12). Guard Harlan fails the DEX save (7 vs DC 13): HP -11.
Lyra saves (20 vs DC 13): HP -5.
```

Damage is rolled **once** and shared by all targets (halved on a save), as with tabletop
fireballs. That keeps the numbers easy to follow.

## 5. Frontend

* **Ability card**: shows an `AoE` badge and the scope in the footer
  (`→ All enemies`, `→ Harlan + 1 each side`).
* **Targeting preview**: while the pointer is on an AoE card, the arena highlights every card
  that would be hit (primary target with the full glow, secondary targets with a weaker one).
  `ALL_ENEMIES` needs no selected target, so the card is usable even without one.
* **Animation** (`eventPlayer.ts`): one projectile to the enemy stack, then a burst
  effect over every hit card, then the per-target damage numbers from `effects`
  (already grouped per `entity`, so the existing float-text code can be reused).
* **Editor**: the special action editor gets an *Area* select (Single / Splash / All enemies),
  a *Radius* field for Splash and an optional *Saving throw* select.

## 6. NPC use

NPCs currently only fight the protagonist, so an NPC AoE would hit just one target. Until
companions or allies exist, NPC abilities with `target_scope` other than `SINGLE` are
resolved like `SINGLE`. The field is still stored, so adventures don't need changes later.

## 7. Implementation steps

1. `special_attacks.py`: normalize the new fields, add `select_targets(...)`, per-target
   saves and the `targets` list. Unit tests for each scope and both roll modes.
2. `player_actions.py`: pass the list of targets instead of a single one, engage hit
   passive NPCs, and run the flee check for each hit target.
3. Blueprint parser and analyzer: the `area`, `save` and `hit_passive` keys plus validation.
4. Frontend types (`NormalizedSpecialAttack.target_scope`), ability card badge, hover
   preview in `ArenaRenderer`, burst animation in `eventPlayer`.
5. Docs: `world-builder-syntax.md`, `world-builder-blueprint-manual.md` and the
   adventure creator skill, with a working *Fireball* example run through the analyzer.
