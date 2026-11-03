import { onBeforeUnmount, ref, watch } from 'vue'

/** One floating value on a character card, e.g. "-5 HP". */
export interface StatPopup {
  id: number
  label: string
  delta: number
  /** Position in the burst of one update (staggers popups of the same card). */
  order: number
}

/** How long a popup stays on its card (ms); matches the CSS animation. */
export const STAT_POPUP_MS = 3200
/** Delay between popups of one update (ms), so several changes read one after another. */
export const STAT_POPUP_STAGGER_MS = 300
/** How long a card flashes after losing HP (ms). */
const HIT_FLASH_MS = 900

type StatReader = (npc: any) => unknown

/** Shown values and how to read them; attributes come from the hero's `stats`. */
const TRACKED_STATS: Array<{ label: string; read: StatReader }> = [
  { label: 'HP', read: (npc) => npc.hp },
  { label: 'MP', read: (npc) => npc.mana },
  { label: 'STA', read: (npc) => npc.stamina },
  { label: 'STR', read: (npc) => npc.stats?.strength },
  { label: 'DEX', read: (npc) => npc.stats?.dexterity },
  { label: 'INT', read: (npc) => npc.stats?.intelligence },
  { label: 'WIS', read: (npc) => npc.stats?.wisdom },
  { label: 'CHA', read: (npc) => npc.stats?.charisma },
  { label: 'AC', read: (npc) => npc.stats?.armor_class },
]

type Snapshot = Record<string, number>

function readSnapshot(npc: any): Snapshot {
  const values: Snapshot = {}
  for (const stat of TRACKED_STATS) {
    const raw = stat.read(npc)
    if (raw === null || raw === undefined || raw === '') continue
    const value = Number(raw)
    if (Number.isFinite(value)) values[stat.label] = value
  }
  return values
}

function changedStats(before: Snapshot, after: Snapshot): Array<{ label: string; delta: number }> {
  return TRACKED_STATS.map(({ label }) => ({ label, delta: (after[label] ?? NaN) - (before[label] ?? NaN) }))
    .filter(({ delta }) => Number.isFinite(delta) && delta !== 0)
}

/**
 * Floating "+/- value" popups for character cards whose HP, Mana, Stamina or attributes change.
 *
 * Only changes between two updates of a card that stays on stage count: the first values of a
 * card (page load, a character entering the scene) never produce popups.
 */
export function useStatChangePopups(npcs: () => any[]) {
  const popups = ref<Record<string, StatPopup[]>>({})
  const hitCards = ref<Set<string>>(new Set())
  let snapshots = new Map<string, Snapshot>()
  let nextId = 1
  const timers = new Set<number>()

  function later(ms: number, action: () => void) {
    const timer = window.setTimeout(() => {
      timers.delete(timer)
      action()
    }, ms)
    timers.add(timer)
  }

  function show(cardId: string, changes: Array<{ label: string; delta: number }>) {
    const added = changes.map((change, order) => ({ id: nextId++, order, ...change }))
    popups.value = { ...popups.value, [cardId]: [...(popups.value[cardId] || []), ...added] }
    const ids = new Set(added.map((popup) => popup.id))
    const lifetime = STAT_POPUP_MS + Math.max(0, added.length - 1) * STAT_POPUP_STAGGER_MS
    later(lifetime, () => {
      const remaining = (popups.value[cardId] || []).filter((popup) => !ids.has(popup.id))
      popups.value = { ...popups.value, [cardId]: remaining }
    })
  }

  function flashHit(cardId: string) {
    hitCards.value = new Set([...hitCards.value, cardId])
    later(HIT_FLASH_MS, () => {
      const remaining = new Set(hitCards.value)
      remaining.delete(cardId)
      hitCards.value = remaining
    })
  }

  watch(
    () => (npcs() || []).map((npc) => [String(npc.id), readSnapshot(npc)] as const),
    (cards) => {
      const next = new Map<string, Snapshot>()
      for (const [cardId, values] of cards) {
        next.set(cardId, values)
        const before = snapshots.get(cardId)
        if (!before) continue
        const changes = changedStats(before, values)
        if (!changes.length) continue
        show(cardId, changes)
        if (changes.some((change) => change.label === 'HP' && change.delta < 0)) flashHit(cardId)
      }
      // Cards that left the stage are forgotten, so a later return starts fresh.
      snapshots = next
    },
    { immediate: true, deep: true }
  )

  onBeforeUnmount(() => {
    timers.forEach((timer) => window.clearTimeout(timer))
    timers.clear()
  })

  return { popups, hitCards }
}
