---
title: "Status Update — Installing published adventures from inside the game"
date: 2026-10-30
category: Announcements
status: draft
version: v0.7.0-beta
since_commit: v0.6.0-beta
images:
  - screenshots/status-library-archive.jpg
  - screenshots/status-library-download.jpg
discussion_url:
---

# Status Update — Installing published adventures from inside the game

**TaleWeaver v0.7.0-beta** · October 2026

This is the first of a recurring series of build-status posts. Every entry
covers what shipped, what it looks like, and what is broken right now. No
roadmap theatre — screenshots from the running instance.

## What shipped

**The Adventure Library now downloads.** Until recently, getting a published
adventure into TaleWeaver meant finding a `.adz` file and importing it by hand.
As of this build the game has a catalog browser: pick an adventure, hit
download, and it lands in your local library ready to play.

![The Archive with a downloaded adventure](https://raw.githubusercontent.com/jschm42/taleweaver/main/docs/screenshots/status-library-archive.jpg)

The Library view lists everything installed locally with cover art, version,
genre, tone and play style. The second card is *Crashed on Proxima-9*, which was
pulled from the catalog in a single click a minute earlier.

![Browsing the catalog](https://raw.githubusercontent.com/jschm42/taleweaver/main/docs/screenshots/status-library-download.jpg)

*Browse Library* opens the catalog: ten adventures, 102.6 MB in total, with
covers, teasers, creators, sizes and a local badge once an adventure is already
installed (`DOWNLOADED` on the first card).

## How distribution works now

The catalog is served straight from
[`jschm42/taleweaver-adventures`](https://github.com/jschm42/taleweaver-adventures)
— a `library.json` index plus one directory per adventure containing
`adventure.adv`, its assets and cover art. No release assets, no zip juggling on
the client side: the app resolves the index, downloads the pack, verifies it and
registers it in the local database.

That also means adding an adventure to the catalog is a normal pull request
against the adventures repo.

## Also in this build

Everything below shipped with its documentation, so the details are a click away:

- **Sandboxed scripting engine** — event scripts with lifecycle triggers, an
  `init_script` and the `tw` API, authored directly in the World Editor.
  → [`docs/scripting_engine.md`](https://github.com/jschm42/taleweaver/blob/main/docs/scripting_engine.md)
- **World Builder blueprints** — declarative world specs with three control
  levels and a strict-adherence/creative-expansion dial for the generator.
  → [`docs/world-builder-blueprint-manual.md`](https://github.com/jschm42/taleweaver/blob/main/docs/world-builder-blueprint-manual.md)
- **Area-of-effect combat** — special actions now resolve against several
  combatants at once, deterministically and visible in the Battle Chronicle.
  → [`docs/specs/combat-aoe-abilities.md`](https://github.com/jschm42/taleweaver/blob/main/docs/specs/combat-aoe-abilities.md)
- **Entity bundles (`.twe`)** — move a protagonist, NPC or item, image
  included, between adventures.
  → [`docs/specs/entity_bundle_format.md`](https://github.com/jschm42/taleweaver/blob/main/docs/specs/entity_bundle_format.md)
- **Custom LLM endpoints** — point TaleWeaver at any OpenAI-compatible
  endpoint instead of the bundled provider.
  → [`docs/custom-openai-compatible.md`](https://github.com/jschm42/taleweaver/blob/main/docs/custom-openai-compatible.md)
- **Stable identifiers** — adventures, sessions and imports get UUIDs; titles
  stay display text, Cyrillic, Japanese or emoji included.
  → [`docs/storage-identifiers.md`](https://github.com/jschm42/taleweaver/blob/main/docs/storage-identifiers.md)
- **Annotated screenshot gallery** — every major screen, documented.
  → [`docs/SCREENSHOTS.md`](https://github.com/jschm42/taleweaver/blob/main/docs/SCREENSHOTS.md)

## Known issues

- **All current catalog entries are flagged `DEPRECATED`.** Their manifests
  declare format `1.3`, while the app treats anything below `1.3.1` as stale.
  They download and play fine — the app upgrades them on import — but the
  catalog hides them behind *Show deprecated* until the packs are re-exported
  with the current format version.
- Download progress is reported per pack, not per byte; large packs look like
  they stall for a few seconds before the card flips to `DOWNLOADED`.

## Next

Cleanup of the old release-based publishing pipeline, and a re-export of the
catalog so the deprecation badges go away.
