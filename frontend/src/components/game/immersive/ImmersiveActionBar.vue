<script setup lang="ts">
/**
 * ImmersiveActionBar — the dock under the story feed.
 *
 * Quick access to Quests, World Map, Hero Sheet, Chronicles, Hints, Memories (and Debug) as a
 * fanned hand of playing cards: each card shows its artwork (src/assets/menu-cards).
 * macOS-style magnification, plus the Action Ideas popup. The ornamental in-game clock sits
 * left of the cards and the experience counter right of them (wide screens only).
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
  inventory?: any[]
  trackedQuest?: any
  worldMemories?: any[]
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

const heroCardArt = computed(() => {
  const path = props.heroImage
  if (!path || heroArtStage.value === 'generic') return heroArt
  if (heroArtStage.value === 'full') return getOriginalImageUrl(path) || heroArt
  return getImageUrl(path, { thumbnail: true }) || heroArt
})

function onHeroArtError() {
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
  /** Signature hue of the card, blended with the theme's ink. */
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
      dot: !!props.trackedQuest,
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

/** Fan of the hand: cards tilt away from the middle and sink slightly towards the edges. */
function fanStyle(idx: number): Record<string, string> {
  const total = dockItems.value.length + 1
  const offset = idx - (total - 1) / 2
  return { '--rot': `${offset * 2.4}deg`, '--drop': `${Math.abs(offset) * 1.6}px` }
}

const ideasCount = computed(() => Math.min(props.promptSuggestions?.length || 0, 5))

// Dock magnification over all cards (the Ideas card is the last one).
const dockRef = ref<HTMLElement | null>(null)
const dock = useDockMagnification(dockRef, () => dockItems.value.length + 1)

// Short "launch" bounce of the clicked card.
const bouncingId = ref<string | null>(null)
let bounceTimer: number | null = null

function bounce(id: string) {
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

function activate(item: DockItem) {
  bounce(item.id)
  item.action()
}

const showIdeasPopup = ref(false)
const ideasWrapperRef = ref<HTMLElement | null>(null)
const isShuffling = ref(false)

function toggleIdeasPopup() {
  bounce('ideas')
  if (showIdeasPopup.value) {
    closeIdeasPopup()
  } else {
    openIdeasPopup()
  }
}

function openIdeasPopup() {
  showIdeasPopup.value = true
  if (!props.promptSuggestions?.length) {
    handleShuffleClick()
  }
  setTimeout(() => {
    document.addEventListener('mousedown', handleOutsideClick)
  }, 0)
}

function closeIdeasPopup() {
  showIdeasPopup.value = false
  document.removeEventListener('mousedown', handleOutsideClick)
}

function handleShuffleClick() {
  isShuffling.value = true
  emit('shuffleSuggestions')
  setTimeout(() => {
    isShuffling.value = false
  }, 1200)
}

function handleOutsideClick(event: MouseEvent) {
  const target = event.target as Node | null
  if (!target) return
  if (ideasWrapperRef.value && !ideasWrapperRef.value.contains(target)) {
    closeIdeasPopup()
  }
}

function handleSelectSuggestion(suggestion: string) {
  emit('selectSuggestion', suggestion)
  closeIdeasPopup()
}

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleOutsideClick)
  if (bounceTimer !== null) window.clearTimeout(bounceTimer)
})
</script>

<template>
  <div class="dock-row relative px-4 pt-4 pb-2">
    <FooterClock :game-time="props.gameTime || null" :clock-tick="props.clockTick" class="dock-side dock-side--left" />
    <div
      ref="dockRef"
      class="dock-shelf"
      @pointerenter="dock.onPointerEnter"
      @pointermove="dock.onPointerMove"
      @pointerleave="dock.onPointerLeave"
    >
      <div
        v-for="(item, idx) in dockItems"
        :key="item.id"
        data-dock-item
        class="dock-item"
        :style="{ '--i': idx, '--s': dock.scaleOf(idx), '--tint': item.tint, ...fanStyle(idx) }"
      >
        <button
          type="button"
          class="dock-card"
          :class="{ 'is-glowing': item.glow, 'is-bouncing': bouncingId === item.id }"
          :title="item.title"
          :aria-label="item.title"
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
            <component :is="item.icon" v-else class="dock-icon" />
          </span>
          <span v-if="item.badge" class="dock-badge">{{ item.badge }}</span>
        </button>
        <span class="dock-label" aria-hidden="true">{{ item.label }}</span>
        <span v-if="item.dot" class="dock-dot" aria-hidden="true"></span>
      </div>

      <span class="dock-divider" aria-hidden="true"></span>

      <!-- Ideas card with the Action Ideas popup -->
      <div
        ref="ideasWrapperRef"
        data-dock-item
        class="dock-item"
        :style="{ '--i': dockItems.length, '--s': dock.scaleOf(dockItems.length), '--tint': '#fbbf24', ...fanStyle(dockItems.length) }"
      >
        <button
          type="button"
          class="dock-card dock-card--ideas"
          :class="{ 'is-active': showIdeasPopup, 'is-bouncing': bouncingId === 'ideas' }"
          title="Prompt Suggestions & Ideas"
          aria-label="Prompt Suggestions & Ideas"
          :aria-expanded="showIdeasPopup"
          @click="toggleIdeasPopup"
        >
          <span class="dock-face">
            <img :src="ideasArt" class="dock-art" alt="" draggable="false" />
          </span>
          <span v-if="ideasCount" class="dock-badge">{{ ideasCount }}</span>
        </button>
        <span v-if="!showIdeasPopup" class="dock-label" aria-hidden="true">Ideas</span>

        <!-- Animated Ideas Popup -->
        <Transition name="popup-slide">
          <div
            v-if="showIdeasPopup"
            class="absolute bottom-full right-0 mb-3 w-80 sm:w-96 rounded-2xl bg-slate-900/95 backdrop-blur-xl border border-amber-500/30 shadow-[0_10px_35px_rgba(0,0,0,0.7)] p-3.5 z-50 flex flex-col gap-2.5"
          >
            <!-- Popup Header -->
            <div class="flex items-center justify-between pb-2 border-b border-slate-800">
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
            <div v-if="props.promptSuggestions?.length" class="flex flex-col gap-1.5 max-h-64 overflow-y-auto custom-scrollbar">
              <button
                v-for="(suggestion, sIdx) in props.promptSuggestions.slice(0, 5)"
                :key="sIdx"
                type="button"
                @click="handleSelectSuggestion(suggestion)"
                class="w-full text-left flex items-center gap-2.5 px-3 py-2 rounded-xl bg-slate-950/60 hover:bg-amber-500/15 border border-slate-800/80 hover:border-amber-400/50 text-slate-200 hover:text-amber-200 text-xs font-semibold transition-all group/item active:scale-[0.98] cursor-pointer"
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
  column-gap: 2.5rem;
}

.dock-row > .dock-shelf {
  grid-column: 2;
}

.dock-side--left {
  grid-column: 1;
  justify-self: end;
}

.dock-side--right {
  grid-column: 3;
  justify-self: start;
}

/* Narrow screens: the cards need the whole width. */
@media (max-width: 1023px) {
  .dock-side {
    display: none;
  }
}

/* ── Shelf ─────────────────────────────────────────────────────────────── */
.dock-shelf {
  /* Card width; cards are 2:3 playing cards, so their height is 1.5x. */
  --dock-base: 58px;
  display: inline-flex;
  align-items: flex-end;
  gap: 0.5rem;
  height: calc(var(--dock-base) * 1.5 + 16px);
  padding: 8px 14px;
  border-radius: calc(var(--tw-card-radius, 0.875rem) + 6px);
  /* No frame; a lightly see-through panel so the scene shows behind the cards. */
  border: none;
  background: color-mix(in srgb, var(--tw-panel-bg, #0f172a) 45%, transparent);
  box-shadow: 0 18px 40px -18px rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(10px) saturate(1.15);
}

@media (max-width: 640px) {
  .dock-shelf {
    --dock-base: 40px;
    gap: 0.35rem;
    padding: 6px 8px;
  }
}

.dock-divider {
  align-self: center;
  width: 1px;
  height: 60%;
  background: color-mix(in srgb, var(--tw-panel-ink, #e2e8f0) 18%, transparent);
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
  30% { transform: translateY(-16px) rotate(0deg) scale(1.04); }
  55% { transform: translateY(0) rotate(0deg) scale(0.97, 1.03); }
  75% { transform: translateY(-6px) rotate(0deg); }
  100% { transform: translateY(var(--drop, 0)) rotate(var(--rot, 0deg)); }
}

/* ── Ideas popup ───────────────────────────────────────────────────────── */
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
