# TaleWeaver MCP Server

TaleWeaver embeds a stateless **Streamable HTTP [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)** server directly at `/mcp` inside the FastAPI backend. External AI coding assistants and agents — such as Claude Code, Claude Desktop, Cursor, Antigravity, or Codex — can inspect your adventure library and game sessions, author or import templates safely, and trigger world or media generation without touching the SQLite database directly or maintaining separate CLI scripts.

> [!NOTE]
> The MCP endpoint is **disabled by default** (`enabled: false`). Requests to `/mcp` return `503 Service Unavailable` until an administrator enables it and issues a bearer token.

---

## Quick Start

1. Open **Admin → System → MCP Server** (`?section=mcp`).
2. Turn on **Enable MCP endpoint**, select the feature groups you want external agents to access, and click **Save** in the bottom save bar.
3. Click **Create token**, give it a clear label (for example `Claude Code Laptop`), pick the acting TaleWeaver user account, optionally restrict its scope (such as the **Read-only** preset) or set an expiration, and create the token.
4. Copy the raw `tw_mcp_...` bearer secret from the reveal modal — it is shown **only once** and stored server-side as a SHA-256 hash.
5. Expand **Client configuration snippet** in the **Endpoint** card to copy a ready-to-use JSON block prefilled with your server's URL.

Changes to MCP settings, feature toggles, and token revocations take effect on the next request with no server restart required.

---

## Connecting MCP Clients

TaleWeaver implements **Streamable HTTP JSON-RPC 2.0** (`POST /mcp`, returning `405` on `GET /mcp` and `204` on `DELETE /mcp`).

### Generic Streamable HTTP Configuration

Use this structure in MCP clients that accept an `mcpServers` JSON config (replace the URL and token with your own):

```json
{
  "mcpServers": {
    "taleweaver": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp",
      "headers": {
        "Authorization": "Bearer tw_mcp_<your-token>"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add --transport http taleweaver http://127.0.0.1:8000/mcp \
  --header "Authorization: Bearer tw_mcp_<your-token>"
```

### Docker & Reverse Proxy (HTTPS)

The bundled [`nginx/nginx.conf`](../nginx/nginx.conf) already routes `/mcp` with `proxy_buffering off;` and a `600s` read timeout. Point your client at `https://<your-taleweaver-host>/mcp`. If you deploy behind another reverse proxy, forward `Authorization` headers and avoid response buffering on `/mcp`.

If your Docker or LAN deployment uses a self-signed TLS certificate that your MCP client does not trust, select **Self-signed HTTPS (mcp-remote)** in **Admin → System → MCP Server → Client configuration snippet** to copy a stdio bridge configuration (`npx -y mcp-remote` with `NODE_TLS_REJECT_UNAUTHORIZED=0`).

---

## Feature Groups, Safety Toggles & Token Scoping

Every tool, resource, and prompt belongs to one of six feature groups. Disabled groups are omitted from discovery (`tools/list`, `resources/list`, `prompts/list`) and rejected if called directly.

| Feature key | Admin UI label | Default | Notes |
|---|---|---|---|
| `read_adventures` | Library & adventure read | On | Read-only inspection of DB templates, catalogs, change-set schemas, and live docs. |
| `read_sessions` | Session inspection | On | Read-only inspection of sessions, state, checkpoints, and chat history. |
| `edit_adventures` | Adventure editing & import | Off | Blueprint/adventure validation, change sets, manifest import, cutscenes, and planned audio tracks. |
| `generate_adventures` | Adventure & region generation | Off | **Consumes LLM quota.** Story suggestions, World-Builder, Region Builder, and AI validation/fixes. |
| `generate_media` | Visuals & audio rendering | Off | **Consumes Media quota.** Server-side `MediaEngine` images, uploads, audio rendering, and thumbnails. |
| `diagnostics` | System diagnostics & telemetry | On | SQLite/storage stats and LLM pipeline latency percentiles. |

### Safety Toggles (Advanced)

Inside **Features & safety → Advanced safety options**:

- **Allow destructive deletes (`allow_destructive`, default off):** Required *in addition to* `edit_adventures` before `delete_adventure` is exposed or permitted. `delete_adventure` also requires `confirm_title` to match the exact adventure title. Deleting individual scenes or entities inside `apply_adventure_changes` stays governed by `edit_adventures`.
- **Allow cross-user inspection (`allow_cross_user_access`, default off):** When off, every token is restricted to adventures and sessions owned by its bound `user_id`. When on, tokens bound to an admin user can inspect and operate across all users' templates and sessions.

### Effective Permissions

Per-request permissions are the intersection of server settings and optional per-token scoping (`allowed_features`):

```
allowed = server.enabled
          AND feature in server.features (enabled)
          AND (token.allowed_features is null OR feature in token.allowed_features)
```

For tokens intended strictly for debugging or blueprint authoring, choose **Custom features** → **Read-only preset** when creating the token (`read_adventures`, `read_sessions`, `diagnostics`).

> [!IMPORTANT]
> Game sessions are **strictly read-only** over MCP. Automated gameplay stays inside TaleWeaver's built-in [Play-Agent](play-agent.md).

---

## Available MCP Surface

### Tools (33)

#### `read_adventures` — Library & Adventure Inspection
| Tool | Purpose |
|---|---|
| `list_adventures` | List adventure templates stored in the database. |
| `list_library_catalog` | Browse the online TaleWeaver library catalog and local `.adv`/`.adz` files on disk. |
| `get_adventure_summary` | Compact ID index of scenes, exits (`FROM->TO`), NPCs, objects, scripts, quests, sections, and init script line count. |
| `get_adventure_details` | Full editor payload, filtered sections, or a single scene slice with neighboring routes and entities. |
| `export_adventure_manifest` | Export an adventure template as a complete `.adv` JSON manifest (Format `1.5.0`). |
| `list_change_set_operations` | Inspect supported operation names and allowed field schemas for `apply_adventure_changes`. |

#### `read_sessions` — Session State & Gameplay Inspection
| Tool | Purpose |
|---|---|
| `list_sessions` | List recent game sessions with player, active scene, and status metadata. |
| `get_session_state` | Runtime session snapshot: avatar stats, inventory/equipment, entity/exit overrides, quests, variables, and pending expansions. |
| `get_session_chat` | Paginated User, Assistant, and System conversation turns. |
| `get_session_checkpoints` | Saved Chronicles Timeline checkpoints for a session. |
| `check_session_integrity` | Verify session avatar inventory and equipment fields against template object definitions. |

#### `edit_adventures` — Authoring, Validation & Import
| Tool | Purpose |
|---|---|
| `validate_blueprint` | Run structural/script checks (`analyze_blueprint`) on a tagged Story Idea / Markdown blueprint. |
| `validate_adventure` | Run structural validation on an existing template (`include_ai=true` also requires `generate_adventures`). |
| `apply_adventure_changes` | Execute a transactional change set; defaults to `commit=false` (dry run) and blocks commits introducing new errors unless `allow_errors=true`. |
| `import_adventure_manifest` | Import an inline `.adv` JSON manifest or install an adventure from the online library / disk catalog. |
| `manage_cutscenes` | Read or replace an adventure's cutscenes and intro/win/game-over cutscene IDs. |
| `manage_audio_tracks` | List, create, update, delete, or assign planned audio tracks (including Suno and Stable Audio prompts). |
| `delete_adventure` | Permanently delete an adventure template. Requires `edit_adventures`, `allow_destructive=true`, and exact `confirm_title`. |

#### `generate_adventures` — LLM World & Region Generation
| Tool | Purpose |
|---|---|
| `suggest_story_idea` | Generate or refine a title and Story Idea using the configured small LLM. |
| `generate_adventure` | Start asynchronous World-Builder generation from a Story Idea or tagged blueprint. |
| `get_generation_status` | Poll adventure or region generation progress, status, errors, and optional logs. |
| `cancel_generation` | Cancel an in-progress adventure generation job. |
| `generate_region` | Start asynchronous Region Builder generation for a planned world section. |
| `ai_validate_and_suggest_fixes` | Run AI logic validation on an adventure, or request reviewable fix proposals for a finding. |

#### `generate_media` — Visuals & Audio Rendering
| Tool | Purpose |
|---|---|
| `generate_visual` | Generate or regenerate a single visual (`cover`, `protagonist`, `scene`, `npc`, `object`, or `cutscene_slide`) via `MediaEngine`. |
| `generate_adventure_visuals` | Batch-generate missing or selected visual assets (asynchronous by default). |
| `get_visual_job_status` | Poll progress and per-target results of a `generate_adventure_visuals` job. |
| `upload_visual` | Upload a validated base64 PNG/JPEG/WEBP image for a cover, protagonist, scene, npc, object, or cutscene slide. |
| `render_audio_track` | Trigger server-side audio track rendering (`Google Lyria` or `ComfyUI`). |
| `get_audio_job_status` | Poll status of a `render_audio_track` background job. |
| `regenerate_thumbnails` | Generate missing web thumbnails for one adventure or all accessible adventures. |

#### `diagnostics` — System Health & LLM Telemetry
| Tool | Purpose |
|---|---|
| `get_db_status` | Inspect SQLite journal mode, DB/WAL/SHM sizes, table record counts, and `data/` disk usage. |
| `get_llm_telemetry` | Compute LLM turn pipeline and request/response latency percentiles (`min`, `p50`, `p90`, `p95`, `max`, `avg`). |

### Live Resources (7 Static + 2 Templates)

Exposed when `read_adventures` (and `read_sessions` for session state) is enabled:

- `taleweaver://docs/world-builder-syntax` — Tagged blueprint key reference ([`docs/world-builder-syntax.md`](world-builder-syntax.md))
- `taleweaver://docs/blueprint-manual` — Blueprint authoring workflow ([`docs/world-builder-blueprint-manual.md`](world-builder-blueprint-manual.md))
- `taleweaver://docs/scripting-engine` — Sandboxed Python `tw.*` API guide ([`docs/scripting_engine.md`](scripting_engine.md))
- `taleweaver://docs/adventure-format` — `.adv` / `.adz` manifest spec ([`docs/specs/adventure_format.md`](specs/adventure_format.md))
- `taleweaver://catalogs/styles` — Configured server image styles catalog
- `taleweaver://catalogs/tones` — Configured server narrative tones catalog
- `taleweaver://catalogs/narrator-voices` — Configured narrator persona voices catalog
- `taleweaver://adventures/{template_id}/summary` — Live compact summary JSON for an adventure
- `taleweaver://sessions/{session_id}/state` — Live runtime state snapshot for a game session

### Workflow Prompts (4)

- `create_adventure_blueprint` (`read_adventures`) — Checklist for authoring validated Story Idea blueprints with deterministic puzzles and a planted twist.
- `edit_adventure_safely` (`read_adventures`) — Safe inspect → dry-run → validate → commit workflow.
- `craft_music_prompts` (`read_adventures`) — Generates Suno and Stable Audio soundtrack prompts preloaded with an adventure's tone, chapters, cutscenes, and scenes.
- `diagnose_session` (`read_sessions`) — Structured session troubleshooting checklist preloaded with runtime state.

---

## Recommended Workflows & Security Boundaries

- **Always dry-run adventure edits first:** Call `get_adventure_summary` and `list_change_set_operations`, then run `apply_adventure_changes` with `commit=false` (the default). Inspect `new_findings` and re-run with `commit=true` only when no unintended errors are introduced. Inline script code must be supplied directly in change sets (`{"$file": ...}` disk reads are disabled over MCP).
- **Poll asynchronous jobs cleanly:** Generation calls (`generate_adventure`, `generate_region`, `generate_adventure_visuals`, `render_audio_track`) return immediately with IDs (`template_id`/`session_id` or `job_id`). Poll `get_generation_status`, `get_visual_job_status`, or `get_audio_job_status` until completion.
- **Server-side settings & audit logging:** Every tool call runs under the token's acting user with global server provider/media settings applied (`apply_global_settings`) and emits a structured `mcp.tool_call` audit log entry.
- **Explicitly excluded operations:** Host setup and maintenance utilities (`generate_keys.py`, `reset_admin.py`, `freeze_catalogs.py`, `convert_assets.py`, `bundle_skill.py`), arbitrary filesystem reads/writes, and raw SQL execution are never exposed over MCP.
