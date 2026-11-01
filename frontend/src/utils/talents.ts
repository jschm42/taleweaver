import type { Talent, TalentTargetType } from '@/types'

/** Mirrors backend/engine/rules/talents.py. */
export const MAX_TALENTS = 8
export const TALENT_COMMAND = '/talent'
export const TALENT_TARGET_TYPES: TalentTargetType[] = ['NONE', 'NPC', 'ITEM', 'ANY']
export const TALENT_TARGET_LABELS: Record<TalentTargetType, string> = {
  NONE: 'Nothing (no target)',
  NPC: 'A character (NPC)',
  ITEM: 'An item (scene or inventory)',
  ANY: 'Anything (optional target)',
}

/** Talent with the engine defaults filled in. */
export interface NormalizedTalent extends Talent {
  target_type: TalentTargetType
  cost_type: 'mana' | 'stamina'
  cost: number
  max_uses: number | null
}

export function normalizeTalent(talent: Talent): NormalizedTalent {
  const target = String(talent.target_type ?? '').toUpperCase() as TalentTargetType
  const maxUses = Number(talent.max_uses)
  return {
    ...talent,
    id: String(talent.id || '').toUpperCase(),
    name: talent.name || talent.id,
    target_type: TALENT_TARGET_TYPES.includes(target) ? target : 'NONE',
    cost_type: talent.cost_type === 'stamina' ? 'stamina' : 'mana',
    cost: Math.max(0, Number(talent.cost) || 0),
    max_uses: Number.isInteger(maxUses) && maxUses > 0 ? maxUses : null,
  }
}

export function talentCostLabel(talent: NormalizedTalent): string {
  if (!talent.cost) return 'Free'
  return `${talent.cost} ${talent.cost_type === 'mana' ? 'MP' : 'STA'}`
}

/** Remaining uses this adventure, or null for unlimited. */
export function talentUsesLeft(talent: NormalizedTalent, uses: Record<string, number> | undefined): number | null {
  if (!talent.max_uses) return null
  return Math.max(0, talent.max_uses - (Number(uses?.[talent.id]) || 0))
}

export function talentNeedsTarget(talent: NormalizedTalent): boolean {
  return talent.target_type === 'NPC' || talent.target_type === 'ITEM'
}

/** Whether ``entityType`` ('NPC' | 'OBJECT') is a valid target for the talent. */
export function talentAcceptsEntity(talent: NormalizedTalent, entityType: string): boolean {
  const kind = String(entityType || '').toUpperCase()
  if (talent.target_type === 'ANY') return kind === 'NPC' || kind === 'OBJECT'
  if (talent.target_type === 'NPC') return kind === 'NPC'
  if (talent.target_type === 'ITEM') return kind === 'OBJECT'
  return false
}

/** The turn command the Talents menu and the context menu send. */
export function talentCommand(talentId: string, targetId?: string | null): string {
  return targetId ? `${TALENT_COMMAND} ${talentId} | ${targetId}` : `${TALENT_COMMAND} ${talentId}`
}

/** Unlocked talents of a character sheet (``sheet.talents`` / ``sheet.unlocked_talents``). */
export function sheetTalents(sheet: any): NormalizedTalent[] {
  const unlocked = new Set<string>((sheet?.unlocked_talents ?? []).map((id: string) => String(id).toUpperCase()))
  return (Array.isArray(sheet?.talents) ? sheet.talents : [])
    .map(normalizeTalent)
    .filter((t: NormalizedTalent) => t.id && unlocked.has(t.id))
}
