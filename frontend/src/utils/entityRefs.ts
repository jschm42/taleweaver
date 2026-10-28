/**
 * In-game display of entity references (`##ITEM_ID`) in authored and generated text.
 *
 * The game view registers the session's entities; references then render with the entity's
 * name. Unknown ids fall back to a readable form of the id ("BRASS_ROD" → "Brass Rod").
 * The editor keeps showing raw ids (see formatObjectIds in editor_utils).
 */
import { shallowRef } from 'vue'

const ENTITY_REF = /##([A-Za-z0-9_-]+)/g

// Replaced as a whole on every update so renders that read it re-run.
const entityNames = shallowRef<Map<string, string>>(new Map())

type NamedEntity = { id?: unknown; name?: unknown }

/**
 * Replaces the registry: the session's id → name map (all scenes), completed by entity lists
 * such as the current scene and the inventory (items created during play).
 */
export function registerEntityNames(
  nameMap: Record<string, unknown> | null | undefined,
  ...lists: (NamedEntity[] | null | undefined)[]
): void {
  const names = new Map<string, string>()
  for (const [id, name] of Object.entries(nameMap || {})) {
    const label = String(name ?? '').trim()
    if (id && label) names.set(id.toUpperCase(), label)
  }
  for (const list of lists) {
    for (const entity of list || []) {
      const id = String(entity?.id ?? '').trim()
      const name = String(entity?.name ?? '').trim()
      if (id && name) names.set(id.toUpperCase(), name)
    }
  }
  entityNames.value = names
}

function humanizeId(id: string): string {
  return id
    .replace(/[_-]+/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim()
}

export function entityRefName(id: string): string {
  return entityNames.value.get(id.toUpperCase()) || humanizeId(id)
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

/** Plain text with every reference replaced by the entity name. */
export function resolveEntityRefsText(text: string | null | undefined): string {
  if (!text) return ''
  return text.replace(ENTITY_REF, (_match, id: string) => entityRefName(id))
}

/** Already-escaped HTML: references become a name tag with the given class. */
export function renderEntityRefsHtml(escapedHtml: string, tagClass: string): string {
  return escapedHtml.replace(
    ENTITY_REF,
    (_match, id: string) => `<span class="${tagClass}">${escapeHtml(entityRefName(id))}</span>`,
  )
}

/** In-game counterpart of formatObjectIds: escaped text with references shown by name. */
export function formatEntityRefs(text: string | null | undefined): string {
  if (!text) return ''
  return renderEntityRefsHtml(escapeHtml(text.replace(/\n/g, '\n')), 'object-id-tag')
}
