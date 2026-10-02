---
description: Mandatory security rules for file paths, path traversal prevention (CWE-22), and safe file operations.
trigger:
  type: model_decision
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
