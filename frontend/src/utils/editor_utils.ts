export type VisualKind = 'cover' | 'protagonist' | 'scene' | 'npc' | 'object'

export function fixNewlines(text: string | null | undefined): string {
  if (!text) return ''
  return text.replace(/\\n/g, '\n')
}

export function normalizeEntityType(entity: any): string {
  return String(entity?.entity_type || entity?.type || '').trim().toUpperCase()
}

export function isNpcEntity(entity: any): boolean {
  const kind = normalizeEntityType(entity)
  return kind === 'NPC' || kind === 'CHARACTER'
}

export function isObjectEntity(entity: any): boolean {
  const kind = normalizeEntityType(entity)
  return kind === 'OBJECT' || kind === 'ITEM'
}

export function mergeUniqueById(primary: any[], extra: any[]): any[] {
  const seen = new Set<string>()
  const merged: any[] = []
  for (const item of [...primary, ...extra]) {
    if (!item || !item.id) continue
    if (seen.has(item.id)) continue
    seen.add(item.id)
    merged.push(item)
  }
  return merged
}

export function formatVoiceOption(voice: { name: string; gender?: string; description?: string }): string {
  const detailParts = [voice.gender, voice.description].filter(Boolean)
  if (detailParts.length === 0) return voice.name
  return `${voice.name} (${detailParts.join(', ')})`
}

export function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }
  return `${Math.ceil(bytes / 1024)} KB`
}

export function makeSafeFilename(label: string, ext: string) {
  const safe = (label || 'asset').replace(/[^a-zA-Z0-9 _-]/g, '').trim().replace(/\s+/g, '_')
  return `${safe || 'asset'}.${ext}`
}

export function getImageExtension(imagePath?: string | null) {
  if (!imagePath) {
    return 'png'
  }
  const cleanPath = imagePath.split('?')[0]
  const parts = cleanPath.split('.')
  const ext = parts[parts.length - 1]?.toLowerCase()
  if (!ext || !/^[a-z0-9]+$/.test(ext)) {
    return 'png'
  }
  return ext
}

// Item type helpers for editor
export function itemTypePrefix(itemType: string): string {
  const map: Record<string, string> = {
    DEFAULT: 'ITEM_',
    CONSUMABLE: 'ITEM_',
    WEARABLE: 'ITEM_',
    WEAPON: 'ITEM_',
    CONSTRUCTABLE: 'RECIPE_',
    READABLE: 'ITEM_',
    CONTAINER: 'CON_',
    SWITCH: 'SW_',
  }
  return map[String(itemType || 'DEFAULT').toUpperCase()] || 'ITEM_'
}

/**
 * Item type as shown to users. CONSTRUCTABLE stays the stored value (database, .adv files,
 * blueprints, LLM prompts) but is presented as "RECIPE".
 */
export function itemTypeLabel(itemType?: string | null): string {
  const type = String(itemType || 'DEFAULT').toUpperCase()
  return type === 'CONSTRUCTABLE' ? 'RECIPE' : type
}

export function sanitizeEditorIdToken(token: string): string {
  return token.replace(/[^A-Za-z0-9_]/g, '').toUpperCase()
}

export function buildPrefixedEditorId(name: string, prefix: string): string {
  if (!name || !prefix) return ''
  const base = name
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/\s+/g, '_')
    .toUpperCase()
  if (!base) return ''
  return `${sanitizeEditorIdToken(prefix)}${base}`
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export function formatObjectIds(text: string | null | undefined): string {
  if (!text) return ''
  const withNewlines = fixNewlines(text)
  const escaped = escapeHtml(withNewlines)
  return escaped.replace(/##([A-Za-z0-9_-]+)/g, '<span class="object-id-tag">$1</span>')
}

export function hasAnyScript(entity: any, topLevelScripts?: any[]): boolean {
  if (!entity || typeof entity !== 'object') return false

  // 1. Direct inline script fields on entity
  for (const [key, val] of Object.entries(entity)) {
    if (typeof val === 'string' && val.trim()) {
      if (key.endsWith('_script') || key === 'unlock_expression' || key === 'guard_expression') {
        return true
      }
    }
  }

  // 2. Inline script fields stored inside metadata / metadata_json
  const metadata = (entity.metadata_json && typeof entity.metadata_json === 'object')
    ? entity.metadata_json
    : ((entity.metadata && typeof entity.metadata === 'object') ? entity.metadata : null)

  if (metadata) {
    for (const [key, val] of Object.entries(metadata)) {
      if (typeof val === 'string' && val.trim()) {
        if (key.endsWith('_script') || key === 'unlock_expression' || key === 'guard_expression') {
          return true
        }
      }
    }
  }

  // 3. Explicit scripts array attached to entity
  if (Array.isArray(entity.scripts) && entity.scripts.length > 0) {
    return true
  }

  // 4. Targeted by top-level adventure scripts
  if (Array.isArray(topLevelScripts) && entity.id) {
    const entityId = String(entity.id).trim().toUpperCase()
    for (const sc of topLevelScripts) {
      if (!sc) continue
      const target = String(sc.target_id || sc.target || '').trim().toUpperCase()
      if (target && target === entityId) {
        return true
      }
    }
  }

  return false
}