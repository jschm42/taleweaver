<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { CombatEnemyState, CombatLogEntry, CombatStat, CombatState } from '@/types'
import { getImageUrl, hasRenderableImagePath } from '@/utils/game_icons'
import { ArenaRenderer, type ArenaView } from './arena/ArenaRenderer'
import type { CardData, ResourceStat } from './arena/CombatantCard'
import { ArenaEventPlayer } from './arena/eventPlayer'

const PLAYER_ID = 'PLAYER'
const EVENT_TIMEOUT_MS = 9000
const RESOURCES: ResourceStat[] = ['hp', 'mana', 'stamina']

const props = defineProps<{
  combat: CombatState
  selectedTargetId: string | null
  fast?: boolean
  reducedMotion?: boolean
}>()

const emit = defineEmits<{
  selectTarget: [id: string]
  revealed: [count: number]
  playing: [isPlaying: boolean]
  hover: [entityId: string | null, event: MouseEvent | null]
}>()

const host = ref<HTMLElement | null>(null)
const failed = ref(false)
let arena: ArenaRenderer | null = null
let player: ArenaEventPlayer | null = null
let ready = false
let seenCount = 0
let playing = false
const queue: CombatLogEntry[] = []

type Deltas = Record<string, Partial<Record<CombatStat, number>>>

function pendingInfo(entries: CombatLogEntry[]): { deltas: Deltas; outIds: Set<string>; engageIds: Set<string> } {
  const deltas: Deltas = {}
  const outIds = new Set<string>()
  const engageIds = new Set<string>()
  for (const entry of entries) {
    const data = entry.data
    if (!data) continue
    if ((data.kind === 'defeat' || data.kind === 'fled') && data.entity) outIds.add(data.entity)
    if (data.kind === 'engage' && data.entity) engageIds.add(data.entity)
    for (const effect of data.effects ?? []) {
      const bucket = (deltas[effect.entity] ||= {})
      bucket[effect.stat] = (bucket[effect.stat] ?? 0) + effect.delta
    }
  }
  return { deltas, outIds, engageIds }
}

function imageUrl(raw: string | null | undefined): string | null {
  return hasRenderableImagePath(raw) ? getImageUrl(raw as string) : null
}

function num(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

/** Final modifiers minus attribute changes that have not been animated yet. */
function rewindModifiers(id: string, modifiers: Partial<Record<CombatStat, number>> | undefined, deltas: Deltas): Partial<Record<CombatStat, number>> {
  const result = { ...(modifiers ?? {}) }
  for (const [stat, delta] of Object.entries(deltas[id] ?? {})) {
    if (RESOURCES.includes(stat as ResourceStat) || !delta) continue
    const key = stat as CombatStat
    result[key] = (result[key] ?? 0) - delta
  }
  return result
}

function resourceValues(id: string, source: Record<string, unknown>, deltas: Deltas): Record<ResourceStat, number> {
  const pending = deltas[id] ?? {}
  return {
    hp: num(source.hp) - (pending.hp ?? 0),
    mana: num(source.mana) - (pending.mana ?? 0),
    stamina: num(source.stamina) - (pending.stamina ?? 0),
  }
}

function enemyCard(enemy: CombatEnemyState, info: ReturnType<typeof pendingInfo>): CardData {
  const values = resourceValues(enemy.id, enemy as unknown as Record<string, unknown>, info.deltas)
  const isOut = !info.outIds.has(enemy.id) && (enemy.defeated || enemy.fled)
  return {
    id: enemy.id,
    name: enemy.name,
    imageUrl: imageUrl(enemy.image_url),
    side: 'enemy',
    ...values,
    maxHp: num(enemy.max_hp, values.hp),
    maxMana: num(enemy.max_mana),
    maxStamina: num(enemy.max_stamina),
    modifiers: rewindModifiers(enemy.id, enemy.modifiers, info.deltas),
    engaged: !!enemy.engaged && !info.engageIds.has(enemy.id),
    out: isOut ? (enemy.fled ? 'fled' : 'defeated') : null,
  }
}

function buildView(pending: CombatLogEntry[]): ArenaView {
  const info = pendingInfo(pending)
  const p = props.combat.player
  const enemies = props.combat.enemies?.length ? props.combat.enemies : [props.combat.enemy]
  const playerValues = resourceValues(PLAYER_ID, p as unknown as Record<string, unknown>, info.deltas)
  return {
    player: {
      id: PLAYER_ID,
      name: p.name,
      imageUrl: imageUrl(p.image_url),
      side: 'player',
      ...playerValues,
      maxHp: num(p.max_hp, playerValues.hp),
      maxMana: num(p.max_mana),
      maxStamina: num(p.max_stamina),
      modifiers: rewindModifiers(PLAYER_ID, p.modifiers, info.deltas),
      engaged: true,
      out: null,
    },
    enemies: enemies.filter(Boolean).map((e) => enemyCard(e, info)),
    selectedId: props.selectedTargetId,
    activeId: props.combat.active ? (props.combat.active_actor ?? null) : null,
  }
}

function applySpeed(): void {
  if (!arena?.tween) return
  arena.tween.speed = props.reducedMotion ? 6 : props.fast ? 3 : 1
}

async function withTimeout(task: Promise<void>): Promise<void> {
  let timer = 0
  const timedOut = await Promise.race([
    task.then(() => false),
    new Promise<boolean>((resolve) => { timer = window.setTimeout(() => resolve(true), EVENT_TIMEOUT_MS) }),
  ])
  window.clearTimeout(timer)
  // A stalled animation (e.g. background tab) must not leave half-faded labels behind.
  if (timedOut) arena?.tween.finishAll()
}

async function drainQueue(): Promise<void> {
  if (playing || !player || !arena) return
  playing = true
  emit('playing', true)
  arena.sync(buildView(queue), true)
  while (queue.length > 0 && player) {
    const entry = queue[0]
    emit('revealed', seenCount - queue.length + 1)
    try {
      // Background tabs pause requestAnimationFrame; skip the show instead of stalling.
      if (!document.hidden) await withTimeout(player.play(entry.data))
    } catch (err) {
      console.warn('Combat animation failed', err)
    }
    queue.shift()
  }
  playing = false
  arena?.sync(buildView([]), true)
  emit('revealed', seenCount)
  emit('playing', false)
}

function onLogChange(): void {
  const logs = props.combat.log ?? []
  if (!ready || failed.value) {
    seenCount = logs.length
    emit('revealed', seenCount)
    return
  }
  if (logs.length < seenCount) {
    queue.length = 0
    seenCount = logs.length
    arena?.sync(buildView([]), true)
    emit('revealed', seenCount)
    return
  }
  if (logs.length === seenCount) return
  queue.push(...logs.slice(seenCount))
  seenCount = logs.length
  if (playing) {
    arena?.sync(buildView(queue), false)
    return
  }
  void drainQueue()
}

watch(() => props.combat.log?.length ?? 0, onLogChange)
watch(
  () => [props.selectedTargetId, props.combat.active_actor, props.combat.enemies, props.combat.player],
  () => {
    if (ready) arena?.sync(buildView(queue), !playing)
  },
)
watch(() => [props.fast, props.reducedMotion], applySpeed)

onMounted(async () => {
  arena = new ArenaRenderer()
  arena.onSelect = (id) => emit('selectTarget', id)
  arena.onHover = (id, event) => emit('hover', id, event)
  try {
    if (!host.value || !(await arena.init(host.value))) return
  } catch (err) {
    console.warn('Pixi arena unavailable, falling back to text mode', err)
    failed.value = true
    onLogChange()
    return
  }
  player = new ArenaEventPlayer(arena)
  ready = true
  applySpeed()
  seenCount = props.combat.log?.length ?? 0
  arena.sync(buildView([]), true)
  emit('revealed', seenCount)
})

onBeforeUnmount(() => {
  queue.length = 0
  player = null
  arena?.destroy()
  arena = null
})
</script>

<template>
  <div class="relative w-full h-full min-h-[260px]">
    <div ref="host" class="absolute inset-0" aria-label="Combat arena" role="img"></div>
    <div v-if="failed" class="absolute inset-0 flex items-center justify-center text-sm text-slate-400 italic">
      Animated arena unavailable on this device. Follow the battle chronicle.
    </div>
  </div>
</template>
