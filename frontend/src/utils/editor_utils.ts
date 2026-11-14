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

export const MAX_EDITOR_ID_LENGTH = 20

export const EDITOR_ID_PREFIXES = {
  SCENE: 'SCENE_',
  DYN_SCENE: 'DYN_',
  ZONE: 'ZONE_',
  NPC: 'NPC_',
  OBJECT: 'ITEM_',
  STANDARD: 'ITEM_',
  CONSUMABLE: 'ITEM_',
  WEARABLE: 'GEAR_',
  WEAPON: 'WP_',
  READABLE: 'DOC_',
  CONTAINER: 'CON_',
  SWITCH: 'SW_',
  COMPLEX_SWITCH: 'CSW_',
  RECIPE: 'RCP_',
  SEQUENCE: 'SEQ_',
  RULE: 'RULE_',
  SCRIPT: 'SCR_',
  TALENT: 'TAL_',
  ATTACK: 'ATK_',
  AWARD: 'AWD_',
} as const

export {
  buildDynamicPlaceholderSceneId,
  generateDeterministicPseudoname,
} from './dynamicPseudoname'

// Item type helpers for editor
export function itemTypePrefix(itemType: string): string {
  const map: Record<string, string> = {
    DEFAULT: EDITOR_ID_PREFIXES.STANDARD,
    CONSUMABLE: EDITOR_ID_PREFIXES.CONSUMABLE,
    WEARABLE: EDITOR_ID_PREFIXES.WEARABLE,
    WEAPON: EDITOR_ID_PREFIXES.WEAPON,
    CONSTRUCTABLE: EDITOR_ID_PREFIXES.RECIPE,
    READABLE: EDITOR_ID_PREFIXES.READABLE,
    CONTAINER: EDITOR_ID_PREFIXES.CONTAINER,
    CONTAINER_SWITCH: EDITOR_ID_PREFIXES.COMPLEX_SWITCH,
    COMPLEX_SWITCH: EDITOR_ID_PREFIXES.COMPLEX_SWITCH,
    SWITCH: EDITOR_ID_PREFIXES.SWITCH,
  }
  return map[String(itemType || 'DEFAULT').toUpperCase()] || EDITOR_ID_PREFIXES.OBJECT
}

export function sanitizeEditorIdToken(token: string): string {
  return String(token || '').replace(/[^A-Za-z0-9_]/g, '').toUpperCase()
}

export function sanitizeEditorId(raw: string, maxLen = MAX_EDITOR_ID_LENGTH): string {
  const safeMax = Math.max(1, Math.floor(Number(maxLen) || MAX_EDITOR_ID_LENGTH))
  return String(raw || '')
    .toUpperCase()
    .replace(/[\s-]+/g, '_')
    .replace(/[^A-Z0-9_]/g, '')
    .slice(0, safeMax)
}

export function isValidEditorId(raw: string, maxLen = MAX_EDITOR_ID_LENGTH): boolean {
  const safeMax = Math.max(1, Math.floor(Number(maxLen) || MAX_EDITOR_ID_LENGTH))
  const trimmed = String(raw || '').trim()
  if (!trimmed || trimmed.length > safeMax) return false
  return /^[A-Z0-9_]+$/.test(trimmed)
}

function normalizeSourceNameForId(sourceName: string): string {
  return String(sourceName || '')
    .replace(/ä/g, 'ae')
    .replace(/ö/g, 'oe')
    .replace(/ü/g, 'ue')
    .replace(/Ä/g, 'AE')
    .replace(/Ö/g, 'OE')
    .replace(/Ü/g, 'UE')
    .replace(/ß/g, 'ss')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function normalizePrefixToken(prefix: string, maxLen: number): string {
  const cleaned = sanitizeEditorId(prefix, Math.max(1, maxLen - 2))
  if (!cleaned) return ''
  return cleaned.endsWith('_') ? cleaned : `${cleaned}_`.slice(0, Math.max(1, maxLen - 2))
}

export interface GenerateEditorIdOptions {
  prefix?: string
  sourceName?: string
  takenIds?: Iterable<string>
  maxLen?: number
  randomFallback?: boolean
}

export function generateEditorId(options: GenerateEditorIdOptions = {}): string {
  const safeMax = Math.max(4, Math.floor(Number(options.maxLen) || MAX_EDITOR_ID_LENGTH))
  const cleanPrefix = normalizePrefixToken(options.prefix || '', safeMax)
  const bodyBudget = Math.max(1, safeMax - cleanPrefix.length)

  let body = normalizeSourceNameForId(options.sourceName || '')
  if (!body) {
    if (options.randomFallback === false) return ''
    body = Math.random().toString(36).slice(2, 8).toUpperCase() || 'ITEM'
  }

  const taken = new Set<string>()
  if (options.takenIds) {
    for (const id of options.takenIds) {
      const normalized = String(id || '').trim().toUpperCase()
      if (normalized) taken.add(normalized)
    }
  }

  const buildCandidate = (rawBody: string, suffix = ''): string => {
    const suffixLen = suffix.length
    const avail = Math.max(1, bodyBudget - suffixLen)
    const clippedBody = rawBody.slice(0, avail).replace(/_+$/g, '') || rawBody.slice(0, avail)
    return `${cleanPrefix}${clippedBody}${suffix}`.slice(0, safeMax)
  }

  const primary = buildCandidate(body)
  if (!taken.has(primary)) return primary

  for (let counter = 2; counter <= 99; counter += 1) {
    const candidate = buildCandidate(body, `_${counter}`)
    if (!taken.has(candidate)) return candidate
  }

  for (let attempt = 0; attempt < 20; attempt += 1) {
    const rnd = Math.random().toString(36).slice(2, 6).toUpperCase()
    const candidate = buildCandidate(body, `_${rnd}`)
    if (!taken.has(candidate)) return candidate
  }

  return buildCandidate(Math.random().toString(36).slice(2, 8).toUpperCase())
}

export function buildPrefixedEditorId(
  name: string,
  prefix: string,
  maxLen = MAX_EDITOR_ID_LENGTH,
): string {
  if (!name || !prefix) return ''
  return generateEditorId({
    prefix,
    sourceName: name,
    maxLen,
    randomFallback: false,
  })
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