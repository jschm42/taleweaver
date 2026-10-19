import type { CombatStat, SpecialCategory } from '@/types'

export const ARENA_FONT = 'Acme, "Trebuchet MS", ui-sans-serif, system-ui, sans-serif'

export const COLORS = {
  ink: 0x0b1120,
  panel: 0x111827,
  panelLight: 0x1e293b,
  gold: 0xfbbf24,
  goldSoft: 0xfde68a,
  player: 0x34d399,
  enemy: 0xfb7185,
  passive: 0x94a3b8,
  hp: 0xef4444,
  hpGain: 0x4ade80,
  mana: 0x60a5fa,
  stamina: 0x34d399,
  attribute: 0xc4b5fd,
  white: 0xf8fafc,
  muted: 0x64748b,
  miss: 0xcbd5e1,
} as const

export const CATEGORY_COLORS: Record<SpecialCategory, number> = {
  MAGIC: 0xa78bfa,
  MELEE: 0xfb923c,
  RANGED: 0x4ade80,
  SOCIAL: 0xf472b6,
  OTHER: 0x22d3ee,
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

export function effectColor(stat: CombatStat, delta: number): number {
  if (stat === 'hp') return delta < 0 ? COLORS.hp : COLORS.hpGain
  if (stat === 'mana') return COLORS.mana
  if (stat === 'stamina') return COLORS.stamina
  return delta < 0 ? COLORS.enemy : COLORS.attribute
}

export function formatDelta(stat: CombatStat, delta: number): string {
  const sign = delta > 0 ? '+' : ''
  return `${sign}${delta} ${STAT_SHORT[stat]}`
}
