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
