# TaleWeaver MCP Server Specification

## 1. Goals & Scope

Expose TaleWeaver's adventure library, runtime session diagnostics, adventure authoring, and generation pipelines over the **Model Context Protocol (MCP)** so external AI agents (Claude Code, Claude Desktop, Cursor, Antigravity, Codex, etc.) can work against a running TaleWeaver instance remotely without direct database access, local CLI scripts, or stale bundled documentation.

### Core Principles
- **Single source of truth**: Reuse TaleWeaver's backend services (`change_set.py`, `WorldGenerator`, `MediaEngine`, `analyze_blueprint`, `validate_adventure`) rather than invoking CLI scripts via subprocesses.
- **Full parity with existing scripts & skills**: Cover the capabilities of `inspect_state.py`, `edit_adventure.py`, `adventure_api.py`, `analyze_llm_latency.py`, and the workflows of `taleweaver-adventure-concept-creator` and `taleweaver-music-prompts`.
- **Secure by default**: The MCP endpoint is disabled until explicitly enabled by an admin. Authentication uses revocable bearer tokens stored as SHA-256 hashes, with granular server-level and optional per-token feature scoping enforced server-side.
- **Modular architecture**: Organize the MCP layer into focused modules under `backend/mcp/` (< 400 lines per module) backed by shared service modules.

---

## 2. Transport & Runtime Architecture

The MCP server runs embedded inside the existing FastAPI application (`backend/main.py`) as a native stateless **Streamable HTTP JSON-RPC 2.0** endpoint at `/mcp` (`POST /mcp`, `405` on `GET /mcp`, `204` on `DELETE /mcp`).

- **Endpoint URL**: `https://<taleweaver-host>/mcp` (or `http://localhost:8000/mcp` in local dev).
- **Embedded lifecycle**: Shares `AsyncSessionLocal`, `ServerSettings`, background job runners, `MediaEngine`, and `WorldGenerator`. Admin updates to settings, feature toggles, or token revocations take effect immediately without a restart.
- **Reverse proxy & routing**:
  - `backend/main.py`: Exclude `/mcp` (and `/mcp/*`) from the SPA catch-all route and allow `MCP-Protocol-Version` / `Mcp-Session-Id` CORS headers.
  - `nginx/nginx.conf`: Dedicated `location /mcp` block with `proxy_buffering off;` and `proxy_read_timeout 600s;` so Streamable HTTP responses work cleanly behind TLS.

---

## 3. Feature Groups & Capabilities

Every MCP tool, resource, and prompt belongs to one of six feature groups. Disabled groups are hidden from discovery (`tools/list`, `resources/list`) and rejected server-side on execution (`tools/call`).

### 3.1 `read_adventures` — Library & Adventure Inspection
Covers `taleweaver-inspector` (`list-adventures`, `list-disk-adventures`, `show-adventure`, `dump-manifest`), `edit_adventure.py` (`summary`, `export`, `ops`), and the online library catalog:
- `list_adventures`: List adventure templates in the database.
- `list_library_catalog`: Browse the online library catalog, available updates, and `.adv`/`.adz` files on disk (`adventures/`, `data/imports/`).
- `get_adventure_summary`: Compact ID index of scenes, exits (`FROM->TO`), NPCs, objects, scripts, quests, sections, and init script line count.
- `get_adventure_details`: Full or filtered editor payload (`scenes`, `exits`, `npcs`, `objects`, `quests`, `awards`, `scripts`, `cutscenes`, `audio_tracks`, `sections`, or a single scene slice with neighbors).
- `export_adventure_manifest`: Export the `.adv` JSON manifest (Format `1.5.0`).
- `list_change_set_operations`: Inspect schemas and allowed fields for all change-set operations.

### 3.2 `read_sessions` — Session State & Gameplay Inspection
Covers `taleweaver-inspector` (`list-sessions`, `show-session`) and session integrity checks. Game sessions remain **strictly read-only** over MCP (automated play stays with the built-in Play-Agent):
- `list_sessions`: List active and recent game sessions (filterable by adventure, user, limit).
- `get_session_state`: Full or focused runtime state (avatar stats, inventory/equipment, current scene, `entity_states` overrides, `exit_states`, quests, flags/vars, active conditions, pending region expansions).
- `get_session_chat`: Paginated dialogue history (User, Assistant, System turns).
- `get_session_checkpoints`: List saved checkpoints (Chronicles Timeline) for a session.
- `check_session_integrity`: Run item/inventory integrity checks.

### 3.3 `edit_adventures` — Authoring, Validation & Import
Covers `taleweaver-adventure-editor` (`edit_adventure.py`), `adventure_api.py` (`import`, `validate`, `validate-blueprint`), cutscenes, and audio track metadata:
- `validate_blueprint`: Run `analyze_blueprint` on a tagged Story Idea / Markdown blueprint.
- `validate_adventure`: Run structural validation (`validate_adventure`) on an existing template (`include_ai=true` also requires `generate_adventures`).
- `apply_adventure_changes`: Execute a transactional change set via `apply_change_set` + `DeferredCommitSession`. Defaults to `commit=false` (dry run) and reports only newly introduced validation findings; new `error` findings block commit unless `allow_errors=true`. For CWE-22 safety, `{"$file": ...}` disk reads are disabled over MCP (script code is passed inline).
- `import_adventure_manifest`: Import a `.adv` JSON manifest (or install from library/disk) with optional post-import validation.
- `manage_cutscenes`: Read or update an adventure's `cutscenes` definitions.
- `manage_audio_tracks`: List, create, update, or delete `audio_tracks` (including Suno/Stable Audio prompts) and assign scene tracks or `title_track_id`.
- `delete_adventure`: Delete an entire adventure template. **Requires both `edit_adventures` and the separate `allow_destructive` toggle** (off by default). Scene/entity deletes inside change sets remain under `edit_adventures`.

### 3.4 `generate_adventures` — LLM World & Region Generation
Covers Portal World-Builder generation, Region Builder, story suggestions, and AI validation/fixes (gated separately because it consumes LLM quota):
- `suggest_story_idea`: Generate or refine a title and story idea.
- `generate_adventure`: Start asynchronous World-Builder generation from a Story Idea or Blueprint; returns `template_id` and `session_id`.
- `get_generation_status`: Poll creation progress (`is_ready`, `creation_status`) and retrieve generation logs.
- `cancel_generation`: Cancel an active generation job.
- `generate_region`: Build a planned world section / region via the Region Builder and poll status.
- `ai_validate_and_suggest_fixes`: Run AI logic validation and/or generate reviewable AI fix proposals.

### 3.5 `generate_media` — Visuals & Audio Rendering
Covers `adventure_api.py` (`visuals`, `upload-visual`), cutscene slide images, audio rendering, and thumbnail generation. Always uses TaleWeaver's server-side `MediaEngine` and audio pipeline with `apply_global_settings(db, user)`:
- `generate_visual`: Generate or regenerate a single visual (`cover`, `protagonist`, `scene`, `npc`, `object`, `cutscene_slide`).
- `generate_adventure_visuals`: Batch-generate missing or selected visuals (async by default).
- `get_visual_job_status`: Poll progress and per-target results of a `generate_adventure_visuals` job.
- `upload_visual`: Upload a validated image (base64 + MIME type) to a visual target.
- `render_audio_track`: Trigger server-side audio rendering (`Lyria` or `ComfyUI`).
- `get_audio_job_status`: Poll status of a `render_audio_track` background job.
- `regenerate_thumbnails`: Generate missing web thumbnails in `data/adventures/library/`.

### 3.6 `diagnostics` — System Health & LLM Telemetry
Covers `inspect_state.py db-status` and `taleweaver-telemetry` (`scripts/analyze_llm_latency.py`):
- `get_db_status`: SQLite journal mode, DB/WAL/SHM sizes, table record counts, and `data/` storage usage.
- `get_llm_telemetry`: Pipeline and request/response latency percentiles (`min`, `p50`, `p90`, `p95`, `max`, `avg`), supporting `since_minutes` and `split_ts`.

### 3.7 MCP Resources & Prompts
When `read_adventures` is enabled, live resources replace static bundled docs:
- `taleweaver://docs/world-builder-syntax`
- `taleweaver://docs/blueprint-manual`
- `taleweaver://docs/scripting-engine`
- `taleweaver://docs/adventure-format`
- `taleweaver://catalogs/styles`, `taleweaver://catalogs/tones`, `taleweaver://catalogs/narrator-voices`
- `taleweaver://adventures/{template_id}/summary` and `taleweaver://sessions/{session_id}/state`

Workflow prompts (`create_adventure_blueprint`, `edit_adventure_safely`, `craft_music_prompts`, `diagnose_session`) encode the guardrails and formatting checklists from the `.claude/skills/` guides.

### 3.8 Explicitly Excluded Operations
Host and repository dev-tools are **never** exposed over MCP:
- `generate_keys.py` / `.env` secret management
- `reset_admin.py` (credential/password resets)
- `freeze_catalogs.py`, `convert_assets.py`, `bundle_skill.py`
- Raw SQL execution or arbitrary host filesystem access

---

## 4. Security, Authentication & Data Model

### 4.1 Server Settings (`ServerSettings.mcp_settings`)
Stored as JSON in `server_settings.mcp_settings`:

```json
{
  "enabled": false,
  "features": {
    "read_adventures": true,
    "read_sessions": true,
    "edit_adventures": false,
    "generate_adventures": false,
    "generate_media": false,
    "diagnostics": true
  },
  "allow_destructive": false,
  "allow_cross_user_access": false
}
```

- **`enabled`**: Master switch (`false` by default). When `false`, `/mcp` rejects all requests.
- **`allow_destructive`**: Required in addition to `edit_adventures` for deleting entire adventure templates (`false` by default).
- **`allow_cross_user_access`**: When `false`, tokens only access adventures/sessions owned by their bound `user_id`. When `true`, admin-bound tokens may inspect across all users.

### 4.2 Access Tokens (`mcp_tokens` Table)
- Columns: `id` (UUID7 PK), `name`, `token_prefix` (display prefix e.g. `tw_mcp_...`), `token_hash` (unique indexed SHA-256 hex digest), `user_id` (FK `users.id`), `allowed_features` (nullable JSON list — `null` inherits server toggles; non-null narrows to a subset), `created_by_user_id` (FK `users.id`), `created_at`, `updated_at`, `expires_at`, `last_used_at`, `revoked_at`.
- Raw secret (`tw_mcp_<32-byte urlsafe token>`) is returned **once** upon creation and never persisted in plaintext.
- Effective permissions on every request:
  `server.enabled AND feature in server_enabled_features AND (token.allowed_features is None OR feature in token.allowed_features)`.
- Every MCP execution loads the acting `User` and calls `await apply_global_settings(db, acting_user)` so server-wide keys and model/media settings apply consistently.
- Every tool call emits a structured audit log entry (`token_id`, `token_name`, `user_id`, `tool_name`, `target_id`, `outcome`, `duration_ms`).

### 4.3 Admin REST Endpoints (`/api/settings/mcp`)
Protected by `get_current_admin`:
- `GET /api/settings/mcp` — load normalized MCP settings + `endpoint_path`.
- `POST /api/settings/mcp` — save MCP endpoint, feature toggles, and safety options.
- `GET /api/settings/mcp/tokens` — list tokens with status (`active`, `expired`, `revoked`), bound user, and scopes (never hashes or secrets).
- `POST /api/settings/mcp/tokens` — create a new token and return `{ token, plain_token }` once.
- `DELETE /api/settings/mcp/tokens/{token_id}` — revoke a token immediately.

---

## 5. Admin Console UI

Located under **System → MCP Server** (`?section=mcp`) in `AdminView.vue`:
1. **Endpoint card**: Master `Enable MCP endpoint` toggle, read-only endpoint URL with copy action, and a collapsed `UiDisclosure` containing a copy-ready client configuration snippet.
2. **Features & safety card**: Six feature group toggles (with quota badges on LLM/media generation) plus a collapsed `UiDisclosure` for `Allow destructive deletes` and `Allow cross-user inspection`. Saved via a single `UiSaveBar` (`useDraft`).
3. **Access tokens card**: Token list with status badges, bound user, scope summary, expiration/last-used metadata, revoke confirmation (`useConfirm({ danger: true })`), `McpTokenCreateModal` (name, acting user, expiration, inherit vs. custom scope with Read-only preset), and `McpTokenRevealModal` (one-time copy dialog).

---

## 6. Phased Implementation Roadmap

- **Phase 1 — Settings, Tokens & Admin UI** *(Done)*
  - `ServerSettings.mcp_settings` + `McpToken` model & Alembic migration.
  - `backend/core/mcp_settings.py` + `backend/api/routes/mcp_settings_api.py`.
  - Admin Console `McpSection.vue`, token modals, navigation entry, tests, and UI checks.
- **Phase 2 — MCP Core, Auth, Read Tools, Diagnostics & Resources** *(Done)*
  - Native embedded Streamable HTTP `/mcp` router mounted in `backend/main.py` and `nginx/nginx.conf`.
  - Extracted shared `inspection_service.py`, `session_inspection_service.py`, and `telemetry_service.py`.
  - Implemented `read_adventures`, `read_sessions`, `diagnostics`, live MCP Resources, and Prompts.
- **Phase 3 — Adventure Editing, Validation & Import** *(Done)*
  - Implemented `validate_blueprint`, `validate_adventure`, `apply_adventure_changes` (dry-run default, no `$file`), `import_adventure_manifest`, `manage_cutscenes`, `manage_audio_tracks`, `delete_adventure`.
- **Phase 4 — Generation & Media Pipelines** *(Done)*
  - Implemented `suggest_story_idea`, `generate_adventure`, `get_generation_status`, `cancel_generation`, `generate_region`, `ai_validate_and_suggest_fixes`, `generate_visual`, `generate_adventure_visuals`, `get_visual_job_status`, `upload_visual`, `render_audio_track`, `get_audio_job_status`, `regenerate_thumbnails`.
- **Phase 5 — User Docs & End-to-End Verification** *(Done)*
  - Added user-facing MCP setup & reference guide ([docs/mcp-server.md](../mcp-server.md)) and linked it in `README.md`.
  - Added full-lifecycle end-to-end integration tests (`tests/test_mcp_e2e.py`).
