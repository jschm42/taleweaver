/**
 * stageCastOrder — orders the character cards of the left stage.
 *
 * Only stable rules apply, so cards do not jump around while characters talk:
 *   0. the protagonist (always first)
 *   1. the active companion (`is_companion`, set by the backend), right next to the protagonist,
 *      even when downed
 *   2. everyone else, in the order the scene lists them
 *   3. defeated characters (always last)
 * The sort is stable, so characters within one group keep their original order.
 */

export function isDefeated(npc: any): boolean {
  return Boolean(npc?.is_defeated) || npc?.hp === 0
}

/** The active companion travelling with the protagonist (never the protagonist card itself). */
export function isStageCompanion(npc: any): boolean {
  return Boolean(npc?.is_companion) && npc?.id !== 'PLAYER'
}

function castRank(npc: any): number {
  if (npc?.id === 'PLAYER') {
    return 0
  }
  if (isStageCompanion(npc)) {
    return 1
  }
  return isDefeated(npc) ? 3 : 2
}

export function orderStageCast(npcs: any[]): any[] {
  return (npcs || [])
    .map((npc, index) => ({ npc, index, rank: castRank(npc) }))
    .sort((a, b) => a.rank - b.rank || a.index - b.index)
    .map((entry) => entry.npc)
}
