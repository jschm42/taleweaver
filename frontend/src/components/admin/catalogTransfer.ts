/**
 * Restore, import and export of the admin catalogs (image styles, tones, narrator personas).
 * Pure functions; the Admin pages ask for confirmation and save the result.
 *
 * File format: { format: "taleweaver-catalog", version: 1, type, items }.
 * A plain array of entries is accepted on import too.
 */
import type { CatalogTile } from '@/types'

export type CatalogKind = 'styles' | 'tones' | 'personas'

export const CATALOG_FILE_FORMAT = 'taleweaver-catalog'

/** Fields every catalog entry has; styles and tones add image_url, personas add sample. */
export interface CatalogEntry {
  id: string
  name: string
  description?: string
  instruction?: string
  image_url?: string | null
  sample?: string
}

export interface CatalogFile<T extends CatalogEntry = CatalogEntry> {
  format: typeof CATALOG_FILE_FORMAT
  version: 1
  type: CatalogKind
  items: T[]
}

export interface MergeResult<T> {
  items: T[]
  added: number
  replaced: number
}

const PLURAL: Record<CatalogKind, string> = { styles: 'image styles', tones: 'tones', personas: 'narrator personas' }

export function catalogPlural(type: CatalogKind): string {
  return PLURAL[type]
}

function slugify(value: string): string {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') || 'item'
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

/** A valid style or tone entry or null (an entry needs a name; the id falls back to the slugged name). */
export function normalizeTile(raw: unknown): CatalogTile | null {
  if (!raw || typeof raw !== 'object') return null
  const entry = raw as Record<string, unknown>
  const name = text(entry.name)
  if (!name) return null
  return {
    id: text(entry.id) || slugify(name),
    name,
    description: text(entry.description),
    instruction: text(entry.instruction),
    image_url: text(entry.image_url) || null,
  }
}

/** A valid narrator persona or null (a persona needs a name and an instruction). */
export function normalizePersona(raw: unknown): CatalogEntry | null {
  if (!raw || typeof raw !== 'object') return null
  const entry = raw as Record<string, unknown>
  const name = text(entry.name)
  const instruction = text(entry.instruction)
  if (!name || !instruction) return null
  return { id: text(entry.id) || slugify(name), name, description: text(entry.description), instruction, sample: text(entry.sample) }
}

function normalizerFor(type: CatalogKind): (raw: unknown) => CatalogEntry | null {
  return type === 'personas' ? normalizePersona : normalizeTile
}

/** Entries of `incoming` replace entries with the same id; new ones are appended. Others stay. */
export function mergeCatalog<T extends { id: string }>(current: T[], incoming: T[]): MergeResult<T> {
  const items = current.map((item) => ({ ...item }))
  const indexById = new Map(items.map((item, index) => [item.id, index]))
  let added = 0
  let replaced = 0
  for (const entry of incoming) {
    const index = indexById.get(entry.id)
    if (index === undefined) {
      indexById.set(entry.id, items.length)
      items.push({ ...entry })
      added += 1
      continue
    }
    items[index] = { ...entry }
    replaced += 1
  }
  return { items, added, replaced }
}

export function buildCatalogFile<T extends CatalogEntry>(type: CatalogKind, items: T[]): CatalogFile<T> {
  return { format: CATALOG_FILE_FORMAT, version: 1, type, items: items.map((item) => ({ ...item })) }
}

export function catalogFileName(type: CatalogKind): string {
  return `taleweaver-${PLURAL[type].replace(/ /g, '-')}.json`
}

/** Parses an exported file. Throws an Error with a user-facing message when it does not fit. */
export function parseCatalogFile(content: string, expected: CatalogKind): CatalogEntry[] {
  let data: unknown
  try {
    data = JSON.parse(content)
  } catch {
    throw new Error('The file is not valid JSON.')
  }
  const file = data as Partial<CatalogFile> | null
  const isWrapped = !!file && !Array.isArray(file) && typeof file === 'object'
  if (isWrapped && file.type && file.type !== expected) {
    throw new Error(`The file holds ${PLURAL[file.type] || file.type}, not ${PLURAL[expected]}.`)
  }
  const rawItems = isWrapped ? file.items : data
  if (!Array.isArray(rawItems)) throw new Error('The file has no catalog entries.')
  const items = rawItems.map(normalizerFor(expected)).filter((item): item is CatalogEntry => item !== null)
  if (!items.length) {
    const needs = expected === 'personas' ? 'a name and an instruction' : 'a name'
    throw new Error(`The file has no valid entries (each entry needs ${needs}).`)
  }
  return items
}

/** Offers a JSON file for download. */
export function downloadJson(filename: string, data: unknown): void {
  const url = URL.createObjectURL(new Blob([`${JSON.stringify(data, null, 2)}\n`], { type: 'application/json;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 100)
}
