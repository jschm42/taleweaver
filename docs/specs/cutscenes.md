# Cut-scenes

Status: implemented.

A cut-scene is a short slide show shown over the whole play view: each slide is a picture and
one or two sentences the narrator says. It opens a chapter or marks a moment a script picks (a
reveal, a death, the ending).

---

## 1. Data

`AdventureTemplate.cutscenes` (JSON, migration `c7e9a1b3d5f8`), normalized by
`engine/cutscenes/library.py`:

```json
{"id": "INTRO", "title": "The Crimson Debt", "image_style": "comic book",
 "audio_track_id": "DREAD_THEME",
 "slides": [{"id": "a1b2c3d4", "passages": ["The village burns.", "Nobody remembers why."],
             "image_url": "/data/adventures/library/<template>/visuals/cutscene/...png",
             "image_prompt": "a medieval village ringed by black fire at night"}]}
```

| Field | Meaning |
| --- | --- |
| `id` | Upper case, `A-Z 0-9 _`, max 40. Chapters and scripts name it. |
| `title` | Shown over the first slide; may be empty. |
| `image_style` | Overrides the adventure's image style for the slide images: a style catalog id or name, or a free description. Empty = the adventure's style. |
| `audio_track_id` | A track of the audio library; plays during the cut-scene instead of the scene audio. |
| `slides` | 1-12 slides. A slide without an image shows on the skin's veil. |
| `slides[].passages` | 1-6 text passages shown one after another over the slide's picture (e.g. a short exchange). A single `text` (LLM output, older data) becomes the first passage. |

At most 100 cut-scenes. Image URLs other than `/data/...` and `assets/...` are dropped.

A chapter (`sequence`) names its cut-scene in `start_cutscene_id`. The adventure names its
intro in `AdventureTemplate.intro_cutscene_id` (migration `d9f1b3c5e7a2`, shown right after a
new session starts) and its optional outcome cut-scenes in `win_cutscene_id` and
`game_over_cutscene_id` (migration `e1a2b3c4d5e6`, shown when the adventure is won or lost,
before the ending card). Only an id of the library is stored (`cutscene_ref_or_none`).

## 2. Showing a cut-scene

**Queue.** Cut-scenes wait in `entity_states["__cutscene__"] = {"queue": [{token, id}]}`
(`engine/cutscenes/queue.py`), so the queue is part of every checkpoint. At most 5 wait; a
cut-scene that is already waiting is not queued again.

**Sources.**

- A session starts: `session_starter._build_session_state` queues the adventure's
  `intro_cutscene_id` first, then the first chapter's `start_cutscene_id`, then the cut-scenes
  the init scripts queued.
- A chapter starts: `sequence_progress._advance_and_trigger`
  (linear advance) and the script/activation start path queue `start_cutscene_id` **first**,
  before the chapter's start hook runs, so a chapter intro plays before cut-scenes its start
  script queued.
- The adventure ends (`completed` or `game_over`): `gameplay_logic._finalize_session` queues
  `win_cutscene_id` or `game_over_cutscene_id`. On the client, `useGameProgressState` holds
  the terminal epilogue and ending card (`holdEnding`) until any lost-fight combat dialog and
  any queued cut-scene (`useCutscenePlayer.isBlocking`) have finished.
- `tw.cutscene.play(id)` (`engine/cutscenes/proxy.py`) records `ScriptChangeset.cutscene_ops`;
  every changeset applier (turn, `TriggerService`, session start) replays them with
  `apply_cutscene_ops`.

**Client.** The next queued cut-scene, resolved for playback (`client_cutscene`: slides without
author fields, the audio track's URL), is `cutscene` in `GET /chat` and in the pre-narration
`state` stream event, so it opens before the turn's narration. Unknown or empty cut-scenes are
skipped. After it ends or is skipped the client sends `POST /{game_id}/cutscene/seen {token}`
(`api/routes/adventures/cutscene_routes.py`), which removes it and returns the next one.
`useCutscenePlayer` remembers shown tokens, so a snapshot already on its way does not open it
again.

**Overlay** (`components/game/immersive/CutsceneOverlay.vue`, timing in
`composables/useCutsceneSlides.ts`):

- Full-view layer above the travel curtain, styled with the skin's `--tw-overlay-*` tokens; it
  carries its own `.tw-skin` / `data-skin`, because it is rendered outside the skinned root.
- The slide image drifts slowly (Ken Burns) and cross-fades to the next; the passages follow
  each other in a letterboxed caption; the title shows over the first slide; dots show the
  slide position.
- With auto-speech on, each passage is read aloud and stays until it was read (at least
  2.5 s). Without it a passage stays for a reading time based on its length (2.5-15 s).
- Holding Space or the mouse button for 0.6 s skips the current passage (after a slide's last
  passage: to the next slide; a ring shows the hold); Escape ends the whole cut-scene.
- While it is open, the turn's narration is not read (`speechDeferred` of `useGameAutoSpeak`);
  it is read once the cut-scene closed. A cut-scene with an audio track replaces the scene audio
  (`effectiveAudio`), which cross-fades back afterwards.

## 3. Editor

**Cut-scenes** page (Presentation group, `components/editor/pages/CutscenesPage.vue`): list,
then the selected cut-scene's form (`components/editor/cutscenes/`): title, ID, image style
(catalog names or free text), audio track, slides (text, image, order). One draft, saved with the
save bar (`PUT /editor/cutscenes {cutscenes, intro_cutscene_id, win_cutscene_id, game_over_cutscene_id}`). **Adventure intro**, **Victory**, and **Game over** above the
list pick the cut-scenes shown at session start, victory, and defeat; their tiles carry badges, and
renaming an id keeps those assignments. **Preview** plays it in the adventure's skin without speech.

Slide images (`CutsceneSlideImageModal.vue`): the prompt comes from the slide text
(`POST /editor/cutscenes/image-prompt`, `engine/cutscenes/images.py`) and can be edited;
**Draw image** (`POST /editor/cutscenes/image`, `quality`: `simple` = LQ model, `advanced` = HQ
model, default HQ) uses the cut-scene's style when set, else the adventure's, optionally with the
tone. While it draws, the dialog's controls are locked; **Cancel** stops waiting for the image
(the server may still finish and store the file, but it is not used); **Upload image** (`POST /editor/cutscenes/image/upload`)
stores the file under the adventure's `visuals/cutscene/`. The URL goes into the draft.

A chapter picks its cut-scene in the chapter dialog (Triggers tab, *Start cut-scene*).

Validation (`core/world_validation/cutscenes.py`): `intro_cutscene_missing`,
`win_cutscene_missing`, `game_over_cutscene_missing`, `chapter_cutscene_missing`,
`cutscene_without_slides`, `cutscene_audio_missing`, `script_cutscene_missing` (a literal
`tw.cutscene.play("ID")` with an unknown id).

## 4. World-Builder

- **Generation:** `WorldManifesto.cutscenes` (`engine/world/world_cutscene_schema.py`),
  `SequenceSchema.start_cutscene_id`, `WorldManifesto.intro_cutscene_id`,
  `WorldManifesto.win_cutscene_id`, and `WorldManifesto.game_over_cutscene_id`. The prompt allows at most three cut-scenes for the opening
  and big turning points, 2-4 slides each, with English `image_prompt`s.
- **Blueprint:** `[Cutscene: ID] Title` (`engine/blueprint/cutscene_blocks.py`): every body
  line is a slide, a `+` line a further passage of the slide above, `image N:` its picture, `style:` and `audio:` as above; chapters use
  `cutscene: ID`, `[World]` uses `intro_cutscene: ID` (alias `cutscene`), `win_cutscene: ID`, and `game_over_cutscene: ID`. The author's slides replace the LLM's for that id after generation; an LLM
  image prompt stays where the author gave none.
- **Apply:** `manifest_apply/adventure_meta` merges the cut-scenes by id (a re-applied manifest
  keeps drawn images); `manifest_apply/cutscene_media.py` draws missing slide images when scene
  images are on.
- **Export / import / clone:** slide images travel as `assets/` files (`engine/cutscenes/transfer.py`).

## 5. Limits and later

- Running sessions read the adventure copy made at session start; cut-scenes added later reach
  new sessions only.
- No per-slide duration or per-slide voice; slides are read by the narrator voice.
- Regions built with the Region Builder do not add cut-scenes yet.
