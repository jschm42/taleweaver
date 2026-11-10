<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { FastForward, Maximize2, Minimize2 } from 'lucide-vue-next'
import type { CharacterSheet, CombatEnemyState, CombatState, InventoryItem } from '@/types'
import { getImageUrl, getItemIcon, getTypeColor, hasRenderableImagePath } from '@/utils/game_icons'
import { useDialogSkin } from '@/skins/dialogSkin'
import { audioDuck } from '@/store/audioPreferences'
import CombatAbilityHand from './combat/CombatAbilityHand.vue'
import CombatBystanders from './combat/CombatBystanders.vue'
import CombatItemTray from './combat/CombatItemTray.vue'
import CombatLogPanel from './combat/CombatLogPanel.vue'
import InitiativeTrack from './combat/InitiativeTrack.vue'

// PixiJS is only downloaded once a fight actually opens.
const CombatArena = defineAsyncComponent(() => import('./combat/CombatArena.vue'))
const FAST_STORAGE_KEY = 'taleweaver.combat.fast'
/** Background audio plays at this share of its volume while the fight's sound effects run. */
const COMBAT_AUDIO_DUCK = 0.55
/** At or below this share of max HP the stage warns with a pulsing red vignette. */
const LOW_HEALTH_RATIO = 0.25
const OUTCOME_TITLES = { victory: 'Victory', defeat: 'Defeat', escaped: 'Escaped' } as const

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
  attack: [targetId: string | null, weaponId: string | null]
  run: []
  rest: []
  special: [id: string, targetId: string | null]
  consume: [name: string]
  lootTake: [item: InventoryItem]
  lootLeave: [item: InventoryItem]
  lootDone: []
  /** A lost fight was acknowledged; the adventure is over, so nothing is sent to the server. */
  defeatDismissed: []
  lootTakeAll: []
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
  audioDuck.value = rendered ? COMBAT_AUDIO_DUCK : 1
  if (!rendered) leaveBrowserFullscreen()
}, { immediate: true })

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
/** NPCs in the scene who have not joined the fight; they are listed apart from the stage. */
const bystanders = computed(() => enemies.value.filter((e) => !e.engaged && isAlive(e)))
const fighterCount = computed(() => enemies.value.length - bystanders.value.length)

function onBystanderHover(id: string, event: MouseEvent): void {
  const entity = tooltipFor(id)
  if (entity) emit('entityHover', entity, event)
}

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

/** The result is announced on the stage once the last animation has played. */
const outcomeShown = computed(() => isFinished.value && !arenaPlaying.value)
const outcomeKind = computed<keyof typeof OUTCOME_TITLES>(() => {
  const outcome = props.combat?.outcome
  return outcome === 'defeat' || outcome === 'escaped' ? outcome : 'victory'
})

/** Closes a finished fight. A defeat hands over to the Game Over screen instead. */
function finishFight(): void {
  if (outcomeKind.value === 'defeat') {
    emit('defeatDismissed')
    return
  }
  emit('lootDone')
}

function asInt(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

const lowHealth = ref(false)

function refreshLowHealth(): void {
  // The server state is ahead of the arena; wait until the hit has been shown.
  if (arenaPlaying.value) return
  const hp = asInt(props.combat?.player?.hp)
  const maxHp = asInt(props.combat?.player?.max_hp)
  lowHealth.value = !!props.combat?.active && hp > 0 && maxHp > 0 && hp / maxHp <= LOW_HEALTH_RATIO
}

watch(() => [arenaPlaying.value, props.combat?.player?.hp, props.combat?.active], refreshLowHealth, { immediate: true })

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
  audioDuck.value = 1
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
          <div
            class="tw-combat-stage relative min-h-[420px] overflow-hidden flex flex-col"
            :class="{ [`is-${outcomeKind}`]: outcomeShown, 'is-low-health': lowHealth }"
          >
            <!-- The current scene sets the stage behind the cards. -->
            <div
              v-if="sceneBackground"
              class="tw-combat-backdrop absolute inset-0 bg-cover bg-center scale-105 blur-[2px] opacity-60"
              :style="{ backgroundImage: sceneBackground }"
              aria-hidden="true"
            ></div>
            <div class="absolute inset-0 bg-gradient-to-b from-black/40 via-black/10 to-black/70" aria-hidden="true"></div>
            <!-- Mood of the stage: danger at low health, gold on victory, blood on defeat. -->
            <div class="tw-combat-vignette absolute inset-0 pointer-events-none" aria-hidden="true"></div>

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
              <p v-if="combat.active && fighterCount > 1" class="absolute bottom-1 inset-x-0 text-center text-[11px] opacity-70 pointer-events-none">
                Click a card in the enemy stack or a portrait in the initiative order to choose your target.
              </p>

              <!-- Floats over the stage so it never moves the panels below. -->
              <Transition name="fight-status">
                <div v-if="evaluating" class="absolute bottom-7 inset-x-0 z-10 flex justify-center pointer-events-none" role="status">
                  <span class="tw-combat-pill tw-combat-eyebrow animate-pulse">
                    <i class="ra ra-hourglass animate-spin"></i> The Game Master is resolving the turn...
                  </span>
                </div>
              </Transition>

              <Transition name="tw-combat-outcome">
                <div v-if="outcomeShown" class="tw-combat-outcome" :class="`is-${outcomeKind}`" role="status">
                  <div class="tw-combat-outcome-title">{{ OUTCOME_TITLES[outcomeKind] }}</div>
                  <p class="tw-combat-outcome-note">{{ combat.status_note || 'The fight is over.' }}</p>
                  <p v-if="isLootPhase" class="tw-combat-eyebrow">Claim your spoils to continue</p>
                  <button
                    v-else
                    class="tw-dialog-button !px-8 !py-2"
                    :disabled="evaluating"
                    @click="finishFight"
                  >Continue</button>
                </div>
              </Transition>
            </div>

            <!-- Abilities are dealt like a hand of cards below the combatants. -->
            <CombatAbilityHand
              v-if="!isFinished"
              class="relative shrink-0"
              :combat="combat"
              :player-sheet="playerSheet"
              :locked="actionsLocked"
              :target-name="selectedTarget?.name ?? null"
              @attack="(weaponId) => emit('attack', selectedTargetId, weaponId)"
              @special="(id) => emit('special', id, selectedTargetId)"
              @hover="(entity, event) => emit('entityHover', entity, event)"
              @leave="emit('entityLeave')"
            />
          </div>

          <div class="flex flex-col gap-3 min-h-0 max-h-[40vh] md:max-h-none">
            <CombatBystanders
              v-if="combat.active && bystanders.length > 0"
              :bystanders="bystanders"
              :selected-target-id="selectedTargetId"
              @select="selectTarget"
              @hover="onBystanderHover"
              @leave="emit('entityLeave')"
            />
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
              <div class="mt-2.5 flex gap-2">
                <button
                  v-if="lootItems.length"
                  class="tw-dialog-button flex-1"
                  :disabled="evaluating"
                  title="Put all remaining loot into your inventory and end the fight"
                  @click="emit('lootTakeAll')"
                >Take All &amp; Finish</button>
                <button
                  class="tw-dialog-button flex-1"
                  :class="{ 'tw-dialog-button--ghost': lootItems.length }"
                  :disabled="evaluating"
                  :title="lootItems.length ? 'Leave the remaining loot lying in the scene' : 'End the fight'"
                  @click="emit('lootDone')"
                >{{ lootItems.length ? 'Drop Rest &amp; Finish' : 'Finish &amp; Continue' }}</button>
              </div>
            </section>
          </div>
        </div>

        <footer v-if="!isFinished || isDebug" class="tw-combat-footer relative shrink-0 border-t p-3 sm:px-4 space-y-3">
          <div v-if="isDebug" class="flex items-center gap-2 pb-2 border-b border-rose-500/20">
            <span class="text-[10px] font-black text-rose-400 uppercase tracking-widest mr-1">Debug</span>
            <button class="px-3 py-1 rounded bg-rose-900/40 border border-rose-500/30 text-rose-200 text-xs font-bold hover:bg-rose-800/60" @click="emit('debugWin')">Win fight</button>
            <button class="px-3 py-1 rounded bg-slate-800 border border-slate-600 text-slate-300 text-xs font-bold hover:bg-slate-700" @click="emit('debugLoose')">Lose fight</button>
          </div>

          <CombatItemTray
            v-if="!isFinished"
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
        </footer>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* The battle screen closes in on the stage when a fight opens. */
.fight-fade-enter-active {
  transition: opacity 0.35s ease;
}

.fight-fade-leave-active {
  transition: opacity 0.25s ease;
}

.fight-fade-enter-active .tw-combat-stage {
  transition: transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1);
}

.fight-fade-enter-from,
.fight-fade-leave-to,
.fight-status-enter-from,
.fight-status-leave-to {
  opacity: 0;
}

.fight-status-enter-active,
.fight-status-leave-active {
  transition: opacity 0.2s ease;
}

.fight-fade-enter-from .tw-combat-stage {
  transform: scale(1.06);
}

@media (prefers-reduced-motion: reduce) {
  .fight-fade-enter-active .tw-combat-stage {
    transition: none;
  }
}
</style>
