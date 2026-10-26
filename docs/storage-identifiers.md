# Adventure identifiers and titles

New automatically allocated adventures, sessions, imports and copies use UUIDs.
Titles remain display text and may contain Cyrillic, Japanese, Arabic, accents or
emoji without becoming directory names. A long title does not lengthen its ID.

Existing IDs, saved sessions and asset directories are not renamed or migrated.
Legacy Unicode IDs remain accepted by the same path-containment checks; separators,
traversal, hidden control characters and escaping symlinks remain rejected.
Visual uploads and reuse also accept validated legacy Unicode IDs and filenames.
Downloads encode Unicode filenames using the HTTP extended filename parameter.

These identifiers have different purposes:

- A local template/session UUID identifies one installed adventure or playthrough.
- `origin_id` identifies a published adventure across installations and versions.
- A catalog `slug` addresses a folder in the public repository; it is separate
  from both the display title and the local UUID.

The catalog's slug rules and existing explicitly supplied import identifiers are
unchanged. This change requires no database migration.
