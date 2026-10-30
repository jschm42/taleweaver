# Status Updates

Recurring, screenshot-driven progress posts for GitHub Discussions.

## Rules

1. **Nothing is posted without review.** A draft exists as a file in this
   directory first. Publishing to GitHub Discussions happens only after Jean has
   read the draft and explicitly approved it in chat.
2. **`docs/` is the primary source.** Documentation is updated in the same
   commits as the features, so the doc delta since the last update decides the
   scope of a post — not the commit subjects. Helper:
   `~/.hermes/profiles/tolkien/skills/software-development/taleweaver-status-update/scripts/doc_delta.py`.
3. **One file per update**: `YYYY-MM-DD-<slug>.md`.
4. **Screenshots come from the running instance**, not from mocks. Every image
   in a post must be traceable to a real headless browser session against
   `https://127.0.0.1:5173`.
5. **Draft status lives in the frontmatter** (`status: draft|approved|published`)
   together with the discussion URL once published.

## Frontmatter

```yaml
---
title: "..."            # discussion title
date: YYYY-MM-DD        # publication target
category: Announcements # GitHub Discussions category
status: draft           # draft | approved | published
version: v0.7.0-beta    # TaleWeaver version the screenshots show
since_commit: v0.6.0-beta  # docs were diffed from here; next update starts here
images:                 # relative to docs/
  - screenshots/foo.jpg
discussion_url:         # filled in after publishing
---
```

## Screenshots

Follow the existing gallery conventions from [`docs/SCREENSHOTS.md`](../SCREENSHOTS.md):

- full size JPG, 1872 px wide → `docs/screenshots/<name>.jpg`
- thumbnail, 936 px wide → `docs/screenshots/small/<name>.jpg`
- captured at viewport 1600×1000 with `deviceScaleFactor: 2` (3200×2000 raw)
- posts reference them as
  `https://raw.githubusercontent.com/jschm42/taleweaver/main/docs/screenshots/<name>.jpg`
  so the images render in Discussions without re-uploading them

Images must be committed and pushed before the discussion is posted, otherwise
GitHub shows broken links.

## Publishing

`status: approved` + explicit go from Jean → create the discussion in the
`Announcements` category (`gh api graphql`, `createDiscussion`), then set
`status: published` and `discussion_url` in the frontmatter.
