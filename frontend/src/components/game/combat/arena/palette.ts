import type { CombatStat, SpecialCategory } from '@/types'

export const ARENA_FONT = 'Acme, "Trebuchet MS", ui-sans-serif, system-ui, sans-serif'

const DEFAULT_COLORS = {
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
}

/** Arena colors; `applySkinColors` adapts the accents to the active dialog skin. */
export const COLORS: Record<keyof typeof DEFAULT_COLORS, number> = { ...DEFAULT_COLORS }

/** Skin token -> arena color it drives. Bars and damage colors stay fixed for readability. */
const SKIN_TOKENS: Partial<Record<keyof typeof DEFAULT_COLORS, string>> = {
  player: '--tw-player',
  gold: '--tw-accent-soft',
}

function parseHexColor(value: string): number | null {
  const match = /^#([0-9a-f]{6})$/i.exec(value.trim())
  return match ? parseInt(match[1], 16) : null
}

/** Reads the skin tokens visible at `el`; call before the arena creates its cards. */
export function applySkinColors(el: HTMLElement): void {
  Object.assign(COLORS, DEFAULT_COLORS)
  const style = getComputedStyle(el)
  for (const [key, token] of Object.entries(SKIN_TOKENS)) {
    const color = parseHexColor(style.getPropertyValue(token as string))
    if (color !== null) COLORS[key as keyof typeof DEFAULT_COLORS] = color
  }
}

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
