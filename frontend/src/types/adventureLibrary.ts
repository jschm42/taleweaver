/**
 * Adventure library API contract.
 * Mirrors backend/services/adventure_library/models.py and
 * backend/api/routes/adventures/library.py.
 */

/** One adventure as listed in the repository's `library.json` (`LibraryEntry`). */
export interface AdventureCatalogEntry {
  id: string
  slug: string
  title: string
  teaser: string
  version: string
  author: string
  language: string
  license: string
  cover: string | null
  size_bytes: number
  /** No longer up to the current standard; still installable, hidden unless the user opts in. */
  deprecated: boolean
  /** Manifest format version of adventure.adv (from the index or the file header); null if unknown. */
  format_version?: string | null
  files: string[]
}

/** A library entry merged with the caller's install state (`LibraryItemView`). */
export interface AdventureLibraryItem {
  entry: AdventureCatalogEntry
  cover_url: string | null
  installed_version: string | null
  update_available: boolean
}

/** Response of `GET /library/catalog` and `POST /library/refresh`. */
export interface AdventureCatalogResponse {
  items: AdventureLibraryItem[]
  stale: boolean
}

/** Response of `POST /library/install`. */
export interface AdventureInstallResponse {
  template_id: string | null
  version: string
}
