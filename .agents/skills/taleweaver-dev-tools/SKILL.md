---
name: taleweaver-dev-tools
description: Developer toolkit for TaleWeaver administration, security key generation, admin credential resets, catalog management, media thumbnail regeneration, ADZ archive extraction, and agent skill bundling.
---

# TaleWeaver Developer & Administration Tools

Use this skill when you need to configure environments, manage admin credentials, generate security keys, freeze catalog defaults, process media assets, unpack adventure archives, or bundle agent skills for distribution.

All commands should be executed with Poetry: `poetry run python scripts/<script_name>.py`.

---

## 1. Security & Cryptographic Key Generation

TaleWeaver requires `ENCRYPTION_KEY` (Fernet base64) and `SECRET_KEY` (32-byte hex) in `.env` for securing session state, password hashing, and API authentication.

Script: [scripts/generate_keys.py](file:///c:/Users/jean/DEV/repositories/taleweaver/scripts/generate_keys.py)

```bash
# Generate both keys formatted for .env
poetry run python scripts/generate_keys.py

# Generate only the Fernet encryption key
poetry run python scripts/generate_keys.py --fernet

# Generate only the Secret key
poetry run python scripts/generate_keys.py --secret

# Output raw key strings without variable prefixes
poetry run python scripts/generate_keys.py --raw
```

*(Note: `scripts/generate_fernet_key.py` is maintained as a backward-compatible wrapper).*

---

## 2. Admin User & Password Management

Reset an existing administrator password or bootstrap a new root admin user.

Script: [scripts/reset_admin.py](file:///c:/Users/jean/DEV/repositories/taleweaver/scripts/reset_admin.py)

```bash
# Reset admin with a strong password (enforcing security policy)
poetry run python scripts/reset_admin.py admin "Your-Strong-Pa55!word"

# Reset admin for local development bypassing strict password complexity
poetry run python scripts/reset_admin.py admin admin123 --no-strict

# Reset a custom username
poetry run python scripts/reset_admin.py lead_weaver "SuperSecret123!" --no-strict
```

---

## 3. Style & Tone Catalog Freezing

Extract customized image styles and tone catalogs from the database user and freeze them into default codebase definitions (`backend/core/catalog_defaults.py`) and static assets.

Script: [scripts/freeze_catalogs.py](file:///c:/Users/jean/DEV/repositories/taleweaver/scripts/freeze_catalogs.py)

```bash
# Freeze catalogs from DB to backend/core/catalog_defaults.py and backend/static/assets/catalog/
poetry run python scripts/freeze_catalogs.py
```

---

## 4. Adventure Media & Thumbnail Generation

Iterates through all adventures in `data/adventures/library/` and generates missing web-optimized thumbnail images.

Script: [scripts/generate_thumbnails.py](file:///c:/Users/jean/DEV/repositories/taleweaver/scripts/generate_thumbnails.py)

```bash
# Generate thumbnails for all adventures in data/adventures/library/
poetry run python scripts/generate_thumbnails.py
```

---

## 5. ADZ Archive Asset Extraction

Unpack entity, scene, and item image assets from `.adz` adventure archives and generate structured metadata indexes (`metadata.json`).

Script: [scripts/extract_adz_assets.py](file:///c:/Users/jean/DEV/repositories/taleweaver/scripts/extract_adz_assets.py)

```bash
# Extract assets from a source directory of .adz files
poetry run python scripts/extract_adz_assets.py --source adventures/samples --target data/extracted_assets --json data/extracted_assets/index.json
```

---

## 6. Catalog Asset Image Conversion

Convert catalog PNG images to optimized JPG format to reduce asset bundle size.

Script: [scripts/convert_assets.py](file:///c:/Users/jean/DEV/repositories/taleweaver/scripts/convert_assets.py)

```bash
# Convert PNG images to JPEG in backend/static/assets/catalog/
poetry run python scripts/convert_assets.py
```

---

## 7. Agent Skill Bundling & Verification

Bundle agent skills (e.g. `taleweaver-adventure-concept-creator`) with companion documentation specs, generating `package.json` and `manifest.json` with SHA-256 checksums, and exporting distribution archives.

Script: [scripts/bundle_skill.py](file:///c:/Users/jean/DEV/repositories/taleweaver/scripts/bundle_skill.py)

```bash
# Copy companion docs into the skill and regenerate package.json + manifest.json
poetry run python scripts/bundle_skill.py --skill taleweaver-adventure-concept-creator

# Verify only (docs up to date, checksums, references); exits 1 on errors, writes nothing
poetry run python scripts/bundle_skill.py --check

# Export a verified bundle to dist/ (tar.gz or zip)
poetry run python scripts/bundle_skill.py --export-archive tar.gz --output dist/
```

Example output:

```text
Bundled taleweaver-adventure-concept-creator 1.0.0 (7 files)
WARNING: docs/scripting_engine.md: link not bundled: in_game_debugging.md
Check passed.
WARNING: docs/scripting_engine.md: link not bundled: in_game_debugging.md
Check passed.
Exported dist/taleweaver-adventure-concept-creator-1.0.0.tar.gz
```

*(Note: `link not bundled` warnings are informational. Bundled docs are exact copies of the repo docs, so links to docs outside the bundle stay unresolved. Only errors fail the check or block an export.)*
