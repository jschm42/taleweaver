# TaleWeaver v0.8.0: The Adventure Library Release

**TaleWeaver v0.8.0** introduces the **Adventure Library**: published adventures are no longer shipped inside the application repository but are browsed and downloaded on demand straight from the portal.

---

## 🌟 Major Highlights

### 📚 1. Adventure Library

* **Browse & Download from the Portal**:
  * A new library dialog lists every adventure published to the distribution repository [`jschm42/taleweaver-adventures`](https://github.com/jschm42/taleweaver-adventures), with cover, teaser, version and size.
  * Select one or more adventures and download them; progress is shown per adventure and downloads can be cancelled.
  * Installed adventures are recognised by their identity (`origin_id`), so the dialog shows what is already installed and when a newer version is available.
* **Verified Downloads**:
  * Every bundle is checked against the size and SHA-256 hash published in the catalog before it is imported; nothing is installed unless it matches.
  * Downloads only ever come from allowlisted HTTPS hosts, and the server never fetches a URL supplied by the browser.
* **Works Offline**:
  * The catalog is cached locally; without network access the dialog falls back to the last known catalog instead of failing.
  * The default adventure (*The Architect*) is still bundled, so a first run works without network access.

---

## ⚠️ Migration Notes

### Example adventure endpoints retired

* `GET /api/adventures/check-examples` and `POST /api/adventures/import-examples` now return **`410 Gone`** with:
  ```json
  {"detail": "Example adventures are now provided by the adventure library."}
  ```
  Use the `/api/adventures/library/*` endpoints instead.
* For one release cycle the old behaviour can be restored with `ADVENTURE_LEGACY_EXAMPLES_ENABLED=true`. This flag will be removed in a future release.

### Previously imported examples keep working

Example adventures you imported in an earlier version **keep working unchanged**. Imported adventures live in your user database, not in the repository, so nothing about them depends on the bundled sample files.

### `adventures/samples/` is scheduled for removal

The `adventures/samples/` folder is **still part of this release**. It is scheduled for removal once every sample has been published to the adventure library and is listed in its catalog.

---

## 🐳 Docker & CI

* Set `TALEWEAVER_PREFETCH_ADVENTURES=1` to pre-download all compatible library adventures on first boot (off by default).
  * Runs only on a first boot (no adventures installed yet) and in the background, so startup is never delayed.
  * Adventures are installed into the first admin account's library; if no admin exists yet, the prefetch is skipped with a warning in the log.
* `scripts/docker-setup.sh` no longer claims that example adventures are imported automatically and points to the library instead.

---

## 🚀 Getting Started with v0.8.0

### Upgrading Backend & Database
```bash
# Pull latest code
git pull origin main

# Activate your virtual environment
.\venv\Scripts\activate   # Windows
source venv/bin/activate  # Linux/macOS

# Apply database migrations
alembic upgrade head
```

### Upgrading Frontend
```bash
cd frontend
npm install
npm run build # or npm run dev
```
