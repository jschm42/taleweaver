# Combat sound effects

The combat dialog plays these files. Standard recordings are bundled with the repository (generated via Stable Audio Open and normalized with FFmpeg). To replace a sound, place your own recording with the same file name here. No code change is needed; reload the page.

## Rules for the files

- Format: MP3, same file name as the placeholder (lower case, `.mp3`).
- Keep them short: 0.2 – 1 s for hits and swings, up to about 3 s for the stings
  (`fight_start`, `victory`, `defeat`).
- Trim leading silence, otherwise the sound lags behind the animation.
- Normalise them to a similar loudness. The game scales each one with the player's audio
  volume (in-game settings) and mutes them together with the background audio.
- Sounds marked *varied* are played at a slightly random pitch each time, so one recording
  does not sound repetitive.
- Only use recordings you have the right to distribute with the project.

A file that is missing or cannot be decoded is skipped silently.

## Files

| File | Plays when | Notes |
| --- | --- | --- |
| `fight_start.mp3` | The fight opens and the cards are dealt in | Sting |
| `round_start.mp3` | A new round begins (initiative banner) | |
| `player_turn.mp3` | "YOUR TURN" banner | Quiet cue |
| `dice_roll.mp3` | The d20 tumbles (attack and ability checks) | Varied, about 0.7 s |
| `swing_melee.mp3` | A melee attack is launched | Varied; whoosh |
| `shot_ranged.mp3` | A ranged attack is launched | Varied; bow or throw |
| `cast_magic.mp3` | A magic attack or magic ability is launched | Varied |
| `ability.mp3` | A social or other ability is used | |
| `hit_melee.mp3` | A melee attack deals damage | Varied |
| `hit_ranged.mp3` | A ranged attack deals damage | Varied |
| `hit_magic.mp3` | A magic attack, ability or Game Master event deals damage | Varied |
| `hit_crit.mp3` | A critical hit deals damage (replaces the normal hit) | Heavy impact |
| `miss.mp3` | An attack misses or an ability fails | Varied |
| `fumble.mp3` | A natural 1 | |
| `heal.mp3` | Someone regains HP | |
| `buff.mp3` | An attribute or armor class goes up | |
| `debuff.mp3` | An attribute or armor class goes down | |
| `consume.mp3` | The player uses a consumable | Potion, bite |
| `rest.mp3` | The player rests | Breath |
| `engage.mp3` | A bystander joins the fight | |
| `taunt.mp3` | An enemy speaks a banter line (speech bubble) | Quiet cue |
| `enemy_defeated.mp3` | A combatant is defeated and its card shatters | |
| `enemy_fled.mp3` | An enemy flees | |
| `escape_success.mp3` | The player escapes | |
| `escape_fail.mp3` | The player fails to escape | |
| `victory.mp3` | The fight is won | Sting |
| `defeat.mp3` | The player is defeated | Sting |

The list of sounds lives in `frontend/src/components/game/combat/combatSounds.ts`
(`COMBAT_SOUND_FILES`). `npm test` in `frontend/` checks that this folder, that list and this
table match.

## Recreating a placeholder

```bash
ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t 0.15 -b:a 32k <name>.mp3
```
