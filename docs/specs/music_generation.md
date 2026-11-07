# Music Generation (Concept)

Status (2026-11-07): **Phases 0–3 implemented**, Phase 4 and some cross-cutting items open.

| Phase | Status | Main modules |
| --- | --- | --- |
| 0: ComfyUI provider + `tw.music` | done | `engine/audio/comfyui_music.py`, `music_state.py`, `scripting/music_proxy.py` |
| 1: Provider abstraction + Lyria | done | `engine/audio/music_providers.py`, `lyria_music.py`, `core/music_settings.py` |
| 2: Music library + scene tracks (editor Music tab, playback, ADZ) | done (sequence overrides open) | `api/routes/adventures/editor_music.py`, `editor_music_tracks.py`, `music_snapshot.py`, `engine/audio/music_library.py`, `music_assets.py`, `music_prompt_context.py`, `components/editor/MusicTab.vue`, `SceneMusicSelect.vue` |
| 3: World-Builder (`music_tracks` / `music_track_id` in schemas, prompt, blueprint `[Music]`, AI fix) | done | `world_schemas.py`, `core/prompts.py`, `blueprint/field_specs.py`, `ai_fix_*` |
| 4: Lyria RealTime adaptive score | open | – |

Not built yet (see the sections below): sequence-level music overrides, the music style catalog,
batch "Generate all music", the cross-session render cache, a per-user Lyria quota, ducking
under TTS, player volume in `User.game_settings`, and the AI-music note in exported licenses.

## 1. Goals

* Every adventure can have background music that fits the place and the moment, the same way
  scenes have background images today.
* Authors get music without composing it: a prompt per scene (written by the author or by the
  World-Builder) is sent to a music model, like image prompts are sent to an image model.
* Scripts can change the music during play (boss fight, chase, twist) with prompts made on
  the fly.
* Music never blocks a turn. Rendering is slow (seconds to minutes); the game keeps playing
  the previous track until the new one is ready.

Non-goals: lyrics/vocals (instrumental only by default), music for TTS lines, editing a
generated track.

## 2. Phase 0 (implemented): ComfyUI provider and `tw.music`

| Piece | Where |
| --- | --- |
| Admin settings (`server_settings.music_settings`, migration `d4a7e2c9b1f3`) | `backend/core/music_settings.py`, `backend/api/routes/music_settings_api.py`, `frontend/src/components/admin/MusicSection.vue` |
| Workflow upload (API-format JSON, `{{prompt}}`, `{{negative_prompt}}`, `{{seed}}`, `{{duration}}` placeholders) | `backend/engine/audio/music_workflow.py` |
| ComfyUI transport (submit, poll own job, download `audio` output) | `backend/engine/audio/comfyui_music.py` |
| Script API `tw.music` (records `ScriptChangeset.music_ops`) | `backend/engine/scripting/music_proxy.py` |
| Session state `entity_states["__music__"]`, replayed by all changeset appliers | `backend/engine/audio/music_state.py` |
| Background rendering (one job at a time, file = ready) | `backend/engine/audio/music_generation.py` |
| `music` field of `GET /chat` (also starts missing renders) | `backend/api/routes/adventures/music_snapshot.py` |
| Client playback (cross-fade, mute, volume) | `frontend/src/composables/useGameMusic.ts`, `components/game/GameMusicToggle.vue` |

Design decisions that later phases keep:

* **The state says what should play; files say what is ready.** A background task never
  writes `entity_states` (that would race with running turns). A track is ready once
  `adventures/sessions/<session>/music/<track_id>.<ext>` exists. Checkpoints restore the music
  state; missing files are rendered again.
* **Named tracks are rendered once.** `tw.music.generate(prompt, name="crypt")` with a known
  name replays the stored track. This keeps GPU time and API cost proportional to the number
  of places, not the number of visits.
* **Limits** (default/maximum length, tracks per session) are admin settings.
* **Generation is driven by the client's regular 5-second state sync**, so there is no job
  queue to restart after a crash.

## 3. Google Lyria

Model facts as reported in September 2026 (see sources at the end). **Verify model IDs, request
shape and pricing against the Gemini API docs before implementing.**

| Model | Use in TaleWeaver | Output |
| --- | --- | --- |
| `lyria-3-clip-preview` (Lyria 3 Clip) | Scene loops, short stingers | Fixed 30 s clips, MP3 |
| `lyria-3.5` (Lyria 3.5) | Main theme / title music, long sequence scores | Full-length tracks, MP3 or WAV, 44.1 kHz stereo |
| Lyria RealTime (streaming, experimental) | Phase 4 only: adaptive score | Continuous PCM stream steered by weighted prompts |

Constraints that shape the design:

* Both batch models are reached through Google's **Interactions API** with the existing
  Google key (`resolve_api_key(keys, "google")`, so the key policy in `core/api_keys.py`
  applies: personal key, server key or disabled).
* Prompts pass **safety filters**: artist names and copyrighted lyrics are blocked. The
  prompt builder (Phase 2) must describe style, never name artists; a blocked prompt is
  reported to the author, not retried.
* Generation is **single-turn**: no editing of a track. "Make it darker" means a new prompt.
* Output carries a **SynthID** watermark. The adventure export notes that its music is
  AI-generated (see section 7).
* Lyria 3.5 also accepts up to 10 images with the prompt. Sending the scene's background
  image along is an option for "music that matches the picture" (Phase 2, behind a setting).

### Provider abstraction (Phase 1)

```python
# backend/engine/audio/music_providers.py
@dataclass(frozen=True)
class MusicRequest:
    prompt: str
    negative_prompt: str = ""
    duration: int = 30        # seconds; providers clamp to what they support
    seed: int | None = None
    loop: bool = True         # hint: ask for a seamless loop
    images: list[bytes] = ()  # Lyria 3.5 only

class MusicProvider(Protocol):
    name: str
    async def render(self, request: MusicRequest, settings: dict, keys: EffectiveKeys) -> AudioResult: ...
```

* `ComfyUIMusicProvider` wraps today's `render_track`.
* `LyriaMusicProvider` picks the model by duration: up to 30 s and `loop=True` uses Lyria 3
  Clip, longer requests use Lyria 3.5. Request: text prompt + negative prompt, response: base64
  audio, saved like the ComfyUI result.
* `MusicSettings.provider` becomes `Literal["comfyui", "lyria"]` plus `lyria_clip_model` /
  `lyria_full_model` (defaults above, editable so a renamed model does not need a release).
* `music_generation._generate` resolves the provider from the settings. The background task
  needs the user's effective keys, so `ensure_generation` receives them from the snapshot
  builder (the request user has `apply_global_settings` applied).
* Model discovery (`services/model_discovery`) gains a "music" capability for the model picker.
* The concurrency lock becomes per provider: ComfyUI keeps one job at a time (local GPU), Lyria
  allows a small number of parallel requests (setting, default 2).

## 4. Music library and scene tracks (Phase 2)

Each adventure owns a **music library**; scenes pick one track each. This replaced an earlier
per-scene prompt/URL design (migration `f7a1c4e8d2b6` turns old scene music and main themes into
library tracks).

### Data model

| Field | On | Meaning |
| --- | --- | --- |
| `music_tracks` | `AdventureTemplate` (JSON) | `[{id, name, prompt, url, source, reference_scene_id, created_at}]`, see `engine/audio/music_library.py` |
| `music_track_id` | `WorldScene` | The scene's track; NULL = silent scene |
| `music_enabled` | `AdventureTemplate` | Author switch for scene music (script music unaffected) |

`source` is `generated`, `uploaded` or `planned` (prompt only, e.g. from the World-Builder or an
`.adv` import without files). Files live in `adventures/library/<template>/music/`; URLs must point
into the adventure's own library folder (`music_assets.local_music_url`), deletions are limited to
its `music/` folder.

### Editor (Music tab)

* **Generate**: name, optional **reference scene**, prompt, length. **AI Prompt** asks the small
  model for a prompt from the adventure's tone, title and teaser plus the reference scene's name and
  description (or the plot when no scene is chosen); `ensure_loopable` always appends the
  seamless-loop instruction. Rendering is a background job (`MusicJobs`) the tab polls.
* **Upload**: MP3, WAV, OGG/Opus, FLAC, M4A up to 50 MB; the type is decided by the file content,
  the stored name is random.
* **Table**: play/stop, name and prompt (editable), source, scenes using the track, status
  (ready, composing with elapsed seconds, failed, no audio), render again, delete (scenes using it
  become silent).
* **Scene dialog**: a dropdown of the library tracks with preview.

All library writes go through `editor_music_tracks.update_tracks` under a per-adventure lock, so a
finishing render cannot overwrite an edit. Library and scene choices are mirrored into
`original_manifest` (template reset, World-Builder re-apply).

### Which music plays

Script track (`tw.music`) > the current scene's library track > silence. The snapshot id is the
track id, so:

* next scene, **same track** → keeps playing without interruption,
* next scene, **other track** → cross-fade (3 s),
* next scene **without track** → fade out.

The snapshot comes with every `GET /chat` and with the `scene_transition` stream event, so the
music changes on arrival, before the arrival narration. Session scene copies prefer their own
`music_track_id` and fall back to the template scene, and tracks are read from the live template,
so newly rendered music reaches running sessions.

### Import/export

* `.adz`: track files are bundled under `assets/`; `adventure.music_tracks[].url` holds the
  `assets/` path and is mapped back on import. Only files shipped in the bundle are accepted.
* `.adv` and World-Builder output keep the tracks as *planned* entries.
* Cloning copies the library with rewritten URLs.

## 5. World-Builder support (Phase 3)

* `WorldManifesto.music_tracks` (`MusicTrackSchema`: `id`, `name`, `prompt`) and
  `WorldSceneSchema.music_track_id`; the generation prompt asks for 2-6 tracks shared by scenes of
  the same mood. `manifest_apply.adventure_meta._apply_music_tracks` merges them into the library
  and keeps audio already rendered for a known id.
* Blueprint: `[Music: ID] Name` (alias `[Track: ID]`) with `prompt`; scenes use `music: ID`.
  Dropped tracks are re-inserted by `merge.apply_blueprint`.
* AI fix and editor change sets: scene field `music_track_id`.

## 6. Adaptive score with Lyria RealTime (Phase 4, optional)

Instead of files, a server-side WebSocket session streams music that follows the game:
weighted prompts per scene, `density`/`brightness`/`bpm` tied to combat state and HP. The backend
relays PCM chunks to the client (WebSocket or chunked HTTP, decoded with Web Audio). Open points:
cost per minute of play, one stream per active player, latency on scene change, and the model
still being experimental. Only worth it after Phases 1–2 are used.

## 7. Cross-cutting concerns

* **Cost control:** per-session track limit (exists), per-user daily quota for Lyria (new,
  `game_settings`), cache by `(provider, model, prompt, duration, seed)` hash so identical
  prompts across sessions reuse one file (`data/music_cache/`).
* **Licensing:** exported adventures carry an "AI-generated music (Google Lyria / local model)"
  note in their license block (`adventures/license_defaults`).
* **Accessibility & player control:** music volume and mute are per player (localStorage
  today; Phase 2 moves them into the player-owned `User.game_settings` so they follow the user
  across devices). Music ducks while TTS speaks (`speechWait.ts` already knows when speech plays).
* **Security:** downloaded audio is size-limited (96 MiB), file names are generated
  (`uuid4().hex`), all paths go through `backend.utils.path_security`. Provider URLs use
  `validate_provider_url`.
* **Telemetry:** `log_structured_event("music.render", provider, model, seconds, bytes, ok)`
  for latency percentiles in `taleweaver-telemetry`.

## 8. Open questions

1. Should script music (`tw.music.generate`) use Lyria too, or stay local-only because it runs
   at play time and costs per session? Proposal: allowed, counted against the per-user quota.
2. Cache across sessions/users: good for cost, but a shared cache leaks prompts between users.
   Proposal: cache per adventure template only.
3. Loop quality of 30 s clips: is the client-side overlap enough, or should Lyria 3.5 render
   60–90 s tracks for scenes where players stay long?

## Sources

* Unite.AI, "Google brings Lyria 3.5 music generation to the Gemini app and API" (Sept. 2026),
  citing Google's developer docs:
  <https://unite.ai/google-brings-lyria-3-5-music-generation-to-the-gemini-app-and-api>
* ComfyUI ACE-Step workflow templates: <https://comfy.org/workflows/audio_ace_step_1_t2a_song-07657d3f976b>
