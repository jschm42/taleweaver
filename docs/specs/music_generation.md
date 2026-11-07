# Music Generation (Concept)

Status: **Phase 0 implemented** (experimental ComfyUI provider + `tw.music` scripting API).
Phases 1–4 (Google Lyria, per-scene music, World-Builder support) are a proposal.

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

## 4. Per-scene music (Phase 2)

Mirrors scene images: a prompt is stored on the entity, generated once in the editor, stored as
an asset, exported in the `.adz`.

### Data model

| Field | On | Meaning |
| --- | --- | --- |
| `music_prompt` | `AdventureTemplate` | Main theme; also the fallback for scenes without music |
| `music_url` | `AdventureTemplate` | Rendered main theme (`/data/adventures/library/<id>/music/theme.<ext>`) |
| `music_prompt`, `music_url` | `WorldScene` | Scene loop |
| `music_prompt`, `music_url` | sequence dict | Optional override while the sequence is active (chase, siege) |
| `music_enabled` | `AdventureTemplate` | Author switch; off = no music even if prompts exist |

Session copies keep the URLs like images (`resolve_session_asset`), so a template change does not
break a running session.

### Which music plays

Priority, highest first: script music (`tw.music`, while `now` is set) > active sequence music >
scene music > adventure main theme > silence. The client already cross-fades on change, so
scene changes reuse `useGameMusic`. The snapshot adds a `source` field (`script`, `sequence`,
`scene`, `theme`) for the debug view. `tw.music.stop()` keeps today's meaning (silence until the
next play); a new `tw.music.release()` hands control back to scene music.

### Prompt building

* New target type `scene_music` / `adventure_music` for the existing prompt-suggestion endpoint
  (`SuggestPromptRequest.target_type`): the small model turns scene description, adventure tone,
  narrator voice and time of day into a music prompt (genre, instruments, tempo, mood; no artist
  names, no lyrics). Rules live in a new `backend/engine/audio/music_prompt_context.py`, next to
  `image_prompt_context.py`.
* A **music style catalog** (admin, like image styles and tones: "Orchestral fantasy",
  "Synthwave noir", "Chiptune") is appended to every prompt of an adventure, so all its scenes
  sound like one score.
* For loops: the prompt gets "seamless loop, no intro, no ending". The client additionally
  overlaps the loop point by 1–2 s with a second audio element, because 30 s clips rarely
  loop cleanly.

### Editor and generation

* Scene editor: music prompt field, "Suggest prompt", "Generate", player, "Remove". Same for the
  adventure (Main Theme) and sequences.
* "Generate all music" runs as a generation job (like batch scene images) with progress.
* Generation happens at **edit time**, so playing an adventure costs nothing. Players of
  imported adventures get the bundled files.

### Import/export

* `.adz`: `assets/music/<scene_id>.<ext>`, `assets/music/theme.<ext>`; the manifest stores
  relative paths like images (`adventure_exporter.py`, `manifest_apply/`). `.adv` keeps the
  prompts only; the importer renders nothing automatically, the editor shows "music missing".
* Adventure format spec (`docs/specs/adventure_format.md`) bumps to 1.4.

## 5. World-Builder support (Phase 3)

Per the engine change propagation rule (AGENTS.md, rule 5) the new fields need:

1. Generation schemas (`world_schemas.py`: `music_prompt` on scenes, sequences, adventure)
   and the generation prompt (`WORLD_GENERATION_SYSTEM_PROMPT`: one short music prompt per scene,
   style rules).
2. Blueprint key `music:` for `Scene`, `Sequence` and `World` tags (`field_specs.py`,
   `converters.py`, `prompt.py`).
3. Exporter/importer round trip (`tests/test_adventure_lifecycle.py`).
4. AI fix allowlists and `FIX_PATCH_FIELD_RULES`.
5. Validators: warn when a scene has a music URL whose file is missing.
6. Docs: `world-builder-syntax.md`, `world-builder-blueprint-manual.md`, skills, bundle rebuild.

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
