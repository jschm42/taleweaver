export type HoverEntity = Record<string, any>

function toNumberOrNull(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return null
}

function firstNumeric(...values: unknown[]): number | null {
  for (const value of values) {
    const parsed = toNumberOrNull(value)
    if (parsed !== null) return parsed
  }
  return null
}

export function hasNonZero(value: unknown): boolean {
  const parsed = toNumberOrNull(value)
  return parsed !== null && parsed !== 0
}

export function fixNewlines(text: string | null | undefined): string {
  if (!text) return ''
  return text.replace(/\\n/g, '\n')
}

export function normalizeHoverEntity(entity: any): any {
  if (!entity || typeof entity !== 'object') return entity

  const normalized: HoverEntity = { ...entity }
  const metadata = (normalized.metadata_json && typeof normalized.metadata_json === 'object') ? normalized.metadata_json : {}
  const embeddedStats = (metadata.stat_modifiers && typeof metadata.stat_modifiers === 'object') ? metadata.stat_modifiers : {}
  const directStats = (normalized.stat_modifiers && typeof normalized.stat_modifiers === 'object') ? normalized.stat_modifiers : {}

  const stat = (...keys: string[]) => firstNumeric(
    ...keys.map((k) => normalized[k]),
    ...keys.map((k) => metadata[k]),
    ...keys.map((k) => embeddedStats[k]),
    ...keys.map((k) => directStats[k]),
  )

  if (normalized.stat_modifier_strength == null) {
    const value = stat('stat_modifier_strength', 'strength', 'str', 'STR')
    if (value != null) normalized.stat_modifier_strength = value
  }
  if (normalized.stat_modifier_dexterity == null) {
    const value = stat('stat_modifier_dexterity', 'stat_modifier_agility', 'dexterity', 'agility', 'dex', 'DEX', 'AGI')
    if (value != null) normalized.stat_modifier_dexterity = value
  }
  if (normalized.stat_modifier_intelligence == null) {
    const value = stat('stat_modifier_intelligence', 'intelligence', 'int', 'INT')
    if (value != null) normalized.stat_modifier_intelligence = value
  }
  if (normalized.stat_modifier_wisdom == null) {
    const value = stat('stat_modifier_wisdom', 'wisdom', 'wis', 'WIS')
    if (value != null) normalized.stat_modifier_wisdom = value
  }
  if (normalized.stat_modifier_charisma == null) {
    const value = stat('stat_modifier_charisma', 'charisma', 'cha', 'CHA')
    if (value != null) normalized.stat_modifier_charisma = value
  }
  if (normalized.stat_modifier_armor_class == null) {
    const value = stat('stat_modifier_armor_class', 'armor_class', 'ac', 'AC')
    if (value != null) normalized.stat_modifier_armor_class = value
  }

  const effects = (metadata.effects && typeof metadata.effects === 'object') ? metadata.effects : {}
  if (normalized.hp_change == null) {
    const value = firstNumeric(normalized.hp_change, metadata.hp_change, metadata.health_change, effects.hp, effects.health)
    if (value != null) normalized.hp_change = value
  }
  if (normalized.mana_change == null) {
    const value = firstNumeric(normalized.mana_change, metadata.mana_change, effects.mana)
    if (value != null) normalized.mana_change = value
  }
  if (normalized.stamina_change == null) {
    const value = firstNumeric(normalized.stamina_change, metadata.stamina_change, effects.stamina, effects.energy)
    if (value != null) normalized.stamina_change = value
  }

  return normalized
}

export function isConsumableEntity(entity: any): boolean {
  if (!entity) return false
  const itemType = String(entity.item_type || '').toUpperCase()
  return itemType === 'CONSUMABLE' || entity.hp_change != null || entity.mana_change != null || entity.stamina_change != null
}
