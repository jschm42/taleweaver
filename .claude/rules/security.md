---
description: Mandatory security rules for file paths, path traversal prevention (CWE-22), safe file operations, and session ownership checks (CWE-639).
trigger: model_decision
---

# Security & Path Traversal Prevention (CWE-22)

1. **Path Traversal Protection**:
   * Never directly concatenate or trust user input (usernames, template IDs, asset filenames) to construct filesystem paths.
   * **Mandatory Helper**: Always use `backend.utils.path_security`:
     * `ensure_within_data_dir(path)`
     * `safe_data_path(...)`
     * `data_url_to_local_path(...)`
     * `local_path_to_data_url(...)`
2. **Filesystem Sinks**:
   * Never pass untrusted paths to `open()`, `shutil.copy*`, `os.makedirs()`, `os.remove()`, or `sendfile()`.
   * Paths passed to sinks must be validated through `backend.utils.path_security`.
3. **Input Sanitization**:
   * Use regex validation for variable path elements (e.g. `^[A-Za-z0-9_-]{1,128}$`).
   * Strip path separators (`/`, `\`) or traversal sequences (`..`).
   * When handling uploaded files, use random UUIDs (e.g. `f"{uuid.uuid4()}.{ext}"`) or `os.path.basename`.
4. **Verification**:
   * Any changes to path-building or file-writing code must pass:
     ```bash
     pytest tests/test_security_hardening.py
     ```

# Session Ownership (CWE-639)

5. **A session id is not an access token**:
   * Resolve a session for a request only with `AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)` (or `GameTurnManager(...).initialize()`, which does that). With `user_id` it returns `None` for another user's session; answer `404`.
   * Never call it without `user_id` for request data, and never load `SessionState` / `GameSession` by id alone in a route.
   * Endpoints that take an optional `session_id` next to a template id (e.g. `map_api.py`) must check the session's owner too, not only the template's.
   * Verification: `pytest tests/test_session_ownership.py`; add new session endpoints to its parametrized list.
