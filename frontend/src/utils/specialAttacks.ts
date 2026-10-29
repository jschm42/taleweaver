import type {
  CombatStat,
  NormalizedSpecialAttack,
  SpecialAttack,
  SpecialCategory,
  SpecialEffect,
  SuccessStat,
  TargetScope,
} from '@/types'

export const SPECIAL_CATEGORIES: SpecialCategory[] = ['MAGIC', 'MELEE', 'RANGED', 'SOCIAL', 'OTHER']
export const SUCCESS_STATS: SuccessStat[] = ['strength', 'dexterity', 'intelligence', 'wisdom', 'charisma']
export const EFFECT_STATS: CombatStat[] = [
  'hp', 'mana', 'stamina', 'strength', 'dexterity', 'intelligence', 'wisdom', 'charisma', 'armor_class',
]
export const AMOUNT_PATTERN = /^[+-]?(\d+d\d+([+-]\d+)?|\d+)$/i

export const CATEGORY_META: Record<SpecialCategory, { label: string; icon: string; tone: string }> = {
  MAGIC: { label: 'Magic', icon: 'ra-crystal-wand', tone: 'violet' },
  MELEE: { label: 'Melee', icon: 'ra-crossed-swords', tone: 'orange' },
  RANGED: { label: 'Ranged', icon: 'ra-arrow-cluster', tone: 'green' },
  SOCIAL: { label: 'Social', icon: 'ra-speech-bubbles', tone: 'pink' },
  OTHER: { label: 'Other', icon: 'ra-scroll-unfurled', tone: 'cyan' },
}

export const STAT_SHORT: Record<CombatStat, string> = {
  hp: 'HP',
  mana: 'MP',
  stamina: 'STA',
  strength: 'STR',
  dexterity: 'DEX',
  intelligence: 'INT',
  wisdom: 'WIS',
  charisma: 'CHA',
  armor_class: 'AC',
}

const CATEGORY_DEFAULT_STAT: Record<SpecialCategory, SuccessStat> = {
  MAGIC: 'intelligence',
  MELEE: 'strength',
  RANGED: 'dexterity',
  SOCIAL: 'charisma',
  OTHER: 'wisdom',
}

function legacyEffects(action: SpecialAttack): SpecialEffect[] {
  const raw = String(action.damage_value || '10').replace(/\s/g, '').replace(/^[+-]/, '')
  const value = AMOUNT_PATTERN.test(raw) ? raw : '10'
  if (action.action_type === 'ATTACK') return [{ target: 'target', stat: 'hp', amount: `-${value}` }]
  if (action.action_type === 'HEAL') return [{ target: 'self', stat: 'hp', amount: `+${value}` }]
  return []
}

/** Client-side mirror of the backend normalization, used for display and editor previews. */
export function normalizeSpecialAttack(action: SpecialAttack): NormalizedSpecialAttack {
  const category = action.category && SPECIAL_CATEGORIES.includes(action.category) ? action.category : 'MAGIC'
  const costType = action.cost_type === 'stamina' ? 'stamina' : 'mana'
  const legacyCost = costType === 'mana' ? Number(action.mana_cost || 0) : 0
  const effects = (action.effects ?? []).filter((e) => EFFECT_STATS.includes(e.stat) && AMOUNT_PATTERN.test(e.amount))
  const finalEffects = effects.length ? effects : legacyEffects(action)
  const scope = action.target_scope && TARGET_SCOPES.includes(action.target_scope) ? action.target_scope : 'SINGLE'
  return {
    ...action,
    category,
    cost_type: costType,
    cost: Math.max(0, Number(action.cost ?? legacyCost) || 0),
    success_stat: action.success_stat ?? CATEGORY_DEFAULT_STAT[category],
    effects: finalEffects,
    targets_enemy: finalEffects.some((e) => e.target === 'target'),
    target_scope: scope,
    splash_radius: Math.min(MAX_SPLASH_RADIUS, Math.max(1, Number(action.splash_radius) || 1)),
  }
}

export const TARGET_SCOPES: TargetScope[] = ['SINGLE', 'SPLASH', 'ALL_ENEMIES']
export const MAX_SPLASH_RADIUS = 2
/** Mirrors `DEFAULT_SAVE_DC` in backend/engine/combat/area_attacks.py. */
export const DEFAULT_SAVE_DC = 12

export function isAreaAttack(action: NormalizedSpecialAttack): boolean {
  return action.targets_enemy && action.target_scope !== 'SINGLE'
}

/** Who an attack hits, e.g. "Harlan", "All enemies" or "Harlan + 1 each side". */
export function areaLabel(action: NormalizedSpecialAttack, targetName: string | null): string {
  const target = targetName || 'no target'
  if (!isAreaAttack(action)) return target
  if (action.target_scope === 'ALL_ENEMIES') return 'All enemies'
  return `${target} + ${action.splash_radius} each side`
}

export function costLabel(action: NormalizedSpecialAttack): string {
  if (!action.cost) return 'Free'
  return `${action.cost} ${action.cost_type === 'mana' ? 'MP' : 'STA'}`
}

export function checkLabel(action: NormalizedSpecialAttack): string {
  if (isAreaAttack(action) && action.save_stat) {
    return `${STAT_SHORT[action.save_stat]} save vs DC ${action.difficulty || DEFAULT_SAVE_DC}`
  }
  const stat = STAT_SHORT[action.success_stat]
  if (action.difficulty) return `${stat} vs DC ${action.difficulty}`
  if (action.targets_enemy) return `${stat} vs AC`
  return 'Always works'
}

export function describeEffects(effects: SpecialEffect[]): string {
  return effects
    .map((e) => `${e.amount} ${STAT_SHORT[e.stat]}${e.target === 'self' ? ' (self)' : ''}`)
    .join(' · ')
}
