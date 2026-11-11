<script setup lang="ts">
/**
 * ImmersiveActionBar — the ornate playing-card dock under the story feed.
 *
 * Quick access to Quests, World Map, Hero Sheet, Chronicles, Hints, Memories (and Debug) as a
 * fanned hand of collector cards: each card shows its artwork (src/assets/menu-cards) with a
 * gilded frame. Hovering or focusing a card magnifies it prominently out of the hand, while
 * neighbours part and scale smoothly. The ornamental in-game clock sits left of the cards and
 * the experience counter right of them on wide screens.
 */
import { computed, onBeforeUnmount, ref, watch, type Component } from 'vue'
import {
  Scroll,
  Map as MapIcon,
  User,
  History,
  BrainCircuit,
  Terminal,
  Sparkles,
  RefreshCw,
  X,
  HelpCircle,
} from 'lucide-vue-next'
import { useDockMagnification } from '@/composables/useDockMagnification'
import { getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'
import FooterClock from './FooterClock.vue'
import FooterXp from './FooterXp.vue'
import type { GameTimeView } from './gameClockTime'
import heroArt from '@/assets/menu-cards/hero.webp'
import hintsArt from '@/assets/menu-cards/hints.webp'
import ideasArt from '@/assets/menu-cards/ideas.webp'
import logArt from '@/assets/menu-cards/log.webp'
import mapArt from '@/assets/menu-cards/map.webp'
import memoriesArt from '@/assets/menu-cards/memories.webp'
import questsArt from '@/assets/menu-cards/quests.webp'

const props = defineProps<{
  inventory?: unknown[]
  trackedQuest?: unknown
  worldMemories?: unknown[]
  inventoryGlow?: boolean
  mapGlow?: boolean
  questGlow?: boolean
  promptSuggestions?: string[]
  canSendInput?: boolean
  debugMode?: boolean
  gameTime?: GameTimeView | null
  clockTick?: boolean
  exp?: number
  /** The protagonist's portrait; the Hero card shows it instead of the generic artwork. */
  heroImage?: string | null
}>()

const emit = defineEmits<{
  openQuests: []
  openMap: []
  openSheet: []
  openChronicles: []
  openWalkthrough: []
  openMemories: []
  openDebug: []
  shuffleSuggestions: []
  selectSuggestion: [suggestion: string]
}>()

// --- Hero card: the protagonist's portrait (thumbnail -> full image -> generic artwork) ---
const heroArtStage = ref<'thumb' | 'full' | 'generic'>('thumb')
watch(
  () => props.heroImage,
  () => {
    heroArtStage.value = 'thumb'
  },
)

const heroCardArt = computed((): string => {
  const path = props.heroImage
  if (!path || heroArtStage.value === 'generic') return heroArt
  if (heroArtStage.value === 'full') return getOriginalImageUrl(path) || heroArt
  return getImageUrl(path, { thumbnail: true }) || heroArt
})

function onHeroArtError(): void {
  heroArtStage.value = heroArtStage.value === 'thumb' ? 'full' : 'generic'
}

interface DockItem {
  id: string
  label: string
  title: string
  icon: Component
  /** Card artwork; without it the card shows the icon large (e.g. Debug). */
  art?: string
  /** The artwork is a character portrait: keep the head in view when cropping. */
  portrait?: boolean
  /** Signature hue of the card, blended with the theme's ink and gilded frame. */
  tint: string
  badge?: number
  glow?: boolean
  dot?: boolean
  action: () => void
}

const dockItems = computed<DockItem[]>(() => {
  const items: DockItem[] = [
    {
      id: 'quests',
      art: questsArt,
      label: 'Quests',
      title: 'Open Quest Log',
      icon: Scroll,
      tint: '#fbbf24',
      glow: props.questGlow,
      dot: Boolean(props.trackedQuest),
      action: () => emit('openQuests'),
    },
    {
      id: 'map',
      art: mapArt,
      label: 'Map',
      title: 'Open World Map',
      icon: MapIcon,
      tint: '#38bdf8',
      glow: props.mapGlow,
      action: () => emit('openMap'),
    },
    {
      id: 'hero',
      art: heroCardArt.value,
      portrait: heroCardArt.value !== heroArt,
      label: 'Hero',
      title: 'Open Character Sheet & Inventory',
      icon: User,
      tint: '#34d399',
      glow: props.inventoryGlow,
      badge: props.inventory?.length || 0,
      action: () => emit('openSheet'),
    },
    {
      id: 'log',
      art: logArt,
      label: 'Log',
      title: 'Open Chronicles Timeline',
      icon: History,
      tint: '#818cf8',
      action: () => emit('openChronicles'),
    },
    {
      id: 'hints',
      art: hintsArt,
      label: 'Hints',
      title: 'Adventure Hints & Walkthrough',
      icon: HelpCircle,
      tint: '#f59e0b',
      action: () => emit('openWalkthrough'),
    },
    {
      id: 'memories',
      art: memoriesArt,
      label: 'Memories',
      title: 'World Memories & Chronicle',
      icon: BrainCircuit,
      tint: '#c084fc',
      badge: props.worldMemories?.length || 0,
      action: () => emit('openMemories'),
    },
  ]
  if (props.debugMode) {
    items.push({
      id: 'debug',
      label: 'Debug',
      title: 'Open Unified Debug Inspector',
      icon: Terminal,
      tint: '#22d3ee',
      action: () => emit('openDebug'),
    })
  }
  return items
})

const ideasIndex = computed((): number => dockItems.value.length)
const ideasCount = computed((): number => Math.min(props.promptSuggestions?.length || 0, 5))

// Dock magnification over all cards (the Ideas card is the last one).
const dockRef = ref<HTMLElement | null>(null)
const dock = useDockMagnification(dockRef, () => dockItems.value.length + 1, {
  maxScale: 1.72,
  radiusFactor: 2.1,
})

const showIdeasPopup = ref(false)
const ideasWrapperRef = ref<HTMLElement | null>(null)
const isShuffling = ref(false)

function isCardSelected(idx: number): boolean {
  if (idx === ideasIndex.value && showIdeasPopup.value && dock.activeIndex.value === null) {
    return true
  }
  return dock.activeIndex.value === idx
}

function isCardNeighbor(idx: number): boolean {
  const active = dock.activeIndex.value ?? (showIdeasPopup.value ? ideasIndex.value : null)
  if (active === null) return false
  return Math.abs(idx - active) === 1
}

function cardScale(idx: number): number {
  const s = dock.scaleOf(idx)
  if (idx === ideasIndex.value && showIdeasPopup.value && dock.activeIndex.value === null) {
    return Math.max(s, 1.46)
  }
  return s
}

/**
 * Parabolic fan arc: cards tilt away from the center and curve along a natural hand arc.
 * `--arc` is a unitless factor multiplied by `--dock-base` in CSS so it scales at every resolution.
 */
function itemStyle(idx: number, tint: string): Record<string, string | number> {
  const total = dockItems.value.length + 1
  const offset = idx - (total - 1) / 2
  const absOffset = Math.abs(offset)
  return {
    '--i': idx,
    '--s': Number(cardScale(idx).toFixed(3)),
    '--push': Number(dock.pushOf(idx).toFixed(3)),
    '--tint': tint,
    '--rot': `${(offset * 2.2).toFixed(2)}deg`,
    '--arc': (absOffset * absOffset * 0.011 + absOffset * 0.014).toFixed(4),
  }
}

// Short "launch" bounce of the clicked card.
const bouncingId = ref<string | null>(null)
let bounceTimer: number | null = null

function bounce(id: string): void {
  bouncingId.value = null
  if (bounceTimer !== null) window.clearTimeout(bounceTimer)
  requestAnimationFrame(() => {
    bouncingId.value = id
  })
  bounceTimer = window.setTimeout(() => {
    bouncingId.value = null
    bounceTimer = null
  }, 650)
}

function activate(item: DockItem): void {
  bounce(item.id)
  item.action()
}

function toggleIdeasPopup(): void {
  bounce('ideas')
  if (showIdeasPopup.value) {
    closeIdeasPopup()
  } else {
    openIdeasPopup()
  }
}

function openIdeasPopup(): void {
  showIdeasPopup.value = true
  if (!props.promptSuggestions?.length) {
    handleShuffleClick()
  }
  setTimeout(() => {
    document.addEventListener('mousedown', handleOutsideClick)
  }, 0)
}

function closeIdeasPopup(): void {
  showIdeasPopup.value = false
  document.removeEventListener('mousedown', handleOutsideClick)
}

function handleShuffleClick(): void {
  isShuffling.value = true
  emit('shuffleSuggestions')
  setTimeout(() => {
    isShuffling.value = false
  }, 1200)
}

function handleOutsideClick(event: MouseEvent): void {
  const target = event.target as Node | null
  if (!target) return
  if (ideasWrapperRef.value && !ideasWrapperRef.value.contains(target)) {
    closeIdeasPopup()
  }
}

function handleSelectSuggestion(suggestion: string): void {
  emit('selectSuggestion', suggestion)
  closeIdeasPopup()
}

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleOutsideClick)
  if (bounceTimer !== null) window.clearTimeout(bounceTimer)
})
</script>

<template>
  <div class="dock-row relative">
    <FooterClock :game-time="props.gameTime || null" :clock-tick="props.clockTick" class="dock-side dock-side--left" />
    <div
      ref="dockRef"
      class="dock-shelf"
      :class="{ 'has-selection': dock.activeIndex.value !== null || showIdeasPopup }"
      @pointerenter="dock.onPointerEnter"
      @pointermove="dock.onPointerMove"
      @pointerleave="dock.onPointerLeave"
    >
      <div
        v-for="(item, idx) in dockItems"
        :key="item.id"
        data-dock-item
        class="dock-item"
        :class="{
          'is-selected': isCardSelected(idx),
          'is-neighbor': isCardNeighbor(idx),
        }"
        :style="itemStyle(idx, item.tint)"
      >
        <button
          type="button"
          class="dock-card"
          :class="{
            'is-selected': isCardSelected(idx),
            'is-glowing': item.glow,
            'is-bouncing': bouncingId === item.id,
          }"
          :title="item.title"
          :aria-label="item.title"
          @focus="dock.onItemFocus(idx)"
          @blur="dock.onItemBlur(idx)"
          @click="activate(item)"
        >
          <span class="dock-face">
            <img
              v-if="item.art"
              :src="item.art"
              class="dock-art"
              :class="{ 'is-portrait': item.portrait }"
              alt=""
              draggable="false"
              @error="item.id === 'hero' && onHeroArtError()"
            />
            <component :is="item.icon" class="dock-icon" :class="{ 'dock-icon--mobile': !!item.art }" />
            <span class="dock-vignette" aria-hidden="true"></span>
          </span>
          <span v-if="item.badge" class="dock-badge">{{ item.badge }}</span>
        </button>
        <span class="dock-label" aria-hidden="true">
          <span class="dock-label-gem"></span>
          <span>{{ item.label }}</span>
          <span class="dock-label-gem"></span>
        </span>
        <span v-if="item.dot" class="dock-dot" aria-hidden="true"></span>
      </div>

      <span class="dock-divider" aria-hidden="true">
        <span class="dock-divider-gem"></span>
      </span>

      <!-- Ideas card with the Action Ideas popup -->
      <div
        ref="ideasWrapperRef"
        data-dock-item
        class="dock-item"
        :class="{
          'is-selected': isCardSelected(ideasIndex),
          'is-neighbor': isCardNeighbor(ideasIndex),
        }"
        :style="itemStyle(ideasIndex, '#fbbf24')"
      >
        <button
          type="button"
          class="dock-card dock-card--ideas"
          :class="{
            'is-selected': isCardSelected(ideasIndex),
            'is-active': showIdeasPopup,
            'is-bouncing': bouncingId === 'ideas',
          }"
          title="Prompt Suggestions & Ideas"
          aria-label="Prompt Suggestions & Ideas"
          :aria-expanded="showIdeasPopup"
          @focus="dock.onItemFocus(ideasIndex)"
          @blur="dock.onItemBlur(ideasIndex)"
          @click="toggleIdeasPopup"
        >
          <span class="dock-face">
            <img :src="ideasArt" class="dock-art" alt="" draggable="false" />
            <Sparkles class="dock-icon dock-icon--mobile" />
            <span class="dock-vignette" aria-hidden="true"></span>
          </span>
          <span v-if="ideasCount" class="dock-badge">{{ ideasCount }}</span>
        </button>
        <span v-if="!showIdeasPopup" class="dock-label" aria-hidden="true">
          <span class="dock-label-gem"></span>
          <span>Ideas</span>
          <span class="dock-label-gem"></span>
        </span>

        <!-- Animated Ideas Popup -->
        <Transition name="popup-slide">
          <div
            v-if="showIdeasPopup"
            class="ideas-popup rounded-2xl bg-slate-900/95 backdrop-blur-xl border border-amber-500/35 shadow-[0_14px_42px_rgba(0,0,0,0.82)] p-3.5 z-50 flex flex-col gap-2.5"
          >
            <!-- Popup Header -->
            <div class="flex items-center justify-between pb-2 border-b border-slate-800/90">
              <div class="flex items-center gap-1.5">
                <Sparkles class="w-4 h-4 text-amber-400" />
                <span class="text-xs font-black uppercase tracking-wider text-amber-200">Action Ideas</span>
              </div>
              <div class="flex items-center gap-1">
                <button
                  type="button"
                  @click="handleShuffleClick"
                  class="p-1 rounded-lg text-slate-400 hover:text-amber-300 hover:bg-amber-500/10 transition-colors cursor-pointer"
                  title="Regenerate Ideas (/shuffle)"
                >
                  <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isShuffling }" />
                </button>
                <button
                  type="button"
                  @click="closeIdeasPopup"
                  class="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
                  title="Close"
                >
                  <X class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            <!-- Suggestions List -->
            <div v-if="props.promptSuggestions?.length" class="ideas-popup-list flex flex-col gap-1.5 overflow-y-auto custom-scrollbar">
              <button
                v-for="(suggestion, sIdx) in props.promptSuggestions.slice(0, 5)"
                :key="sIdx"
                type="button"
                @click="handleSelectSuggestion(suggestion)"
                class="w-full text-left flex items-center gap-2.5 px-3 py-2 rounded-xl bg-slate-950/65 hover:bg-amber-500/15 border border-slate-800/80 hover:border-amber-400/50 text-slate-200 hover:text-amber-200 text-xs font-semibold transition-all group/item active:scale-[0.98] cursor-pointer"
              >
                <span class="w-1.5 h-1.5 rounded-full bg-amber-400/60 group-hover/item:bg-amber-400 shrink-0 transition-colors"></span>
                <span class="flex-1 leading-snug">{{ suggestion }}</span>
              </button>
            </div>

            <!-- Empty / Loading State -->
            <div v-else class="py-5 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
              <Sparkles class="w-5 h-5 text-amber-400/80 animate-spin" />
              <span class="font-medium">Generating situation-aware ideas...</span>
            </div>
          </div>
        </Transition>
      </div>
    </div>
    <FooterXp :exp="props.exp || 0" class="dock-side dock-side--right" />
  </div>
</template>

<style scoped>
/* ── Row: clock | cards | XP ───────────────────────────────────────────── */
.dock-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  column-gap: clamp(0.65rem, 2vw, 2.25rem);
  padding: clamp(0.45rem, 1.3dvh, 1rem) clamp(0.5rem, 2vw, 1.25rem) clamp(0.3rem, 0.8dvh, 0.55rem);
}

.dock-row > .dock-shelf {
  grid-column: 2;
}

.dock-side--left {
  grid-column: 1;
  justify-self: end;
  transform-origin: right center;
}

.dock-side--right {
  grid-column: 3;
  justify-self: start;
  transform-origin: left center;
}

/* Medium screens: compact the side ornaments slightly so the full-sized card hand fits comfortably. */
@media (max-width: 1279px) {
  .dock-side {
    transform: scale(0.88);
  }
}

/* Narrow or very short screens: header already displays clock and XP; give the cards the full row. */
@media (max-width: 1023px), (max-height: 580px) {
  .dock-row {
    grid-template-columns: 1fr;
    justify-items: center;
  }

  .dock-row > .dock-shelf {
    grid-column: 1;
  }

  .dock-side {
    display: none;
  }
}

/* ── Sculpted Card Shelf ───────────────────────────────────────────────── */
.dock-shelf {
  /*
   * Base card width (2:3 aspect ratio -> height is 1.5x).
   * Generous size on standard/wide desktop screens (~64px–68px wide at rest, ~115px when selected)
   * while scaling down smoothly on smaller laptop, tablet, and mobile viewports.
   */
  --dock-base: clamp(36px, min(5.4vw, 9.2dvh), 68px);
  --dock-pad-y: calc(var(--dock-base) * 0.14);
  --dock-pad-x: calc(var(--dock-base) * 0.36);
  --dock-tray: color-mix(in srgb, var(--tw-panel-bg, #0f172a) 48%, #04050a);
  position: relative;
  isolation: isolate;
  display: inline-flex;
  align-items: flex-end;
  justify-content: center;
  gap: calc(var(--dock-base) * 0.13);
  height: calc(var(--dock-base) * 1.5 + var(--dock-pad-y) * 2);
  padding: var(--dock-pad-y) var(--dock-pad-x);
  max-width: 100%;
}

@media (max-width: 1023px) {
  .dock-shelf {
    --dock-base: clamp(38px, min(8.6vw, 8.8dvh), 60px);
  }
}

/* Mobile view: compact, permanently visible horizontal row of action buttons. */
@media (max-width: 767px) {
  .dock-row {
    padding: 0.35rem 0.5rem 0.15rem;
  }

  .dock-shelf {
    --dock-base: clamp(32px, 9.8vw, 40px);
    height: auto;
    align-items: center;
    gap: clamp(0.28rem, 1.4vw, 0.5rem);
    padding: 0.3rem 0.55rem;
  }

  .dock-shelf::before {
    inset: 0;
    border-radius: 0.85rem;
  }

  .dock-shelf::after {
    display: none;
  }

  .dock-divider {
    height: 1.35rem;
    margin-inline: 0.1rem;
  }

  .dock-divider-gem {
    width: 4px;
    height: 4px;
  }
}

/* The sculpted obsidian-and-brass cradle the cards stand in. */
.dock-shelf::before {
  content: '';
  position: absolute;
  inset: 44% 0 0;
  z-index: -1;
  border-radius: calc(var(--dock-base) * 0.34);
  border: 1px solid color-mix(in srgb, var(--tw-accent, #f59e0b) 32%, rgba(255, 255, 255, 0.08));
  background:
    radial-gradient(65% 130% at 50% 0%, color-mix(in srgb, var(--tw-accent, #f59e0b) 22%, transparent), transparent 72%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--dock-tray) 68%, rgba(30, 41, 59, 0.5)),
      color-mix(in srgb, var(--dock-tray) 94%, #020305)
    );
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, var(--tw-accent, #f59e0b) 42%, rgba(255, 255, 255, 0.2)),
    inset 0 -1px 0 rgba(0, 0, 0, 0.7),
    0 20px 38px -14px rgba(0, 0, 0, 0.88),
    0 0 24px -8px color-mix(in srgb, var(--tw-accent, #f59e0b) 18%, transparent);
  backdrop-filter: blur(12px) saturate(1.25);
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
}

.dock-shelf.has-selection::before {
  border-color: color-mix(in srgb, var(--tw-accent, #f59e0b) 48%, rgba(255, 255, 255, 0.14));
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, var(--tw-accent, #f59e0b) 55%, rgba(255, 255, 255, 0.25)),
    inset 0 -1px 0 rgba(0, 0, 0, 0.75),
    0 22px 44px -12px rgba(0, 0, 0, 0.92),
    0 0 32px -6px color-mix(in srgb, var(--tw-accent, #f59e0b) 28%, transparent);
}

/* Invisible upper hover cushion so diagonal pointer movement between raised cards stays in the dock. */
.dock-shelf::after {
  content: '';
  position: absolute;
  inset: calc(var(--dock-base) * -0.95) 0 100%;
  pointer-events: auto;
}

/* Ornamental gilded divider with central diamond gem between the deck and Ideas. */
.dock-divider {
  position: relative;
  align-self: center;
  width: 1px;
  height: 58%;
  margin-inline: calc(var(--dock-base) * 0.08);
  background: linear-gradient(
    180deg,
    transparent,
    color-mix(in srgb, var(--tw-accent, #f59e0b) 65%, rgba(255, 255, 255, 0.2)) 50%,
    transparent
  );
  flex-shrink: 0;
}

.dock-divider-gem {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 5px;
  height: 5px;
  background: color-mix(in srgb, var(--tw-accent, #f59e0b) 85%, #ffffff);
  transform: translate(-50%, -50%) rotate(45deg);
  box-shadow: 0 0 6px color-mix(in srgb, var(--tw-accent, #f59e0b) 80%, transparent);
}

/* ── Animations ────────────────────────────────────────────────────────── */
.dock-card.is-glowing {
  animation: dock-glow 1.6s ease-in-out infinite;
}

.dock-card.is-bouncing {
  animation: dock-bounce 0.6s cubic-bezier(0.28, 0.84, 0.42, 1);
}

@keyframes dock-glow {
  0%,
  100% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--tint) 55%, transparent), 0 8px 18px -10px rgba(0, 0, 0, 0.8);
  }
  50% {
    box-shadow: 0 0 0 6px color-mix(in srgb, var(--tint) 0%, transparent), 0 0 24px -2px color-mix(in srgb, var(--tint) 75%, transparent);
  }
}

@keyframes dock-bounce {
  0% { transform: translateY(var(--drop, 0)) rotate(var(--rot, 0deg)); }
  30% { transform: translateY(calc(var(--card-w) * -0.34)) rotate(0deg) scale(1.05); }
  55% { transform: translateY(0) rotate(0deg) scale(0.97, 1.03); }
  75% { transform: translateY(calc(var(--card-w) * -0.12)) rotate(0deg); }
  100% { transform: translateY(var(--drop, 0)) rotate(var(--rot, 0deg)); }
}

/* ── Ideas popup (scalable across small & short viewports) ─────────────── */
.ideas-popup {
  position: absolute;
  bottom: calc(100% + var(--dock-base) * 0.55);
  right: 0;
  width: clamp(16.5rem, 78vw, 24rem);
  max-width: calc(100vw - 1.5rem);
}

.ideas-popup-list {
  max-height: min(16rem, 42dvh);
}

@media (max-width: 639px) {
  .ideas-popup {
    right: -0.5rem;
    width: min(22rem, calc(100vw - 1.25rem));
  }
}

.popup-slide-enter-active,
.popup-slide-leave-active {
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.popup-slide-enter-from,
.popup-slide-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.96);
}

.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 4px;
}
</style>

<style scoped src="./dockCards.css"></style>
