<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { FastForward } from 'lucide-vue-next'
import type { CharacterSheet, CombatEnemyState, CombatState, InventoryItem } from '@/types'
import { getImageUrl, getItemIcon, getTypeColor, hasRenderableImagePath } from '@/utils/game_icons'
import CombatActionBar from './combat/CombatActionBar.vue'
import CombatLogPanel from './combat/CombatLogPanel.vue'
import InitiativeTrack from './combat/InitiativeTrack.vue'

// PixiJS is only downloaded once a fight actually opens.
const CombatArena = defineAsyncComponent(() => import('./combat/CombatArena.vue'))
const FAST_STORAGE_KEY = 'taleweaver.combat.fast'

const props = defineProps<{
  open: boolean
  combat: CombatState | null
  consumables: InventoryItem[]
  npcMetadata: Record<string, any>
  playerSheet: CharacterSheet | null
  evaluating?: boolean
  isDebug?: boolean
  sceneImage?: string | null
}>()

const emit = defineEmits<{
  attack: [targetId: string | null]
  run: []
  rest: []
  special: [id: string, targetId: string | null]
  consume: [name: string]
  lootTake: [item: InventoryItem]
  lootLeave: [item: InventoryItem]
  lootDone: []
  entityHover: [entity: any, event: MouseEvent]
  entityLeave: []
  debugWin: []
  debugLoose: []
}>()

const isRendered = computed(() => !!(props.open && props.combat))
const sceneBackground = computed(() => (
  hasRenderableImagePath(props.sceneImage) ? `url("${getImageUrl(props.sceneImage as string)}")` : null
))
const revealedCount = ref(0)
const arenaPlaying = ref(false)
const selectedTargetId = ref<string | null>(null)
const fast = ref(readFastPreference())
const prefersReducedMotion = ref(false)
let motionQuery: MediaQueryList | null = null

function readFastPreference(): boolean {
  try {
    return window.localStorage.getItem(FAST_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function toggleFast(): void {
  fast.value = !fast.value
  try {
    window.localStorage.setItem(FAST_STORAGE_KEY, fast.value ? '1' : '0')
  } catch {
    // Preference simply isn't remembered.
  }
}

const enemies = computed<CombatEnemyState[]>(() => {
  const c = props.combat
  if (!c) return []
  return c.enemies?.length ? c.enemies : c.enemy ? [c.enemy] : []
})

function isAlive(enemy: CombatEnemyState | undefined): boolean {
  return !!enemy && !enemy.defeated && !enemy.fled && (enemy.hp ?? 0) > 0
}

const selectedTarget = computed(() => enemies.value.find((e) => e.id === selectedTargetId.value) ?? null)

function ensureValidTarget(): void {
  if (isAlive(selectedTarget.value ?? undefined)) return
  const list = enemies.value
  const preferred = list.find((e) => e.id === props.combat?.target_id)
  const fallback = [preferred, ...list.filter((e) => e.engaged), ...list].find(isAlive)
  selectedTargetId.value = fallback?.id ?? null
}

watch(() => [props.combat?.target_id, enemies.value], ensureValidTarget, { immediate: true, deep: false })

function selectTarget(id: string): void {
  const enemy = enemies.value.find((e) => e.id === id)
  if (isAlive(enemy)) selectedTargetId.value = id
}

const logs = computed(() => props.combat?.log ?? [])
const visibleLogs = computed(() => logs.value.slice(0, revealedCount.value))
const lootItems = computed(() => props.combat?.loot_items ?? [])
const isLootPhase = computed(() => !!props.combat?.loot_pending)
const isFinished = computed(() => !!props.combat && !props.combat.active)
const isPlayerTurn = computed(() => !!props.combat?.active && props.combat.turn === 'player')
const actionsLocked = computed(() => !!props.evaluating || arenaPlaying.value || !isPlayerTurn.value)

const turnLabel = computed(() => {
  if (isFinished.value) return props.combat?.outcome ?? 'ended'
  if (arenaPlaying.value || props.evaluating) return 'resolving'
  return isPlayerTurn.value ? 'your move' : 'enemy'
})

function asInt(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function tooltipFor(entityId: string): Record<string, unknown> | null {
  const c = props.combat
  if (!c) return null
  if (entityId === 'PLAYER') {
    const sheet = props.playerSheet
    return {
      id: 'PLAYER',
      entity_type: 'NPC',
      name: sheet?.name ? `You (${sheet.name})` : c.player.name,
      description: sheet?.description || 'Your character in this adventure.',
      image_url: c.player.image_url || sheet?.profile_image || null,
      hp: asInt(c.player.hp),
      max_hp: asInt(c.player.max_hp),
      stamina: asInt(c.player.stamina),
      max_stamina: asInt(c.player.max_stamina),
      mana: asInt(c.player.mana),
      max_mana: asInt(c.player.max_mana),
      inventory: sheet?.inventory ?? [],
    }
  }
  const enemy = enemies.value.find((e) => e.id === entityId)
  if (!enemy) return null
  const base = (props.npcMetadata?.[enemy.id] || props.npcMetadata?.[enemy.name] || {}) as Record<string, unknown>
  return {
    ...base,
    id: enemy.id,
    name: enemy.name,
    entity_type: 'NPC',
    image_url: enemy.image_url || base.image_url || null,
    description: (base.description as string) || 'A dangerous opponent in this fight.',
    hp: enemy.hp,
    max_hp: enemy.max_hp,
    stamina: asInt(enemy.stamina),
    max_stamina: asInt(enemy.max_stamina),
    mana: asInt(enemy.mana),
    max_mana: asInt(enemy.max_mana),
    inventory: enemy.inventory ?? [],
  }
}

function onArenaHover(entityId: string | null, event: MouseEvent | null): void {
  const entity = entityId ? tooltipFor(entityId) : null
  if (entity && event) {
    emit('entityHover', entity, event)
    return
  }
  emit('entityLeave')
}

function onMotionChange(event: MediaQueryListEvent): void {
  prefersReducedMotion.value = event.matches
}

onMounted(() => {
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  prefersReducedMotion.value = motionQuery.matches
  motionQuery.addEventListener('change', onMotionChange)
})

onBeforeUnmount(() => {
  motionQuery?.removeEventListener('change', onMotionChange)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fight-fade">
      <div
        v-if="isRendered && combat"
        class="fixed inset-0 z-[110] bg-slate-950/85 backdrop-blur-md p-2 sm:p-5 flex items-center justify-center"
        style="pointer-events: auto;"
        role="dialog"
        aria-modal="true"
        aria-label="Combat"
      >
        <div class="relative w-full max-w-7xl h-[92vh] sm:h-[88vh] border border-amber-700/40 bg-gradient-to-b from-slate-900/95 via-slate-900 to-slate-950 rounded-2xl shadow-[0_0_80px_rgba(251,191,36,0.18)] overflow-hidden flex flex-col">
          <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_15%,rgba(16,185,129,0.07),transparent_55%),radial-gradient(circle_at_80%_80%,rgba(244,63,94,0.08),transparent_55%)]"></div>

          <header class="relative shrink-0 px-4 sm:px-6 py-3 border-b border-amber-500/20 bg-slate-950/60 flex flex-wrap items-center gap-x-4 gap-y-2">
            <h2 class="text-sm sm:text-base uppercase tracking-[0.28em] text-amber-300 font-black flex items-center gap-2">
              <i class="ra ra-crossed-swords"></i> Battle
            </h2>
            <span class="px-2.5 py-1 rounded-full border border-amber-500/25 bg-slate-950/60 text-xs">
              <span class="uppercase tracking-[0.18em] text-amber-300/70 font-bold">Round</span>
              <span class="ml-1.5 font-black text-amber-200">{{ combat.round }}</span>
            </span>
            <span
              class="px-2.5 py-1 rounded-full border text-xs uppercase tracking-[0.16em] font-black"
              :class="isPlayerTurn && !arenaPlaying ? 'border-emerald-500/40 text-emerald-300' : 'border-rose-500/40 text-rose-300'"
            >{{ turnLabel }}</span>
            <div class="flex-1 min-w-0">
              <InitiativeTrack :combat="combat" />
            </div>
            <button
              type="button"
              class="flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-bold transition-colors"
              :class="fast ? 'border-amber-300/70 bg-amber-500/20 text-amber-100' : 'border-slate-600 text-slate-400 hover:text-slate-200'"
              :aria-pressed="fast"
              title="Speed up battle animations"
              @click="toggleFast"
            >
              <FastForward class="w-3.5 h-3.5" /> Fast
            </button>
          </header>

          <div class="relative flex-1 min-h-0 grid grid-cols-1 md:grid-cols-[1fr_300px] gap-3 p-2 sm:p-4">
            <div class="relative min-h-[260px] rounded-xl border border-amber-500/10 bg-slate-950/40 overflow-hidden">
              <!-- The current scene sets the stage behind the cards. -->
              <div
                v-if="sceneBackground"
                class="absolute inset-0 bg-cover bg-center scale-105 blur-[2px] opacity-60"
                :style="{ backgroundImage: sceneBackground }"
                aria-hidden="true"
              ></div>
              <div class="absolute inset-0 bg-gradient-to-b from-slate-950/40 via-slate-950/20 to-slate-950/80" aria-hidden="true"></div>
              <CombatArena
                :combat="combat"
                :selected-target-id="selectedTargetId"
                :fast="fast"
                :reduced-motion="prefersReducedMotion"
                @select-target="selectTarget"
                @revealed="revealedCount = $event"
                @playing="arenaPlaying = $event"
                @hover="onArenaHover"
              />
              <p v-if="combat.active && enemies.length > 1" class="absolute bottom-2 inset-x-0 text-center text-[11px] text-slate-400/80 pointer-events-none">
                Click a card in the enemy stack to choose your target.
              </p>
            </div>

            <div class="flex flex-col gap-3 min-h-0 max-h-[40vh] md:max-h-none">
              <CombatLogPanel class="flex-1" :entries="visibleLogs" :total="logs.length" />

              <section v-if="isLootPhase && !arenaPlaying" class="shrink-0 border border-amber-500/25 bg-slate-950/70 rounded-xl p-3">
                <div class="text-[11px] uppercase tracking-[0.2em] text-amber-300/80 mb-2 font-black">Spoils of Battle</div>
                <div v-if="lootItems.length === 0" class="text-sm text-slate-400">Nothing worth taking.</div>
                <div v-else class="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                  <div v-for="item in lootItems" :key="item.id || item.name" class="flex items-center justify-between gap-2 p-2 rounded-lg bg-slate-900/80 border border-slate-700/50">
                    <span class="flex items-center gap-2 min-w-0">
                      <i :class="['ra text-sm', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
                      <span class="text-sm text-slate-200 truncate">{{ item.name }}</span>
                    </span>
                    <span class="flex gap-1 shrink-0">
                      <button class="px-2 py-0.5 text-xs font-black rounded bg-emerald-700/80 hover:bg-emerald-600 text-white disabled:opacity-40" :disabled="evaluating" @click="emit('lootTake', item)">Take</button>
                      <button class="px-2 py-0.5 text-xs font-black rounded bg-slate-700 hover:bg-slate-600 text-white disabled:opacity-40" :disabled="evaluating" @click="emit('lootLeave', item)">Leave</button>
                    </span>
                  </div>
                </div>
                <button class="mt-2.5 w-full px-4 py-2 text-xs font-black rounded-lg bg-amber-600 hover:bg-amber-500 text-white uppercase tracking-[0.16em] disabled:opacity-40" :disabled="evaluating" @click="emit('lootDone')">
                  Finish & Continue
                </button>
              </section>
            </div>
          </div>

          <footer class="relative shrink-0 border-t border-amber-500/20 bg-slate-950/80 p-3 sm:p-4 space-y-3">
            <div v-if="isDebug" class="flex items-center gap-2 pb-2 border-b border-rose-500/20">
              <span class="text-[10px] font-black text-rose-400 uppercase tracking-widest mr-1">Debug</span>
              <button class="px-3 py-1 rounded bg-rose-900/40 border border-rose-500/30 text-rose-200 text-xs font-bold hover:bg-rose-800/60" @click="emit('debugWin')">Win fight</button>
              <button class="px-3 py-1 rounded bg-slate-800 border border-slate-600 text-slate-300 text-xs font-bold hover:bg-slate-700" @click="emit('debugLoose')">Lose fight</button>
            </div>

            <div v-if="isFinished && !isLootPhase" class="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl border border-amber-500/20 bg-slate-950/40">
              <span
                class="text-sm font-black uppercase tracking-widest px-3 py-1.5 rounded border"
                :class="combat.outcome === 'defeat' ? 'text-rose-400 border-rose-500/30 bg-rose-500/10' : 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'"
              >{{ combat.outcome === 'defeat' ? 'Defeat' : combat.outcome === 'escaped' ? 'Escaped' : 'Victory' }}</span>
              <span class="text-sm text-slate-400 italic flex-1 min-w-[200px]">{{ combat.status_note || 'The fight is over.' }}</span>
              <button
                class="px-6 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-sm font-black uppercase tracking-[0.2em] disabled:opacity-50"
                :disabled="evaluating || arenaPlaying"
                @click="emit('lootDone')"
              >Continue</button>
            </div>

            <CombatActionBar
              v-else-if="!isFinished"
              :combat="combat"
              :player-sheet="playerSheet"
              :consumables="consumables"
              :locked="actionsLocked"
              :target-name="selectedTarget?.name ?? null"
              @attack="emit('attack', selectedTargetId)"
              @special="(id) => emit('special', id, selectedTargetId)"
              @consume="(name) => emit('consume', name)"
              @rest="emit('rest')"
              @run="emit('run')"
              @hover="(entity, event) => emit('entityHover', entity, event)"
              @leave="emit('entityLeave')"
            />

            <div v-if="evaluating" class="text-xs text-amber-300/80 animate-pulse text-center flex items-center justify-center gap-1.5">
              <i class="ra ra-hourglass animate-spin"></i> The Game Master is resolving the turn...
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
</style>
