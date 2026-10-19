# TaleWeaver Entity Bundle (`.twe`)

A `.twe` file transfers a single **protagonist**, **NPC**, or **item** between adventures, including its image. Like `.adz`, it is a plain ZIP archive.

## Layout

```
entity.json         # manifest (required)
assets/image.<ext>  # optional image (png, jpg, webp)
```

## `entity.json`

```json
{
  "format": "TaleWeaverEntity",
  "version": 1,
  "kind": "npc",
  "exported_at": "2026-10-18T12:00:00+00:00",
  "source": { "adventure_title": "The Alchemist's Folly" },
  "entity": { "id": "OLD_LIBRARIAN", "name": "Old Librarian", "description": "...", "hp": 40 },
  "image": "assets/image.png"
}
```

| Field    | Description |
|----------|-------------|
| `kind`   | `protagonist`, `npc`, or `item`. |
| `entity` | NPC/item: the `WorldEntity` columns (without `template_id`, `session_id`, `image_url`). Protagonist: profile, vitals, attributes, `stats` (incl. scripts and special actions), and `status_effects`. |
| `image`  | Path of the image entry inside the ZIP, or `null`. |

## Import Behaviour

Endpoints: `GET /api/adventures/{id}/editor/transfer/protagonist`, `GET /api/adventures/{id}/editor/transfer/entity/{entity_id}`, `POST /api/adventures/{id}/editor/transfer/import`.

- **NPC / item**: always created as a new entity. On an ID clash a suffix is added (`SWORD` → `SWORD_2`). If the original scene does not exist, the entity is placed in the start scene. References to scenes/items that do not exist in the target adventure (`allowed_scenes`, `inventory`, `reveals_item_id`) are removed; missing crafting ingredients are only reported. All adjustments are returned as `warnings`.
- **Protagonist**: replaces the profile, stats, and portrait of the current protagonist. Inventory and equipment stay unchanged, as they reference adventure-specific items.
- Images are checked with Pillow and must be PNG, JPEG, or WEBP. Size limits: 25 MB per bundle file, 20 MB per entry, max. 8 entries.
