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
  isDebug?: boolean
}>()

const emit = defineEmits<{
  attack: []
  run: []
  rest: []
  consume: [name: string]
  lootTake: [item: InventoryItem]
  lootLeave: [item: InventoryItem]
  lootDone: []
  entityHover: [entity: any, event: MouseEvent]
  entityLeave: []
  debugWin: []
  debugLoose: []
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
const currentAnimationStartIndex = ref(0)
const activeTurn = computed(() => {
  // If we are currently revealing new logs sequentially, sync the turn glow
  // with the source of the most recently revealed log of this turn.
  if (visibleLogCount.value < parsedLogs.value.length) {
    for (let i = visibleLogCount.value - 1; i >= currentAnimationStartIndex.value; i--) {
      const log = parsedLogs.value[i]
      if (log) {
        if (log.source === 'YOU') return 'player'
        if (log.source === 'ENEMY') return 'enemy'
      }
    }
  }

  if (props.evaluating) {
    return 'enemy'
  }
  return props.combat?.turn || 'player'
})
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

const isRendered = computed(() => !!(props.open && props.combat))

const combatIdentity = computed(() => {
  const c = props.combat
  if (!c || !c.player || !c.enemy) return ''
  return `${c.player.name}::${c.enemy.id}`
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
  currentAnimationStartIndex.value = 0
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
    currentAnimationStartIndex.value = startIndex
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
  isCrit?: boolean
  damageDice?: string
  damageExpression?: string
  damageTotal?: number
}

function parseAttackRoll(text: string): AttackRollView | null {
  const rx = /^(.*?) ATTACK ROLL: (\d+) \+ (-?\d+) = (\d+) vs AC (\d+) -> (HIT|MISS|CRITICAL HIT)(?: \| DMG ([^ ]+) \(([^)]*)\) = (\d+))?$/
  const match = text.match(rx)
  if (!match) return null
  return {
    attacker: match[1].trim(),
    hitRoll: Number(match[2]),
    hitModifier: Number(match[3]),
    hitTotal: Number(match[4]),
    targetAc: Number(match[5]),
    isHit: match[6] === 'HIT' || match[6] === 'CRITICAL HIT',
    isCrit: match[6] === 'CRITICAL HIT',
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
    stamina: asInt(player.stamina, asInt(sheet?.stamina)),
    max_stamina: asInt(player.max_stamina, asInt(sheet?.max_stamina)),
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
    stamina: asInt(enemy.stamina, asInt(base.stamina)),
    max_stamina: asInt(enemy.max_stamina, asInt(base.max_stamina)),
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

const mainHandItem = computed(() => {
  return props.playerSheet?.equipment?.MainHand || null
})

const playerStamina = computed(() => {
  return asInt(props.combat?.player?.stamina, asInt(props.playerSheet?.stamina))
})

const isAttackDisabled = computed(() => {
  return !isPlayerTurn.value || isInteractionLocked.value || playerStamina.value < 20 || (props.combat?.enemy?.hp ?? 0) <= 0
})

const attackSlotClass = computed(() => {
  if (!isPlayerTurn.value || (props.combat?.enemy?.hp ?? 0) <= 0) {
    return 'border-slate-800 bg-slate-950/20 opacity-50 cursor-not-allowed text-slate-500'
  }
  if (playerStamina.value < 20) {
    return 'border-rose-900/60 bg-rose-950/20 text-rose-400 hover:border-rose-800/80 cursor-not-allowed ring-1 ring-rose-500/20'
  }
  return 'border-emerald-500/30 bg-emerald-950/10 hover:bg-emerald-950/20 hover:border-emerald-500/60 text-emerald-200 cursor-pointer shadow-[0_0_10px_rgba(16,185,129,0.05)] hover:shadow-[0_0_15px_rgba(16,185,129,0.15)]'
})

const restSlotClass = computed(() => {
  if (!isPlayerTurn.value || (props.combat?.enemy?.hp ?? 0) <= 0) {
    return 'border-slate-800 bg-slate-950/20 opacity-50 cursor-not-allowed text-slate-500'
  }
  if (playerStamina.value < 20) {
    return 'border-emerald-500 bg-emerald-950/20 text-emerald-100 cursor-pointer ring-2 ring-emerald-500 ring-offset-2 ring-offset-slate-950 animate-pulse'
  }
  return 'border-slate-700 bg-slate-900/40 hover:bg-slate-800/60 hover:border-slate-500 text-slate-200 cursor-pointer'
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fight-fade">
      <div 
        v-if="isRendered" 
        class="fixed inset-0 z-[110] bg-slate-950/70 backdrop-blur-sm p-3 sm:p-6 md:p-8 flex items-center justify-center"
        style="pointer-events: auto;"
      >
        <div class="w-full max-w-6xl h-[80vh] border border-amber-700/40 bg-gradient-to-b from-slate-900/95 via-slate-900 to-slate-950 rounded-2xl shadow-[0_0_60px_rgba(251,191,36,0.15)] overflow-hidden flex flex-col">
          <header class="shrink-0 px-5 py-4 border-b border-amber-500/20 bg-slate-950/60 flex items-center justify-between">
            <h2 class="text-base sm:text-lg uppercase tracking-[0.22em] text-amber-300 font-black">Turn-Based Combat</h2>
            <div class="text-sm text-slate-300">
              Round <span class="font-black text-amber-200">{{ combat.round }}</span>
              <span class="mx-2 text-slate-600">|</span>
              Turn: <span class="font-black" :class="activeTurn === 'player' ? 'text-emerald-300' : 'text-rose-300'">{{ activeTurn }}</span>
            </div>
          </header>

          <div class="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-[260px_1fr_260px] gap-3 p-3 md:p-4">
            <section
              class="bg-slate-900/80 rounded-xl p-4 flex flex-col items-center justify-start transition-all duration-300"
              :class="activeTurn === 'player'
                ? 'active-turn-player'
                : 'border border-emerald-500/20'"
              @mouseenter="protagonistTooltipEntity && emitHover(protagonistTooltipEntity, $event)"
              @mousemove="protagonistTooltipEntity && emitHover(protagonistTooltipEntity, $event)"
              @mouseleave="emitLeave"
            >
              <div class="text-xs uppercase tracking-[0.2em] text-emerald-300/80 mb-3 font-bold">Protagonist</div>
              <div class="relative w-32 h-32 sm:w-44 sm:h-44 rounded-xl overflow-hidden bg-slate-950 transition-all duration-300"
                :class="activeTurn === 'player'
                  ? 'active-turn-player'
                  : 'border border-emerald-400/40'"
              >
                <!-- Defeated Ribbon -->
                <div v-if="combat.player?.hp <= 0" class="absolute -right-10 top-3 bg-red-600 text-white text-xs font-black uppercase tracking-[0.15em] py-1 w-32 text-center rotate-45 shadow-lg z-10">
                  Defeated
                </div>
                <img v-if="hasRenderableImagePath(combat.player?.image_url) && !playerImageFailed" :src="getImageUrl(combat.player?.image_url)" class="w-full h-full object-cover object-top transition-all" :class="{ 'grayscale opacity-50': combat.player?.hp <= 0 }" alt="protagonist" @error="onPlayerImageError">
                <div v-else class="w-full h-full flex items-center justify-center text-emerald-300 ra ra-player text-4xl" :class="{ 'grayscale opacity-40': combat.player?.hp <= 0 }"></div>
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
              <div class="mt-3 text-sm text-white font-bold text-center">{{ combat.player?.name }}</div>
              <div class="mt-3 w-full">
                <StatBar label="HP" :value="asInt(combat.player?.hp)" :max="asInt(combat.player?.max_hp)" color="crimson" size="sm" />
                <StatBar label="Stamina" :value="asInt(combat.player?.stamina, asInt(playerSheet?.stamina))" :max="asInt(combat.player?.max_stamina, asInt(playerSheet?.max_stamina))" color="emerald" size="sm" />
                <StatBar v-if="asInt(playerSheet?.max_mana) > 0" label="Mana" :value="asInt(playerSheet?.mana)" :max="asInt(playerSheet?.max_mana)" color="sapphire" size="sm" />
              </div>
            </section>

            <section class="border border-amber-500/20 bg-slate-900/80 rounded-xl min-h-0 flex flex-col">
              <div class="px-4 py-2.5 border-b border-amber-500/15 text-xs uppercase tracking-[0.2em] text-amber-300/80 font-bold">
                Battle Chronicle
              </div>
              <div ref="logContainerRef" class="flex-1 min-h-0 overflow-y-auto custom-scrollbar px-4 py-3 space-y-3">
                <div v-for="(entry, idx) in visibleLogs" :key="makeLogKey(entry, idx)" class="combat-log-entry text-sm md:text-base leading-relaxed border-l-2 pl-3"
                  :class="entry.type === 'special' ? 'border-violet-400/60 text-violet-200' : entry.type === 'enemy_action' ? 'border-rose-500/50 text-rose-200' : entry.type === 'player_action' ? 'border-emerald-500/50 text-emerald-200' : 'border-amber-500/40 text-slate-200'">
                  <div class="mb-1.5">
                    <span :class="['text-xs px-2 py-0.5 rounded border font-black uppercase tracking-[0.12em]', sourceClass(entry.source)]">
                      {{ entry.source }}
                    </span>
                  </div>
                  <template v-if="entry.attackRoll">
                    <div :class="['rounded-lg border p-3 attack-roll-card', attackCardClass(entry.isPlayerAttack), entry.attackRoll.isHit ? 'attack-roll-hit' : 'attack-roll-miss']">
                      <div class="flex items-center justify-between text-xs md:text-sm font-semibold flex-wrap gap-2">
                        <div class="flex items-center gap-2">
                          <span :class="['text-xs px-1.5 py-0.5 rounded border font-black uppercase tracking-wider', attackLabelClass(entry.isPlayerAttack)]">
                            ⚔ {{ entry.attackRoll.isCrit ? 'CRIT' : 'ATTACK' }}
                          </span>
                          <span class="text-slate-300 font-bold text-sm">{{ entry.attackRoll.attacker }}</span>
                        </div>
                        <div class="flex items-center gap-2.5">
                          <span class="text-slate-400 text-xs">Roll:</span>
                          <span class="font-mono text-cyan-300 bg-slate-800/80 px-1.5 py-0.5 rounded border border-cyan-500/20 text-xs font-bold">
                            {{ entry.attackRoll.hitRoll }}+{{ entry.attackRoll.hitModifier }} = {{ entry.attackRoll.hitTotal }}
                          </span>
                          <span class="text-slate-400 text-xs">vs AC:</span>
                          <span class="font-mono text-violet-300 bg-slate-800/80 px-1.5 py-0.5 rounded border border-violet-500/20 text-xs font-bold">
                            {{ entry.attackRoll.targetAc }}
                          </span>
                          <span class="px-2 py-0.5 rounded text-xs font-black uppercase tracking-wider"
                            :class="entry.attackRoll.isCrit ? 'bg-amber-600/80 text-amber-100 border border-amber-400/40 animate-pulse' : entry.attackRoll.isHit ? 'bg-emerald-600/80 text-emerald-100 border border-emerald-400/30' : 'bg-rose-600/80 text-rose-100 border border-rose-400/30'">
                            {{ entry.attackRoll.isCrit ? 'Crit Hit' : entry.attackRoll.isHit ? 'Hit' : 'Miss' }}
                          </span>
                        </div>
                      </div>
                      <div v-if="entry.attackRoll.isHit && entry.attackRoll.damageTotal != null" class="mt-2 flex items-center justify-between text-xs border-t border-slate-700/30 pt-2 flex-wrap gap-2">
                        <div class="flex items-center gap-1.5 text-slate-400 text-xs">
                          <span>Damage Dice:</span>
                          <span class="font-mono text-rose-300">{{ entry.attackRoll.damageDice }}</span>
                          <span class="text-xs text-slate-500">({{ entry.attackRoll.damageExpression }})</span>
                        </div>
                        <div class="font-bold text-rose-400 text-xs">
                          Dealt <span class="text-rose-200 text-sm bg-rose-950/40 border border-rose-500/20 px-2 py-0.5 rounded font-black">{{ entry.attackRoll.damageTotal }}</span> dmg
                        </div>
                      </div>
                    </div>
                  </template>
                  <template v-else>
                    <span class="text-sm md:text-base">{{ entry.text }}</span>
                  </template>
                </div>
              </div>

              <div v-if="isLootPhase" class="border-t border-amber-500/15 px-4 py-3">
                <div class="text-xs uppercase tracking-[0.2em] text-amber-300/80 mb-2 font-bold">Loot Summary</div>
                <div v-if="lootItems.length === 0" class="text-sm text-slate-400">No loot left.</div>
                <div v-else class="space-y-2 max-h-40 overflow-y-auto custom-scrollbar pr-1">
                  <div v-for="item in lootItems" :key="item.id || item.name" class="flex items-center justify-between gap-3 p-2.5 rounded-lg bg-slate-950/70 border border-slate-700/50">
                    <div class="flex items-center gap-2.5 min-w-0">
                      <i :class="['ra text-base', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
                      <span class="text-sm text-slate-200 truncate">{{ item.name }}</span>
                    </div>
                    <div class="flex items-center gap-1.5 shrink-0">
                      <button class="px-2.5 py-1 text-xs font-black rounded bg-emerald-700/80 hover:bg-emerald-600 text-white disabled:opacity-40" :disabled="isInteractionLocked" @click="emit('lootTake', item)">Take</button>
                      <button class="px-2.5 py-1 text-xs font-black rounded bg-slate-700 hover:bg-slate-600 text-white disabled:opacity-40" :disabled="isInteractionLocked" @click="emit('lootLeave', item)">Leave</button>
                    </div>
                  </div>
                </div>
                <div class="mt-2.5 flex justify-end">
                  <button class="px-4 py-2 text-xs font-black rounded bg-amber-700 hover:bg-amber-600 text-white uppercase tracking-[0.08em] disabled:opacity-40" :disabled="isInteractionLocked" @click="emit('lootDone')">
                    Finish Loot
                  </button>
                </div>
              </div>
            </section>

            <section
              class="bg-slate-900/80 rounded-xl p-4 flex flex-col items-center justify-start transition-all duration-300"
              :class="activeTurn === 'enemy'
                ? 'active-turn-enemy'
                : 'border border-rose-500/20'"
              @mouseenter="enemyTooltipEntity && emitHover(enemyTooltipEntity, $event)"
              @mousemove="enemyTooltipEntity && emitHover(enemyTooltipEntity, $event)"
              @mouseleave="emitLeave"
            >
              <div class="text-xs uppercase tracking-[0.2em] text-rose-300/80 mb-3 font-bold">Enemy</div>
              <div class="relative w-32 h-32 sm:w-44 sm:h-44 rounded-xl overflow-hidden bg-slate-950 transition-all duration-300"
                :class="activeTurn === 'enemy'
                  ? 'active-turn-enemy'
                  : 'border border-rose-400/40'"
              >
                <!-- Defeated Ribbon -->
                <div v-if="combat.enemy?.hp <= 0" class="absolute -right-10 top-3 bg-red-600 text-white text-xs font-black uppercase tracking-[0.15em] py-1 w-32 text-center rotate-45 shadow-lg z-10">
                  Defeated
                </div>
                <img v-if="hasRenderableImagePath(combat.enemy?.image_url) && !enemyImageFailed" :src="getImageUrl(combat.enemy?.image_url)" class="w-full h-full object-cover object-top transition-all" :class="{ 'grayscale opacity-50': combat.enemy?.hp <= 0 }" alt="enemy" @error="onEnemyImageError">
                <div v-else class="w-full h-full flex items-center justify-center text-rose-300 ra ra-monster-skull text-4xl" :class="{ 'grayscale opacity-40': combat.enemy?.hp <= 0 }"></div>
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
              <div class="mt-3 text-sm text-white font-bold text-center">
                {{ combat.enemy?.name }}
                <div v-if="isDebug" class="text-xs font-mono text-rose-300 opacity-60">ID: {{ combat.enemy?.id }}</div>
              </div>
              <div class="mt-3 w-full">
                <StatBar label="HP" :value="asInt(combat.enemy?.hp)" :max="asInt(combat.enemy?.max_hp)" color="crimson" size="sm" />
                <StatBar v-if="asInt(combat.enemy?.max_stamina, asInt(enemyTooltipEntity?.max_stamina)) > 0" label="Stamina" :value="asInt(combat.enemy?.stamina, asInt(enemyTooltipEntity?.stamina))" :max="asInt(combat.enemy?.max_stamina, asInt(enemyTooltipEntity?.max_stamina))" color="emerald" size="sm" />
                <StatBar v-if="asInt(enemyTooltipEntity?.max_mana) > 0" label="Mana" :value="asInt(enemyTooltipEntity?.mana)" :max="asInt(enemyTooltipEntity?.max_mana)" color="sapphire" size="sm" />
              </div>
            </section>
          </div>

          <footer class="shrink-0 border-t border-amber-500/20 bg-slate-950/70 p-3.5 space-y-3.5">
            <!-- Debug Controls -->
            <div v-if="isDebug" class="flex items-center gap-2 pb-2 mb-2 border-b border-rose-500/20">
              <span class="text-xs font-black text-rose-400 uppercase tracking-widest mr-2">Debug Actions:</span>
              <button 
                class="px-3.5 py-1.5 rounded bg-rose-900/40 border border-rose-500/30 text-rose-200 text-xs font-bold hover:bg-rose-800/60 transition-colors"
                @click="emit('debugWin')"
              >
                Win fight (DEBUG)
              </button>
              <button 
                class="px-3.5 py-1.5 rounded bg-slate-800 border border-slate-600 text-slate-300 text-xs font-bold hover:bg-slate-700 transition-colors"
                @click="emit('debugLoose')"
              >
                Loose fight (DEBUG)
              </button>
            </div>

            <!-- Victory/Defeat Acknowledgment / Loot Done -->
            <div v-if="!combat.active && !isLootPhase && combat.outcome" class="flex items-center justify-between bg-slate-950/40 p-3.5 rounded-xl border border-amber-500/20 animate-fade-in">
              <div 
                class="text-sm md:text-base font-black uppercase tracking-widest px-3.5 py-2 rounded border shadow-lg"
                :class="combat.outcome === 'victory' ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' : 'text-rose-400 border-rose-500/30 bg-rose-500/10'"
              >
                {{ combat.outcome === 'victory' ? 'Victory' : 'Defeat' }}
              </div>
              <div class="text-sm text-slate-400 max-w-md italic">{{ combat.status_note || 'The fight is concluded.' }}</div>
              <button
                class="px-6 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-sm font-black uppercase tracking-[0.2em] shadow-[0_0_20px_rgba(217,119,6,0.3)] transition-all transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="isInteractionLocked"
                @click="emit('lootDone')"
              >
                Continue
              </button>
            </div>

            <!-- Active Combat Interface -->
            <div v-else class="grid grid-cols-1 lg:grid-cols-[220px_1fr_260px] gap-3.5 items-stretch">
              
              <!-- Slot 1: Equipped Item (Main Hand Slot) -->
              <div 
                class="flex flex-col justify-between p-3 rounded-xl border transition-all"
                :class="attackSlotClass"
                @click="emit('attack')"
                @mouseenter="mainHandItem && emitHover({ ...mainHandItem, entity_type: 'ITEM' }, $event)"
                @mousemove="mainHandItem && emitHover({ ...mainHandItem, entity_type: 'ITEM' }, $event)"
                @mouseleave="emitLeave"
              >
                <div class="flex items-center justify-between">
                  <span class="text-xs uppercase font-black tracking-widest text-slate-400">Main Hand</span>
                  <span class="text-xs font-black px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-500/30 text-emerald-400">
                    ⚡ 20 STA
                  </span>
                </div>
                
                <div class="flex items-center gap-3 my-2">
                  <div class="w-12 h-12 rounded bg-slate-950 border border-slate-700/50 flex items-center justify-center shrink-0">
                    <img 
                      v-if="mainHandItem && hasRenderableImagePath(mainHandItem.image_url)" 
                      :src="getImageUrl(mainHandItem.image_url)" 
                      class="w-full h-full object-cover" 
                      :alt="mainHandItem.name"
                    >
                    <i v-else-if="mainHandItem" :class="['ra text-2xl', getItemIcon(mainHandItem.item_type), getTypeColor(mainHandItem.item_type)]"></i>
                    <!-- Hand/Fist silhouette placeholder if nothing equipped -->
                    <i v-else class="ra ra-hand text-slate-600 text-2xl"></i>
                  </div>
                  <div class="min-w-0">
                    <div class="text-sm font-bold text-slate-100 truncate">
                      {{ mainHandItem ? mainHandItem.name : 'Bare Fists' }}
                    </div>
                    <div class="text-xs text-slate-400 truncate">
                      {{ mainHandItem && mainHandItem.damage ? `Dmg: ${mainHandItem.damage}` : 'Click to punch' }}
                    </div>
                  </div>
                </div>

                <div class="text-xs text-center font-bold" :class="isAttackDisabled ? 'text-rose-400' : 'text-emerald-400'">
                  {{ isAttackDisabled ? (playerStamina < 20 ? 'Insufficient Stamina' : 'Not Your Turn') : 'Click to Attack' }}
                </div>
              </div>

              <!-- Slot 2: Consumables grid row -->
              <div class="border border-slate-800 bg-slate-900/20 rounded-xl p-3 flex flex-col justify-between">
                <span class="text-xs uppercase font-black tracking-widest text-slate-400 mb-1.5">Consumables</span>
                <div class="flex-grow flex items-center">
                  <div class="flex flex-wrap gap-2.5 w-full">
                    <button
                      v-for="item in consumables"
                      :key="item.id || item.name"
                      class="group flex items-center gap-2.5 px-3 py-2 rounded-lg border border-cyan-500/25 bg-cyan-950/20 hover:bg-cyan-900/30 hover:border-cyan-400/40 disabled:opacity-40 disabled:hover:bg-cyan-950/20 transition-all text-left"
                      @mouseenter="emitHover(toConsumableTooltipEntity(item), $event)"
                      @mousemove="emitHover(toConsumableTooltipEntity(item), $event)"
                      @mouseleave="emitLeave"
                      :disabled="!isPlayerTurn || isInteractionLocked"
                      @click="emit('consume', item.name)"
                    >
                      <div class="w-8 h-8 rounded overflow-hidden border border-cyan-500/30 bg-slate-950 shrink-0 flex items-center justify-center">
                        <img
                          v-if="hasRenderableImagePath(item.image_url as string)"
                          :src="getImageUrl(item.image_url as string)"
                          class="w-full h-full object-cover"
                          :alt="item.name"
                        >
                        <i v-else :class="['ra text-sm', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
                      </div>
                      <div class="min-w-0 pr-1">
                        <span class="text-xs font-bold text-cyan-200 block truncate max-w-28">
                          {{ item.name }}
                        </span>
                        <span class="text-[10px] text-cyan-400/70 block">Use item</span>
                      </div>
                    </button>
                    <span v-if="consumables.length === 0" class="text-sm text-slate-500 italic my-auto">No consumable items in inventory.</span>
                  </div>
                </div>
              </div>

              <!-- Slot 3: Tactical Actions (Rest & Run) -->
              <div class="grid grid-cols-2 gap-2.5">
                <!-- Rest button -->
                <div 
                  class="flex flex-col justify-between p-3 rounded-xl border transition-all"
                  :class="restSlotClass"
                  @click="emit('rest')"
                >
                  <div class="flex items-center justify-between">
                    <span class="text-xs uppercase font-black tracking-widest text-slate-400">Action</span>
                    <span class="text-xs font-black px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-500/30 text-emerald-400">
                      +40 STA
                    </span>
                  </div>
                  
                  <div class="flex flex-col items-center justify-center my-1.5">
                    <i class="ra ra-hourglass text-xl mb-1" :class="playerStamina < 20 ? 'text-emerald-400 animate-pulse' : 'text-slate-400'"></i>
                    <span class="text-xs font-bold block text-center">Rest & Recover</span>
                  </div>

                  <div class="text-xs text-center text-slate-400 font-bold">
                    {{ playerStamina < 20 ? '★ REST REQUIRED ★' : 'Skip & recover' }}
                  </div>
                </div>

                <!-- Run button -->
                <div 
                  class="flex flex-col justify-between p-3 rounded-xl border border-slate-700 bg-slate-900/40 hover:bg-rose-950/10 hover:border-rose-900/50 text-slate-200 cursor-pointer transition-all"
                  :class="{ 'opacity-50 cursor-not-allowed': !isPlayerTurn || isInteractionLocked }"
                  @click="emit('run')"
                >
                  <span class="text-xs uppercase font-black tracking-widest text-slate-400">Flee</span>
                  
                  <div class="flex flex-col items-center justify-center my-1.5">
                    <i class="ra ra-running text-xl text-rose-400/80 mb-1"></i>
                    <span class="text-xs font-bold block text-center">Escape</span>
                  </div>

                  <div class="text-xs text-center text-rose-400/80 font-bold">
                    Dexterity check
                  </div>
                </div>
              </div>

            </div>

            <!-- Game Master resolving indicator -->
            <div v-if="isInteractionLocked" class="text-sm text-amber-300/80 animate-pulse text-center flex items-center justify-center gap-1.5 py-1.5">
              <i class="ra ra-hourglass animate-spin"></i>
              <span>Game Master is resolving the turn...</span>
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

.active-turn-player {
  border: 1px solid rgba(59, 130, 246, 0.7);
  animation: activePlayerGlow 2.5s infinite ease-in-out;
}

.active-turn-enemy {
  border: 1px solid rgba(239, 68, 68, 0.7);
  animation: activeEnemyGlow 2.5s infinite ease-in-out;
}

@keyframes activePlayerGlow {
  0%, 100% {
    box-shadow: 0 0 6px rgba(59, 130, 246, 0.35);
    border-color: rgba(59, 130, 246, 0.4);
  }
  50% {
    box-shadow: 0 0 18px rgba(59, 130, 246, 0.8);
    border-color: rgba(59, 130, 246, 0.95);
  }
}

@keyframes activeEnemyGlow {
  0%, 100% {
    box-shadow: 0 0 6px rgba(239, 68, 68, 0.35);
    border-color: rgba(239, 68, 68, 0.4);
  }
  50% {
    box-shadow: 0 0 18px rgba(239, 68, 68, 0.8);
    border-color: rgba(239, 68, 68, 0.95);
  }
}

@media (prefers-reduced-motion: reduce) {
  .combat-log-entry,
  .attack-roll-card,
  .attack-roll-hit,
  .attack-roll-miss,
  .damage-float,
  .active-turn-player,
  .active-turn-enemy {
    animation: none !important;
  }
}

.ra {
  font-family: 'rpgawesome' !important;
}
</style>
