/**
 * stageCastOrder — orders the character cards of the left stage.
 *
 * Only stable rules apply, so cards do not jump around while characters talk:
 *   0. the protagonist (always first)
 *   1. everyone else, in the order the scene lists them
 *   2. defeated characters (always last)
 * The sort is stable, so characters within one group keep their original order.
 */

export function isDefeated(npc: any): boolean {
  return Boolean(npc?.is_defeated) || npc?.hp === 0
}

function castRank(npc: any): number {
  if (npc?.id === 'PLAYER') {
    return 0
  }
  return isDefeated(npc) ? 2 : 1
}

export function orderStageCast(npcs: any[]): any[] {
  return (npcs || [])
    .map((npc, index) => ({ npc, index, rank: castRank(npc) }))
    .sort((a, b) => a.rank - b.rank || a.index - b.index)
    .map((entry) => entry.npc)
}
