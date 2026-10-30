---
title: "Status Update — Installing published adventures from inside the game"
date: 2026-10-30
category: Announcements
status: draft
version: v0.7.0-beta
since_commit: v0.6.0-beta
images:
  - screenshots/library-archive.jpg
  - screenshots/library-catalog.jpg
discussion_url:
---

# Installing published adventures from inside the game

**TaleWeaver v0.7.0-beta** · October 2026

Getting a published adventure into TaleWeaver used to mean finding an `.adz` file
and importing it by hand. As of this build the game has a catalog browser: pick
an adventure, hit download, and it lands in your local library ready to play.

![Browsing the catalog](https://raw.githubusercontent.com/jschm42/taleweaver/main/docs/screenshots/library-catalog.jpg)

*Browse Library* opens the catalog: ten adventures, 102.6 MB in total, with
covers, teasers, creators, sizes, and a `DOWNLOADED` badge once a pack is
already local.

![The Archive with a downloaded adventure](https://raw.githubusercontent.com/jschm42/taleweaver/main/docs/screenshots/library-archive.jpg)

The Library view lists everything installed locally with cover art, version,
genre, tone and play style. The second card is *Crashed on Proxima-9*, pulled
from the catalog a single click earlier.

## How it works

The catalog is served straight from
[`jschm42/taleweaver-adventures`](https://github.com/jschm42/taleweaver-adventures)
— a `library.json` index plus one directory per adventure containing
`adventure.adv`, its assets and cover art. No release assets, no zip juggling on
the client side: the app resolves the index, downloads the pack, verifies it and
registers it in the local database. Adding an adventure to the catalog is a
normal pull request against the adventures repo.

## Known issues

- **All current catalog entries are flagged `DEPRECATED`.** Their manifests
  declare format `1.3`, while the app treats anything below `1.3.1` as stale.
  They download and play fine — the app upgrades them on import — but the
  catalog hides them behind *Show deprecated* until the packs are re-exported
  with the current format version.
- Download progress is reported per pack, not per byte; large packs look like
  they stall for a few seconds before the card flips to `DOWNLOADED`.

## Next

A short post on the sandboxed scripting engine, then a catalog re-export so the
deprecation badges go away.
