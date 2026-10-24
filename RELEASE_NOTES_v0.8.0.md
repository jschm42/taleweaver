# TaleWeaver v0.8.0: The Adventure Library Release

**TaleWeaver v0.8.0** introduces the **Adventure Library**: published adventures are no longer shipped inside the application repository but are browsed and downloaded on demand straight from the portal.

---

## 🌟 Major Highlights

### 📚 1. Adventure Library

* **Browse & Download from the Portal**:
  * A new library dialog lists every adventure in the adventures repository [`jschm42/taleweaver-adventures`](https://github.com/jschm42/taleweaver-adventures), with cover, teaser, version and size.
  * Select one or more adventures and install them; they are installed one after another and the card being installed is marked.
  * Installed adventures are recognised by their identity (`origin_id`), so the dialog shows what is already installed and when a newer version is available.
* **Straight from the Repository**:
  * Adventures are stored unpacked in the adventures repository and listed in its `library.json`. The server fetches the listed files over HTTPS from that repository, assembles the bundle and runs the regular importer with its size and manifest checks.
  * The server never fetches a URL supplied by the browser; every file path from the index is validated before it is requested.
* **Works Offline**:
  * The index is cached locally; without network access the dialog falls back to the last known index instead of failing.
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

The `adventures/samples/` folder is **still part of this release**. It is scheduled for removal once every sample has been published to the adventure library and is listed in its index.

---

## 🐳 Docker & CI

* `scripts/docker-setup.sh` no longer claims that example adventures are imported automatically and points to the library instead.
* `ADVENTURE_LIBRARY_URL` points at the adventures repository's raw content (default: `https://raw.githubusercontent.com/jschm42/taleweaver-adventures/main`); override it to use a fork or mirror.

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
