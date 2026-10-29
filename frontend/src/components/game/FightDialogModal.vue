<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { FastForward, Maximize2, Minimize2 } from 'lucide-vue-next'
import type { CharacterSheet, CombatEnemyState, CombatState, InventoryItem } from '@/types'
import { getImageUrl, getItemIcon, getTypeColor, hasRenderableImagePath } from '@/utils/game_icons'
import { useDialogSkin } from '@/skins/dialogSkin'
import CombatAbilityHand from './combat/CombatAbilityHand.vue'
import CombatItemTray from './combat/CombatItemTray.vue'
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

const { activeSkin, skinStyle } = useDialogSkin()
const isRendered = computed(() => !!(props.open && props.combat))
const sceneBackground = computed(() => (
  hasRenderableImagePath(props.sceneImage) ? `url("${getImageUrl(props.sceneImage as string)}")` : null
))
const revealedCount = ref(0)
const arenaPlaying = ref(false)
const selectedTargetId = ref<string | null>(null)
const fast = ref(readFastPreference())
const prefersReducedMotion = ref(false)
const isBrowserFullscreen = ref(false)
const canUseBrowserFullscreen = typeof document !== 'undefined' && !!document.fullscreenEnabled
let motionQuery: MediaQueryList | null = null

/**
 * Hides the browser chrome on top of the viewport-filling dialog. The whole page goes
 * fullscreen (not just the dialog) so teleported tooltips stay visible.
 */
async function toggleBrowserFullscreen(): Promise<void> {
  try {
    if (document.fullscreenElement) {
      await document.exitFullscreen()
      return
    }
    await document.documentElement.requestFullscreen()
  } catch (err) {
    console.warn('Fullscreen request failed', err)
  }
}

function onFullscreenChange(): void {
  isBrowserFullscreen.value = !!document.fullscreenElement
}

function leaveBrowserFullscreen(): void {
  if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined)
}

watch(isRendered, (rendered) => {
  if (!rendered) leaveBrowserFullscreen()
})

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
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onBeforeUnmount(() => {
  motionQuery?.removeEventListener('change', onMotionChange)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  leaveBrowserFullscreen()
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fight-fade">
      <div
        v-if="isRendered && combat"
        class="tw-skin tw-combat fixed inset-0 z-[110] flex flex-col overflow-hidden"
        :data-skin="activeSkin"
        :style="[skinStyle, { pointerEvents: 'auto' }]"
        role="dialog"
        aria-modal="true"
        aria-label="Combat"
      >
        <header class="tw-combat-header relative shrink-0 px-4 sm:px-6 py-3 border-b flex flex-wrap items-center gap-x-4 gap-y-2">
          <h2 class="tw-combat-title text-sm sm:text-base font-black flex items-center gap-2">
            <i class="ra ra-crossed-swords"></i> Battle
          </h2>
          <span class="tw-combat-pill">
            <span class="opacity-70">Round</span>
            <span>{{ combat.round }}</span>
          </span>
          <span
            class="tw-combat-pill"
            :class="isPlayerTurn && !arenaPlaying ? 'tw-combat-pill--player' : 'tw-combat-pill--enemy'"
          >{{ turnLabel }}</span>
          <div class="flex-1"></div>
          <button
            type="button"
            class="tw-dialog-icon-button tw-combat-toggle gap-1.5 px-2.5 py-1 text-xs font-bold"
            :aria-pressed="fast"
            title="Speed up battle animations"
            @click="toggleFast"
          >
            <FastForward class="w-3.5 h-3.5" /> Fast
          </button>
          <button
            v-if="canUseBrowserFullscreen"
            type="button"
            class="tw-dialog-icon-button tw-combat-toggle w-7 h-7"
            :title="isBrowserFullscreen ? 'Exit fullscreen' : 'Fullscreen (hide browser bars)'"
            :aria-label="isBrowserFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'"
            :aria-pressed="isBrowserFullscreen"
            @click="toggleBrowserFullscreen"
          >
            <Minimize2 v-if="isBrowserFullscreen" class="w-3.5 h-3.5" />
            <Maximize2 v-else class="w-3.5 h-3.5" />
          </button>
        </header>

        <div class="relative flex-1 min-h-0 grid grid-cols-1 md:grid-cols-[1fr_340px] gap-3 p-2 sm:p-4">
          <div class="tw-combat-stage relative min-h-[420px] overflow-hidden flex flex-col">
            <!-- The current scene sets the stage behind the cards. -->
            <div
              v-if="sceneBackground"
              class="absolute inset-0 bg-cover bg-center scale-105 blur-[2px] opacity-60"
              :style="{ backgroundImage: sceneBackground }"
              aria-hidden="true"
            ></div>
            <div class="absolute inset-0 bg-gradient-to-b from-black/40 via-black/10 to-black/70" aria-hidden="true"></div>

            <!-- Acting order of this round; clicking an enemy portrait picks it as target. -->
            <div class="relative shrink-0 flex justify-center px-3 pt-3">
              <InitiativeTrack
                :combat="combat"
                :selected-target-id="selectedTargetId"
                :player-image="playerSheet?.profile_image ?? null"
                @select="selectTarget"
              />
            </div>

            <div class="relative flex-1 min-h-[220px]">
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
              <p v-if="combat.active && enemies.length > 1" class="absolute bottom-1 inset-x-0 text-center text-[11px] opacity-70 pointer-events-none">
                Click a card in the enemy stack or a portrait in the initiative order to choose your target.
              </p>
            </div>

            <!-- Abilities are dealt like a hand of cards below the combatants. -->
            <CombatAbilityHand
              v-if="!isFinished"
              class="relative shrink-0"
              :combat="combat"
              :player-sheet="playerSheet"
              :locked="actionsLocked"
              :target-name="selectedTarget?.name ?? null"
              @attack="emit('attack', selectedTargetId)"
              @special="(id) => emit('special', id, selectedTargetId)"
              @hover="(entity, event) => emit('entityHover', entity, event)"
              @leave="emit('entityLeave')"
            />
          </div>

          <div class="flex flex-col gap-3 min-h-0 max-h-[40vh] md:max-h-none">
            <CombatLogPanel class="flex-1" :entries="visibleLogs" :total="logs.length" />

            <section v-if="isLootPhase && !arenaPlaying" class="tw-combat-panel shrink-0 p-3">
              <div class="tw-combat-eyebrow mb-2">Spoils of Battle</div>
              <div v-if="lootItems.length === 0" class="text-sm opacity-70">Nothing worth taking.</div>
              <div v-else class="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                <div v-for="item in lootItems" :key="item.id || item.name" class="tw-combat-loot-row">
                  <span class="flex items-center gap-2 min-w-0">
                    <i :class="['ra text-sm', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
                    <span class="text-sm truncate">{{ item.name }}</span>
                  </span>
                  <span class="flex gap-1 shrink-0">
                    <button class="tw-dialog-button !px-2 !py-0.5" :disabled="evaluating" @click="emit('lootTake', item)">Take</button>
                    <button class="tw-dialog-button tw-dialog-button--ghost !px-2 !py-0.5" :disabled="evaluating" @click="emit('lootLeave', item)">Leave</button>
                  </span>
                </div>
              </div>
              <button class="tw-dialog-button mt-2.5 w-full" :disabled="evaluating" @click="emit('lootDone')">
                Finish &amp; Continue
              </button>
            </section>
          </div>
        </div>

        <footer class="tw-combat-footer relative shrink-0 border-t p-3 sm:px-4 space-y-3">
          <div v-if="isDebug" class="flex items-center gap-2 pb-2 border-b border-rose-500/20">
            <span class="text-[10px] font-black text-rose-400 uppercase tracking-widest mr-1">Debug</span>
            <button class="px-3 py-1 rounded bg-rose-900/40 border border-rose-500/30 text-rose-200 text-xs font-bold hover:bg-rose-800/60" @click="emit('debugWin')">Win fight</button>
            <button class="px-3 py-1 rounded bg-slate-800 border border-slate-600 text-slate-300 text-xs font-bold hover:bg-slate-700" @click="emit('debugLoose')">Lose fight</button>
          </div>

          <div v-if="isFinished && !isLootPhase" class="tw-combat-panel flex flex-wrap items-center justify-between gap-3 p-3">
            <span
              class="tw-combat-pill !text-sm"
              :class="combat.outcome === 'defeat' ? 'tw-combat-pill--enemy' : 'tw-combat-pill--player'"
            >{{ combat.outcome === 'defeat' ? 'Defeat' : combat.outcome === 'escaped' ? 'Escaped' : 'Victory' }}</span>
            <span class="text-sm opacity-75 italic flex-1 min-w-[200px]">{{ combat.status_note || 'The fight is over.' }}</span>
            <button
              class="tw-dialog-button !px-6"
              :disabled="evaluating || arenaPlaying"
              @click="emit('lootDone')"
            >Continue</button>
          </div>

          <CombatItemTray
            v-else-if="!isFinished"
            :combat="combat"
            :player-sheet="playerSheet"
            :consumables="consumables"
            :locked="actionsLocked"
            @consume="(name) => emit('consume', name)"
            @rest="emit('rest')"
            @run="emit('run')"
            @hover="(entity, event) => emit('entityHover', entity, event)"
            @leave="emit('entityLeave')"
          />

          <div v-if="evaluating" class="tw-combat-eyebrow animate-pulse text-center flex items-center justify-center gap-1.5">
            <i class="ra ra-hourglass animate-spin"></i> The Game Master is resolving the turn...
          </div>
        </footer>
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
