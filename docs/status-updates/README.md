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
4. **Short posts, one topic each.** Target 250–450 words and one idea per post.
   A build with several new features becomes a series of small posts, not one
   long one — readers skim Discussions, and a focused post is easier to link,
   quote and reply to. Everything else waits in [`backlog.md`](backlog.md).
5. **Screenshots come from the running instance**, not from mocks. Every image
   in a post must be traceable to a real headless browser session against
   `https://127.0.0.1:5173`.
6. **Draft status lives in the frontmatter** (`status: draft|approved|published`)
   together with the discussion URL once published.
7. **Merging is not publishing.** A merged PR only puts the draft on `main`; the
   discussion is a separate, explicit step (see *Publishing*).

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

Nothing posts automatically — there is no workflow that watches `main`. Merging
the PR that contains the draft is only the point where the text and the images
become reachable at their `raw.githubusercontent.com` URLs, which is why the post
must be published *after* the merge, never before.

Publishing is one explicit step, done only on Jean's go:

1. `status: approved` in the frontmatter, body copy final.
2. Post the body (without the YAML block) as a new discussion:

   ```bash
   gh api graphql -f query='
     mutation($repo:ID!, $cat:ID!, $title:String!, $body:String!) {
       createDiscussion(input:{repositoryId:$repo, categoryId:$cat, title:$title, body:$body}) {
         discussion { url number }
       }
     }' \
     -f repo=REPO_ID -f cat=DIC_kwDOSAfRcM4C8vKp \
     -f title='...' -F body=@body.md
   ```

   `Announcements` is `DIC_kwDOSAfRcM4C8vKp` in this repository; the repo node ID
   comes from `gh api graphql -f query='{repository(owner:"jschm42",name:"taleweaver"){id}}'`.
3. Set `status: published` and the returned URL as `discussion_url`, and move the
   item in [`backlog.md`](backlog.md) to *published*. That commit is what makes
   the next update's `since_commit` meaningful.
