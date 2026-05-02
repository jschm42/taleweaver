<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { CombatState, InventoryItem, CharacterSheet } from '@/types'
import StatBar from './StatBar.vue'
import { getImageUrl, getItemIcon, getTypeColor, hasRenderableImagePath } from '@/utils/game_icons'

const LOG_REVEAL_DELAY_MS = 2000
const DAMAGE_FLOAT_DURATION_MS = 2600
const IMPACT_DURATION_MS = 620
const HEAVY_IMPACT_DURATION_MS = 900
const HEAVY_HIT_MAX_HP_RATIO = 0.15
const HEAVY_HIT_MIN_DAMAGE = 8
const HEAVY_HIT_FALLBACK_DAMAGE = 18

const props = defineProps<{
  open: boolean
  combat: CombatState | null
  consumables: InventoryItem[]
  npcMetadata: Record<string, any>
  playerSheet: CharacterSheet | null
  evaluating?: boolean
}>()

const emit = defineEmits<{
  attack: []
  run: []
  consume: [name: string]
  lootTake: [item: InventoryItem]
  lootLeave: [item: InventoryItem]
  lootDone: []
  entityHover: [entity: any, event: MouseEvent]
  entityLeave: []
}>()

const logs = computed(() => props.combat?.log || [])
const parsedLogs = computed(() => logs.value.map((entry) => ({
  ...entry,
  attackRoll: parseAttackRoll(entry.text),
  isPlayerAttack: isPlayerAttack(entry.text),
  source: getEntrySource(entry.type, entry.text),
})))
const lootItems = computed(() => props.combat?.loot_items || [])
const isLootPhase = computed(() => !!props.combat?.loot_pending)
const activeTurn = computed(() => props.combat?.turn || 'player')
const playerImageFailed = ref(false)
const enemyImageFailed = ref(false)
const visibleLogCount = ref(0)
const lastSeenLogLength = ref(0)
const initializedLogView = ref(false)
const logContainerRef = ref<HTMLElement | null>(null)
const prefersReducedMotion = ref(false)

type DamageFxItem = {
  id: number
  side: 'player' | 'enemy'
  amount: number
  offsetX: number
}

type ImpactFxItem = {
  id: number
  side: 'player' | 'enemy'
  heavy: boolean
}

const damageFx = ref<DamageFxItem[]>([])
const playerDamageFx = computed(() => damageFx.value.filter((item) => item.side === 'player'))
const enemyDamageFx = computed(() => damageFx.value.filter((item) => item.side === 'enemy'))
const impactFx = ref<ImpactFxItem[]>([])
const playerImpactFx = computed(() => impactFx.value.filter((item) => item.side === 'player'))
const enemyImpactFx = computed(() => impactFx.value.filter((item) => item.side === 'enemy'))

let damageFxCounter = 0
let revealTimeouts: number[] = []
let cleanupTimeouts: number[] = []
let motionMediaQuery: MediaQueryList | null = null

const visibleLogs = computed(() => parsedLogs.value.slice(0, visibleLogCount.value))

const combatIdentity = computed(() => {
  const combat = props.combat
  if (!combat) return ''
  return `${combat.player.name}::${combat.enemy.id}`
})

function clearTimeoutList(timeoutIds: number[]): void {
  for (const timeoutId of timeoutIds) {
    window.clearTimeout(timeoutId)
  }
  timeoutIds.length = 0
}

function clearPendingTimers(): void {
  clearTimeoutList(revealTimeouts)
  clearTimeoutList(cleanupTimeouts)
}

function resetAnimatedState(): void {
  clearPendingTimers()
  visibleLogCount.value = 0
  lastSeenLogLength.value = 0
  initializedLogView.value = false
  damageFx.value = []
}

function makeLogKey(entry: any, idx: number): string {
  const timestamp = entry.timestamp || 'no-ts'
  return `${timestamp}-${entry.round}-${entry.type}-${idx}`
}

function maybeSpawnDamageFx(entry: any): void {
  const roll = entry?.attackRoll
  if (!roll || !roll.isHit || roll.damageTotal == null || roll.damageTotal <= 0) return

  const side: 'player' | 'enemy' = entry.isPlayerAttack ? 'enemy' : 'player'
  const fxId = ++damageFxCounter
  const isHeavy = isHeavyHitByMaxHp(side, roll.damageTotal)
  damageFx.value.push({
    id: fxId,
    side,
    amount: roll.damageTotal,
    offsetX: Math.round((Math.random() - 0.5) * 30),
  })
  maybeSpawnImpactFx(side, isHeavy)

  const cleanupId = window.setTimeout(() => {
    damageFx.value = damageFx.value.filter((item) => item.id !== fxId)
  }, DAMAGE_FLOAT_DURATION_MS)
  cleanupTimeouts.push(cleanupId)
}

function maybeSpawnImpactFx(side: 'player' | 'enemy', heavy: boolean): void {
  const fxId = ++damageFxCounter
  impactFx.value.push({ id: fxId, side, heavy })
  const duration = heavy ? HEAVY_IMPACT_DURATION_MS : IMPACT_DURATION_MS
  const cleanupId = window.setTimeout(() => {
    impactFx.value = impactFx.value.filter((item) => item.id !== fxId)
  }, duration)
  cleanupTimeouts.push(cleanupId)
}

function getTargetMaxHp(side: 'player' | 'enemy'): number {
  const raw = side === 'player' ? props.combat?.player?.max_hp : props.combat?.enemy?.max_hp
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : 0
}

function isHeavyHitByMaxHp(side: 'player' | 'enemy', damageTotal: number): boolean {
  const maxHp = getTargetMaxHp(side)
  if (maxHp <= 0) {
    return damageTotal >= HEAVY_HIT_FALLBACK_DAMAGE
  }
  const threshold = Math.max(HEAVY_HIT_MIN_DAMAGE, Math.ceil(maxHp * HEAVY_HIT_MAX_HP_RATIO))
  return damageTotal >= threshold
}

watch(() => props.combat?.player?.image_url, () => {
  playerImageFailed.value = false
})

watch(() => props.combat?.enemy?.image_url, () => {
  enemyImageFailed.value = false
})

function onPlayerImageError(): void {
  playerImageFailed.value = true
}

function onEnemyImageError(): void {
  enemyImageFailed.value = true
}

function scrollLogToBottom(behavior: ScrollBehavior): void {
  const el = logContainerRef.value
  if (!el) return
  el.scrollTo({ top: el.scrollHeight, behavior })
}

function revealNewLogs(startIndex: number, endIndex: number): void {
  const interval = prefersReducedMotion.value ? 0 : LOG_REVEAL_DELAY_MS
  for (let idx = startIndex; idx < endIndex; idx += 1) {
    const step = idx - startIndex
    const delay = interval * (step + 1)
    const timeoutId = window.setTimeout(() => {
      visibleLogCount.value = Math.max(visibleLogCount.value, idx + 1)
      maybeSpawnDamageFx(parsedLogs.value[idx])
      nextTick(() => scrollLogToBottom(prefersReducedMotion.value ? 'auto' : 'smooth'))
    }, delay)
    revealTimeouts.push(timeoutId)
  }
}

watch(() => props.open, (isOpen) => {
  if (!isOpen) {
    resetAnimatedState()
  }
})

watch(combatIdentity, (nextIdentity, prevIdentity) => {
  if (nextIdentity !== prevIdentity) {
    resetAnimatedState()
  }
})

watch(
  parsedLogs,
  (nextLogs) => {
    if (!props.open || !props.combat) return

    const nextLength = nextLogs.length
    if (!initializedLogView.value) {
      visibleLogCount.value = nextLength
      lastSeenLogLength.value = nextLength
      initializedLogView.value = true
      nextTick(() => scrollLogToBottom('auto'))
      return
    }

    if (nextLength < lastSeenLogLength.value) {
      clearPendingTimers()
      visibleLogCount.value = nextLength
      lastSeenLogLength.value = nextLength
      nextTick(() => scrollLogToBottom('auto'))
      return
    }

    if (nextLength === lastSeenLogLength.value) return

    clearTimeoutList(revealTimeouts)
    const startIndex = lastSeenLogLength.value
    lastSeenLogLength.value = nextLength
    revealNewLogs(startIndex, nextLength)
  },
  { deep: false },
)

function onMotionChange(event: MediaQueryListEvent): void {
  prefersReducedMotion.value = event.matches
}

onMounted(() => {
  motionMediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  prefersReducedMotion.value = motionMediaQuery.matches
  motionMediaQuery.addEventListener('change', onMotionChange)
})

onBeforeUnmount(() => {
  clearPendingTimers()
  if (motionMediaQuery) {
    motionMediaQuery.removeEventListener('change', onMotionChange)
    motionMediaQuery = null
  }
})

type AttackRollView = {
  attacker: string
  hitRoll: number
  hitModifier: number
  hitTotal: number
  targetAc: number
  isHit: boolean
  damageDice?: string
  damageExpression?: string
  damageTotal?: number
}

function parseAttackRoll(text: string): AttackRollView | null {
  const rx = /^(.*?) ATTACK ROLL: (\d+) \+ (-?\d+) = (\d+) vs AC (\d+) -> (HIT|MISS)(?: \| DMG ([^ ]+) \(([^)]*)\) = (\d+))?$/
  const match = text.match(rx)
  if (!match) return null
  return {
    attacker: match[1].trim(),
    hitRoll: Number(match[2]),
    hitModifier: Number(match[3]),
    hitTotal: Number(match[4]),
    targetAc: Number(match[5]),
    isHit: match[6] === 'HIT',
    damageDice: match[7],
    damageExpression: match[8],
    damageTotal: match[9] ? Number(match[9]) : undefined,
  }
}

function isPlayerAttack(text: string): boolean {
  const attacker = text.split(' ATTACK ROLL:')[0]?.trim() || ''
  return attacker.length > 0 && attacker === (props.combat?.player?.name || '')
}

function attackCardClass(isPlayer: boolean): string {
  return isPlayer
    ? 'border-emerald-500/30 bg-emerald-950/20'
    : 'border-rose-500/30 bg-rose-950/20'
}

function attackLabelClass(isPlayer: boolean): string {
  return isPlayer
    ? 'bg-emerald-700/30 border-emerald-400/30 text-emerald-200'
    : 'bg-rose-700/30 border-rose-400/30 text-rose-200'
}

function getEntrySource(entryType: string, text: string): 'YOU' | 'ENEMY' | 'GAMEMASTER' | 'LOOT' {
  if (entryType === 'enemy_action') return 'ENEMY'
  if (entryType === 'special' || entryType === 'initiative' || entryType === 'turn' || entryType === 'outcome') return 'GAMEMASTER'
  if (entryType === 'loot') return 'LOOT'
  if (entryType === 'player_action' || entryType === 'consume' || entryType === 'run') return 'YOU'

  if (text.includes(' ATTACK ROLL:')) {
    const attacker = text.split(' ATTACK ROLL:')[0]?.trim() || ''
    if (attacker && attacker === (props.combat?.player?.name || '')) return 'YOU'
    if (attacker) return 'ENEMY'
  }
  return 'GAMEMASTER'
}

function sourceClass(source: 'YOU' | 'ENEMY' | 'GAMEMASTER' | 'LOOT'): string {
  if (source === 'YOU') return 'bg-emerald-700/30 border-emerald-400/30 text-emerald-200'
  if (source === 'ENEMY') return 'bg-rose-700/30 border-rose-400/30 text-rose-200'
  if (source === 'LOOT') return 'bg-amber-700/30 border-amber-400/30 text-amber-200'
  return 'bg-violet-700/30 border-violet-400/30 text-violet-200'
}

const isPlayerTurn = computed(() => !isLootPhase.value && activeTurn.value === 'player')
const isInteractionLocked = computed(() => !!props.evaluating)

function asInt(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

const protagonistTooltipEntity = computed(() => {
  const player = props.combat?.player
  if (!player) return null
  const sheet = props.playerSheet
  return {
    id: 'PLAYER',
    entity_type: 'NPC',
    name: sheet?.name ? `You (${sheet.name})` : player.name,
    description: sheet?.description || 'Your character in this adventure.',
    image_url: player.image_url || sheet?.profile_image || null,
    hp: asInt(player.hp),
    max_hp: asInt(player.max_hp, asInt(sheet?.max_hp, 0)),
    stamina: asInt(sheet?.stamina),
    max_stamina: asInt(sheet?.max_stamina),
    mana: asInt(sheet?.mana),
    max_mana: asInt(sheet?.max_mana),
    inventory: Array.isArray(sheet?.inventory) ? sheet?.inventory : [],
  }
})

const enemyTooltipEntity = computed(() => {
  const enemy = props.combat?.enemy
  if (!enemy) return null
  const byId = props.npcMetadata?.[enemy.id]
  const byName = props.npcMetadata?.[enemy.name]
  const base = (byId || byName || {}) as Record<string, any>
  return {
    ...base,
    id: enemy.id,
    name: enemy.name,
    image_url: enemy.image_url || base.image_url || null,
    entity_type: 'NPC',
    description: base.description || 'A dangerous opponent in this fight.',
    hp: enemy.hp,
    max_hp: enemy.max_hp || base.max_hp,
    stamina: asInt(base.stamina),
    max_stamina: asInt(base.max_stamina),
    mana: asInt(base.mana),
    max_mana: asInt(base.max_mana),
    inventory: enemy.inventory || base.inventory || [],
  }
})

function toConsumableTooltipEntity(item: InventoryItem): Record<string, any> {
  return {
    ...item,
    entity_type: 'ITEM',
    description: (item.description as string) || 'A consumable that can be used during combat.',
  }
}

function emitHover(entity: any, event: MouseEvent): void {
  emit('entityHover', entity, event)
}

function emitLeave(): void {
  emit('entityLeave')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fight-fade">
      <div v-if="open && combat" class="fixed inset-0 z-[110] bg-slate-950/70 backdrop-blur-sm p-3 sm:p-6 md:p-8 flex items-center justify-center">
        <div class="w-full max-w-6xl h-[80vh] border border-amber-700/40 bg-gradient-to-b from-slate-900/95 via-slate-900 to-slate-950 rounded-2xl shadow-[0_0_60px_rgba(251,191,36,0.15)] overflow-hidden flex flex-col">
          <header class="shrink-0 px-4 py-3 border-b border-amber-500/20 bg-slate-950/60 flex items-center justify-between">
            <h2 class="text-sm sm:text-base uppercase tracking-[0.22em] text-amber-300 font-black">Turn-Based Combat</h2>
            <div class="text-xs text-slate-300">
              Round <span class="font-black text-amber-200">{{ combat.round }}</span>
              <span class="mx-2 text-slate-600">|</span>
              Turn: <span class="font-black" :class="activeTurn === 'player' ? 'text-emerald-300' : 'text-rose-300'">{{ activeTurn }}</span>
            </div>
          </header>

          <div class="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-[220px_1fr_220px] gap-2 sm:gap-3 p-2 sm:p-3 md:p-4">
            <section
              class="border border-emerald-500/20 bg-slate-900/80 rounded-xl p-3 flex flex-col items-center justify-start"
              @mouseenter="protagonistTooltipEntity && emitHover(protagonistTooltipEntity, $event)"
              @mousemove="protagonistTooltipEntity && emitHover(protagonistTooltipEntity, $event)"
              @mouseleave="emitLeave"
            >
              <div class="text-[10px] uppercase tracking-[0.2em] text-emerald-300/80 mb-2">Protagonist</div>
              <div class="relative w-24 h-24 sm:w-28 sm:h-28 rounded-xl overflow-hidden border border-emerald-400/40 bg-slate-950">
                <img v-if="hasRenderableImagePath(combat.player.image_url) && !playerImageFailed" :src="getImageUrl(combat.player.image_url)" class="w-full h-full object-cover object-top" alt="protagonist" @error="onPlayerImageError">
                <div v-else class="w-full h-full flex items-center justify-center text-emerald-300 ra ra-player text-3xl"></div>
                <div class="absolute inset-0 pointer-events-none">
                  <span
                    v-for="fx in playerImpactFx"
                    :key="fx.id"
                    :class="['impact-float', fx.heavy ? 'impact-float-heavy' : 'impact-float-light']"
                  ></span>
                </div>
                <div class="absolute inset-0 pointer-events-none">
                  <span
                    v-for="fx in playerDamageFx"
                    :key="fx.id"
                    class="damage-float"
                    :style="{ '--dx': `${fx.offsetX}px` }"
                  >
                    -{{ fx.amount }}
                  </span>
                </div>
              </div>
              <div class="mt-3 text-xs text-white font-bold text-center">{{ combat.player.name }}</div>
              <div class="mt-2 w-full">
                <StatBar label="HP" :value="asInt(combat.player.hp)" :max="asInt(combat.player.max_hp)" color="crimson" size="sm" />
                <StatBar label="Stamina" :value="asInt(playerSheet?.stamina)" :max="asInt(playerSheet?.max_stamina)" color="emerald" size="sm" />
                <StatBar label="Mana" :value="asInt(playerSheet?.mana)" :max="asInt(playerSheet?.max_mana)" color="sapphire" size="sm" />
              </div>
            </section>

            <section class="border border-amber-500/20 bg-slate-900/80 rounded-xl min-h-0 flex flex-col">
              <div class="px-3 py-2 border-b border-amber-500/15 text-[10px] uppercase tracking-[0.2em] text-amber-300/80">
                Battle Chronicle
              </div>
              <div ref="logContainerRef" class="flex-1 min-h-0 overflow-y-auto custom-scrollbar px-3 py-2 space-y-2">
                <div v-for="(entry, idx) in visibleLogs" :key="makeLogKey(entry, idx)" class="combat-log-entry text-sm md:text-base leading-relaxed border-l-2 pl-2"
                  :class="entry.type === 'special' ? 'border-violet-400/60 text-violet-200' : entry.type === 'enemy_action' ? 'border-rose-500/50 text-rose-200' : entry.type === 'player_action' ? 'border-emerald-500/50 text-emerald-200' : 'border-amber-500/40 text-slate-200'">
                  <div class="mb-1.5">
                    <span :class="['text-[10px] px-1.5 py-0.5 rounded border font-black uppercase tracking-[0.12em]', sourceClass(entry.source)]">
                      {{ entry.source }}
                    </span>
                  </div>
                  <template v-if="entry.attackRoll">
                    <div :class="['rounded-lg border p-2.5 attack-roll-card', attackCardClass(entry.isPlayerAttack), entry.attackRoll.isHit ? 'attack-roll-hit' : 'attack-roll-miss']">
                      <div class="flex items-center gap-2 mb-2 flex-wrap">
                        <span :class="['text-[10px] px-1.5 py-0.5 rounded border font-black uppercase tracking-[0.12em]', attackLabelClass(entry.isPlayerAttack)]">
                          ⚔ Attack
                        </span>
                        <span class="text-xs uppercase tracking-[0.12em] font-black text-slate-200">{{ entry.attackRoll.attacker }}</span>
                        <span class="text-[10px] px-2 py-0.5 rounded font-black uppercase tracking-[0.1em]"
                          :class="entry.attackRoll.isHit ? 'bg-emerald-700/70 text-emerald-100 border border-emerald-400/30' : 'bg-rose-700/70 text-rose-100 border border-rose-400/30'">
                          {{ entry.attackRoll.isHit ? 'Hit' : 'Miss' }}
                        </span>
                      </div>

                      <div class="text-[11px] md:text-sm text-slate-300 mb-1.5 font-semibold">🎲 To-Hit Check</div>
                      <div class="flex items-center gap-1.5 flex-wrap mb-2">
                        <span class="px-2 py-1 rounded bg-slate-800 text-cyan-200 text-[11px] font-black">d20 {{ entry.attackRoll.hitRoll }}</span>
                        <span class="px-2 py-1 rounded bg-slate-800 text-amber-200 text-[11px] font-black">MOD {{ entry.attackRoll.hitModifier >= 0 ? '+' : '' }}{{ entry.attackRoll.hitModifier }}</span>
                        <span class="px-2 py-1 rounded bg-slate-800 text-emerald-200 text-[11px] font-black">TOTAL {{ entry.attackRoll.hitTotal }}</span>
                        <span class="px-2 py-1 rounded bg-slate-800 text-violet-200 text-[11px] font-black">AC {{ entry.attackRoll.targetAc }}</span>
                      </div>

                      <div v-if="entry.attackRoll.isHit && entry.attackRoll.damageTotal != null">
                        <div class="text-[11px] md:text-sm text-slate-300 mb-1.5 font-semibold">💥 Damage Roll</div>
                        <div class="flex items-center gap-1.5 flex-wrap">
                          <span class="px-2 py-1 rounded bg-slate-800 text-rose-200 text-[11px] font-black">{{ entry.attackRoll.damageDice }}</span>
                          <span class="px-2 py-1 rounded bg-slate-800 text-orange-200 text-[11px] font-black">{{ entry.attackRoll.damageExpression }}</span>
                          <span class="px-2 py-1 rounded bg-rose-700/60 border border-rose-400/40 text-rose-100 text-[11px] font-black">DMG {{ entry.attackRoll.damageTotal }}</span>
                        </div>
                      </div>
                    </div>
                  </template>
                  <template v-else>
                    {{ entry.text }}
                  </template>
                </div>
              </div>

              <div v-if="isLootPhase" class="border-t border-amber-500/15 px-3 py-2">
                <div class="text-[10px] uppercase tracking-[0.2em] text-amber-300/80 mb-2">Loot Summary</div>
                <div v-if="lootItems.length === 0" class="text-xs text-slate-400">No loot left.</div>
                <div v-else class="space-y-2 max-h-40 overflow-y-auto custom-scrollbar pr-1">
                  <div v-for="item in lootItems" :key="item.id || item.name" class="flex items-center justify-between gap-2 p-2 rounded-lg bg-slate-950/70 border border-slate-700/50">
                    <div class="flex items-center gap-2 min-w-0">
                      <i :class="['ra text-sm', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
                      <span class="text-xs text-slate-200 truncate">{{ item.name }}</span>
                    </div>
                    <div class="flex items-center gap-1 shrink-0">
                      <button class="px-2 py-1 text-[10px] font-black rounded bg-emerald-700/80 hover:bg-emerald-600 text-white disabled:opacity-40" :disabled="isInteractionLocked" @click="emit('lootTake', item)">Take</button>
                      <button class="px-2 py-1 text-[10px] font-black rounded bg-slate-700 hover:bg-slate-600 text-white disabled:opacity-40" :disabled="isInteractionLocked" @click="emit('lootLeave', item)">Leave</button>
                    </div>
                  </div>
                </div>
                <div class="mt-2 flex justify-end">
                  <button class="px-3 py-1.5 text-[10px] font-black rounded bg-amber-700 hover:bg-amber-600 text-white uppercase tracking-[0.08em] disabled:opacity-40" :disabled="isInteractionLocked" @click="emit('lootDone')">
                    Finish Loot
                  </button>
                </div>
              </div>
            </section>

            <section
              class="border border-rose-500/20 bg-slate-900/80 rounded-xl p-3 flex flex-col items-center justify-start"
              @mouseenter="enemyTooltipEntity && emitHover(enemyTooltipEntity, $event)"
              @mousemove="enemyTooltipEntity && emitHover(enemyTooltipEntity, $event)"
              @mouseleave="emitLeave"
            >
              <div class="text-[10px] uppercase tracking-[0.2em] text-rose-300/80 mb-2">Enemy</div>
              <div class="relative w-24 h-24 sm:w-28 sm:h-28 rounded-xl overflow-hidden border border-rose-400/40 bg-slate-950">
                <img v-if="hasRenderableImagePath(combat.enemy.image_url) && !enemyImageFailed" :src="getImageUrl(combat.enemy.image_url)" class="w-full h-full object-cover object-top" alt="enemy" @error="onEnemyImageError">
                <div v-else class="w-full h-full flex items-center justify-center text-rose-300 ra ra-monster-skull text-3xl"></div>
                <div class="absolute inset-0 pointer-events-none">
                  <span
                    v-for="fx in enemyImpactFx"
                    :key="fx.id"
                    :class="['impact-float', fx.heavy ? 'impact-float-heavy' : 'impact-float-light']"
                  ></span>
                </div>
                <div class="absolute inset-0 pointer-events-none">
                  <span
                    v-for="fx in enemyDamageFx"
                    :key="fx.id"
                    class="damage-float"
                    :style="{ '--dx': `${fx.offsetX}px` }"
                  >
                    -{{ fx.amount }}
                  </span>
                </div>
              </div>
              <div class="mt-3 text-xs text-white font-bold text-center">{{ combat.enemy.name }}</div>
              <div class="mt-2 w-full">
                <StatBar label="HP" :value="asInt(combat.enemy.hp)" :max="asInt(combat.enemy.max_hp)" color="crimson" size="sm" />
                <StatBar label="Stamina" :value="asInt(enemyTooltipEntity?.stamina)" :max="asInt(enemyTooltipEntity?.max_stamina)" color="emerald" size="sm" />
                <StatBar label="Mana" :value="asInt(enemyTooltipEntity?.mana)" :max="asInt(enemyTooltipEntity?.max_mana)" color="sapphire" size="sm" />
              </div>
            </section>
          </div>

          <footer class="shrink-0 border-t border-amber-500/20 bg-slate-950/70 p-3 space-y-3">
            <div class="flex items-center gap-2">
              <button
                class="px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-black uppercase tracking-[0.1em] disabled:opacity-40"
                :disabled="isLootPhase || activeTurn !== 'player' || isInteractionLocked"
                @click="emit('attack')"
              >
                Attack
              </button>
              <button
                class="px-4 py-2 rounded-lg bg-rose-700 hover:bg-rose-600 text-white text-xs font-black uppercase tracking-[0.1em] disabled:opacity-40"
                :disabled="isLootPhase || activeTurn !== 'player' || isInteractionLocked"
                @click="emit('run')"
              >
                Run
              </button>
              <div class="text-[11px] text-slate-400 ml-2">{{ isInteractionLocked ? 'Game Master is resolving the turn...' : 'Use a consumable instead of attacking in this round.' }}</div>
            </div>

            <div>
              <div class="text-[10px] uppercase tracking-[0.2em] text-slate-400 mb-2">Consumables</div>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="item in consumables"
                  :key="item.id || item.name"
                  class="group flex items-center gap-1.5 px-2 py-1 rounded-lg border border-cyan-500/25 bg-cyan-900/20 hover:bg-cyan-800/30 disabled:opacity-40"
                  @mouseenter="emitHover(toConsumableTooltipEntity(item), $event)"
                  @mousemove="emitHover(toConsumableTooltipEntity(item), $event)"
                  @mouseleave="emitLeave"
                  :disabled="!isPlayerTurn || isInteractionLocked"
                  @click="emit('consume', item.name)"
                >
                  <div class="w-6 h-6 rounded overflow-hidden border border-cyan-400/30 bg-slate-950 shrink-0 flex items-center justify-center">
                    <img
                      v-if="hasRenderableImagePath(item.image_url as string)"
                      :src="getImageUrl(item.image_url as string)"
                      class="w-full h-full object-cover"
                      :alt="item.name"
                    >
                    <i v-else :class="['ra text-[11px]', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
                  </div>
                  <span class="text-[11px] font-bold text-cyan-100 max-w-32 truncate">
                    {{ item.name }}
                  </span>
                </button>
                <span v-if="consumables.length === 0" class="text-xs text-slate-500">No consumables available.</span>
              </div>
            </div>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fight-fade-enter-active,
.fight-fade-leave-active {
  transition: opacity 0.2s ease;
}

.fight-fade-enter-from,
.fight-fade-leave-to {
  opacity: 0;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.35);
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(251, 191, 36, 0.25);
  border-radius: 6px;
}

.combat-log-entry {
  animation: combatLogIn 240ms ease-out both;
}

.attack-roll-card {
  animation: attackCardIn 260ms ease-out both;
}

.attack-roll-hit {
  box-shadow: 0 0 0 rgba(16, 185, 129, 0);
  animation: attackCardIn 260ms ease-out both, attackHitPulse 560ms ease-out 120ms;
}

.attack-roll-miss {
  box-shadow: 0 0 0 rgba(244, 63, 94, 0);
  animation: attackCardIn 260ms ease-out both, attackMissPulse 560ms ease-out 120ms;
}

.damage-float {
  position: absolute;
  left: 50%;
  bottom: 14px;
  transform: translateX(calc(-50% + var(--dx, 0px)));
  font-size: clamp(1.7rem, 3.8vw, 2.5rem);
  line-height: 1;
  font-weight: 900;
  letter-spacing: 0.05em;
  color: #fecdd3;
  text-shadow: 0 0 18px rgba(251, 113, 133, 0.85), 0 0 6px rgba(244, 63, 94, 0.75), 0 0 2px rgba(15, 23, 42, 0.9);
  animation: damageFloatUp 2600ms cubic-bezier(0.2, 0.68, 0.18, 1) forwards;
}

.impact-float {
  position: absolute;
  inset: 0;
  border-radius: 0.72rem;
  border: 1px solid rgba(251, 113, 133, 0.45);
  pointer-events: none;
}

.impact-float-light {
  animation: portraitImpactLight 620ms ease-out forwards;
}

.impact-float-heavy {
  animation: portraitImpactHeavy 900ms cubic-bezier(0.18, 0.7, 0.2, 1) forwards;
}

@keyframes combatLogIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes attackCardIn {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.985);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes attackHitPulse {
  0% {
    box-shadow: 0 0 0 rgba(16, 185, 129, 0);
  }
  50% {
    box-shadow: 0 0 22px rgba(16, 185, 129, 0.28);
  }
  100% {
    box-shadow: 0 0 0 rgba(16, 185, 129, 0);
  }
}

@keyframes attackMissPulse {
  0% {
    box-shadow: 0 0 0 rgba(244, 63, 94, 0);
  }
  50% {
    box-shadow: 0 0 18px rgba(244, 63, 94, 0.24);
  }
  100% {
    box-shadow: 0 0 0 rgba(244, 63, 94, 0);
  }
}

@keyframes damageFloatUp {
  0% {
    opacity: 0;
    transform: translateX(calc(-50% + var(--dx, 0px))) translateY(16px) scale(0.75);
  }
  12% {
    opacity: 1;
    transform: translateX(calc(-50% + var(--dx, 0px))) translateY(0) scale(1);
  }
  70% {
    opacity: 1;
    transform: translateX(calc(-50% + var(--dx, 0px))) translateY(-52px) scale(1.06);
  }
  100% {
    opacity: 0;
    transform: translateX(calc(-50% + var(--dx, 0px))) translateY(-96px) scale(1.08);
  }
}

@keyframes portraitImpactLight {
  0% {
    opacity: 0;
    box-shadow: inset 0 0 0 rgba(251, 113, 133, 0), 0 0 0 rgba(251, 113, 133, 0);
    transform: scale(1);
  }
  25% {
    opacity: 1;
    box-shadow: inset 0 0 18px rgba(251, 113, 133, 0.26), 0 0 14px rgba(251, 113, 133, 0.25);
    transform: scale(1.02);
  }
  100% {
    opacity: 0;
    box-shadow: inset 0 0 0 rgba(251, 113, 133, 0), 0 0 0 rgba(251, 113, 133, 0);
    transform: scale(1);
  }
}

@keyframes portraitImpactHeavy {
  0% {
    opacity: 0;
    transform: translateX(0) scale(1);
    box-shadow: inset 0 0 0 rgba(244, 63, 94, 0), 0 0 0 rgba(244, 63, 94, 0);
  }
  14% {
    opacity: 1;
    transform: translateX(-2px) scale(1.03);
    box-shadow: inset 0 0 26px rgba(244, 63, 94, 0.36), 0 0 22px rgba(244, 63, 94, 0.38);
  }
  28% {
    transform: translateX(2px) scale(1.02);
  }
  42% {
    transform: translateX(-1px) scale(1.02);
  }
  100% {
    opacity: 0;
    transform: translateX(0) scale(1);
    box-shadow: inset 0 0 0 rgba(244, 63, 94, 0), 0 0 0 rgba(244, 63, 94, 0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .combat-log-entry,
  .attack-roll-card,
  .attack-roll-hit,
  .attack-roll-miss,
  .damage-float {
    animation: none !important;
  }
}

.ra {
  font-family: 'rpgawesome' !important;
}
</style>
