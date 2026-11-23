---
name: taleweaver-music-prompts
description: Generate music AI prompts (Suno, Stable Audio) for an adventure in the TaleWeaver database—on request for the main/title track, chapters (sequences), cutscenes, or individual scenes. Use when the user asks for Suno or Stable Audio prompts, soundtrack prompts, or music cues for an existing adventure.
---

# TaleWeaver Music AI Prompt Generator

Generates production-ready prompts for **Suno** and **Stable Audio** tailored to an adventure stored in the TaleWeaver database. Depending on what the user asks for, it produces prompts for:

- **Main / Title Track** (`title_track_id` — overarching adventure theme)
- **Chapters** (`sequences` — arc-level themes matching each chapter's stakes and pacing)
- **Cutscenes** (`cutscenes` — narrative cues timed to slide progression and dramatic beats)
- **Scenes** (`scenes` — ambient/environmental loops for individual locations, enriched by their region in `sections`)

All prompts are written strictly in **English** (music AI models perform best with English musical descriptors), regardless of the adventure's language.

---

## 1. Load the Adventure from the Database

1. Find the adventure ID or title if unknown:
   ```bash
   poetry run python scripts/inspect_state.py list-adventures
   ```
2. Export the full editor payload to your scratchpad (PowerShell: set `$env:PYTHONPATH="."` first):
   ```bash
   poetry run python scripts/edit_adventure.py export "<id or title>" --out <scratchpad>/adventure_export.json
   ```
   (Alternatively, `poetry run python scripts/inspect_state.py dump-manifest "<id or title>"` dumps the original manifest.)
3. Read the relevant sections from the exported JSON:
   - **Adventure meta** (`adventure`): `title`, `teaser`, `selected_tone`, `context`, `plot`, `rules`, `audio_tracks`, `title_track_id`, `world_sections` (`sections`).
   - **Chapters** (`sequences`): `id`, `order`, `title`, `description`, `end_condition`, `start_cutscene_id`, `on_start_sequence_text`, `on_end_sequence_text`.
   - **Cutscenes** (`cutscenes`): `id`, `title`, `audio_track_id`, `image_style`, `slides[].text`.
   - **Scenes** (`scenes`): `id`, `label`, `description`, `section_id`, `audio_track_id`, `decorative_objects`.

Check `audio_tracks` and existing `audio_track_id` / `title_track_id` assignments first so you know which tracks already exist and can maintain consistent instrumentation and motifs across the adventure.

---

## 2. Determine Targets & Music AI Format

Match what the user requested:
- **Targets**: `Main Track`, `Chapters`, `Cutscenes`, `Scenes`, or any combination.
  - If the user asks for "scenes" in a large adventure, either generate one prompt per requested scene or group scenes that share a mood/region (matching TaleWeaver's design where scenes sharing a track keep the music playing seamlessly across transitions).
  - Never invent scene/chapter/cutscene IDs—only generate for entries present in the adventure (or explicitly requested by the user).
- **Music AI provider**:
  - Generate **Suno**, **Stable Audio**, or **both** (default to **both** when the user does not specify one).

---

## 3. Prompt Crafting Rules

### Musical & Sonic Cohesion
- Establish a **sonic palette** from `selected_tone`, `context`, and `title` (e.g., 2-3 signature instruments or a harmonic motif) and reference variations of it across chapters, cutscenes, and scenes.
- **No copyrighted references**: never name real artists, composers, bands, songs, films, or games. Describe only genre, instrumentation, tempo (BPM), key/mode, dynamics, texture, and acoustics.
- **Instrumental by default**: background game audio should be instrumental without vocals/lyrics unless the user explicitly asks for a vocal track (e.g., a tavern song or lyrical main theme).

### Suno Format
Provide:
1. **Mode**: `Instrumental` (toggle ON) unless vocals were requested.
2. **Style of Music** (compact comma-separated tags, <= 200 characters):
   - Genre / sub-genre, lead & backing instruments, tempo (`BPM`), key/mood, production/acoustics, loopability (`seamless loop, loopable`), and `instrumental` (e.g., `"dark fantasy orchestral, bowed cello, hurdy-gurdy, hammered dulcimer, 84 BPM, D minor, brooding, cavernous reverb, seamless loop, loopable, instrumental"`).
   - Explicitly include `seamless loop, loopable` on all repeating/background tracks so they avoid abrupt intros or fade-outs.
3. **Optional Custom Prompt / Structure** (when vocals or dynamic progression are requested):
   - Use bracketed section tags (`[Intro]`, `[Build]`, `[Climax]`, `[Outro]`) or lyric verses if vocal.

### Stable Audio Format
Provide:
1. **Prompt** (2-3 crisp English sentences or rich descriptor phrases, max ~400 characters):
   - Genre, lead instruments, accompaniment, exact tempo in BPM, mood, and spatial acoustics.
   - **For loopable tracks** (scenes, chapters, ambient beds, and repeating main themes): explicitly instruct loopability and end with:
     `Seamless loop: no intro, no fade-out ending.`
   - **For strictly one-shot cues** (only when a non-looping cutscene is requested): describe the arc instead (e.g., `"Builds from sparse solo intro to dramatic climax and clean resolve."`).
2. **Suggested Duration**:
   - Scene / Chapter loop: `45s-90s`
   - Cutscene cue: `30s-60s`
   - Main / Title track: `120s-180s`
3. **Negative Prompt**:
   - e.g. `vocals, singing, speech, harsh distortion, abrupt cut, fade out` (omit `fade out` for non-looping cues that should resolve naturally).

---

## 4. Output Structure

Present the generated prompts cleanly in Markdown, grouped by the requested target types:

1. **Sonic Palette Summary** (brief: core instruments, harmonic feel, and tone derived from the adventure).
2. **Main / Title Track** (if requested) — include `title_track_id` context.
3. **Chapters (`sequences`)** (if requested) — list in `order`, showing `[SEQ_ID] Order. Title`.
4. **Cutscenes (`cutscenes`)** (if requested) — show `[CUTSCENE_ID] Title` and summarize the slide arc.
5. **Scenes (`scenes`)** (if requested) — show `[SCENE_ID] Label (Region)` and current `audio_track_id` if any.

For each entry, provide copy-pasteable **Suno** and **Stable Audio** blocks.
If the user wants to store the prompts as `audio_tracks` entries in TaleWeaver (or assign `title_track_id` / `audio_track_id`), offer to save them via the Adventure Editor Audio API or `AdventureTemplate.audio_tracks`.
