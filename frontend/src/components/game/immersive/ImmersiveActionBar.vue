<script setup lang="ts">
/**
 * ImmersiveActionBar — the dock under the story feed.
 *
 * Quick access to Quests, World Map, Hero Sheet, Chronicles, Hints, Memories (and Debug) as
 * theme-styled cards with macOS-style magnification, plus the Action Ideas popup.
 */
import { computed, onBeforeUnmount, ref, type Component } from 'vue'
import {
  Scroll,
  Map as MapIcon,
  User,
  History,
  Lightbulb,
  BrainCircuit,
  Terminal,
  Sparkles,
  RefreshCw,
  X,
  HelpCircle,
} from 'lucide-vue-next'
import { useDockMagnification } from '@/composables/useDockMagnification'

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

interface DockItem {
  id: string
  label: string
  title: string
  icon: Component
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
      label: 'Map',
      title: 'Open World Map',
      icon: MapIcon,
      tint: '#38bdf8',
      glow: props.mapGlow,
      action: () => emit('openMap'),
    },
    {
      id: 'hero',
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
      label: 'Log',
      title: 'Open Chronicles Timeline',
      icon: History,
      tint: '#818cf8',
      action: () => emit('openChronicles'),
    },
    {
      id: 'hints',
      label: 'Hints',
      title: 'Adventure Hints & Walkthrough',
      icon: HelpCircle,
      tint: '#f59e0b',
      action: () => emit('openWalkthrough'),
    },
    {
      id: 'memories',
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
  <div class="relative flex justify-center px-4 pt-4 pb-2">
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
        :style="{ '--i': idx, '--s': dock.scaleOf(idx), '--tint': item.tint }"
      >
        <button
          type="button"
          class="dock-card"
          :class="{ 'is-glowing': item.glow, 'is-bouncing': bouncingId === item.id }"
          :title="item.title"
          :aria-label="item.title"
          @click="activate(item)"
        >
          <component :is="item.icon" class="dock-icon" />
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
        :style="{ '--i': dockItems.length, '--s': dock.scaleOf(dockItems.length), '--tint': '#fbbf24' }"
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
          <Lightbulb class="dock-icon" />
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
  </div>
</template>

<style scoped>
/* ── Shelf ─────────────────────────────────────────────────────────────── */
.dock-shelf {
  --dock-base: 46px;
  display: inline-flex;
  align-items: flex-end;
  gap: 0.55rem;
  height: calc(var(--dock-base) + 14px);
  padding: 7px 12px;
  border-radius: calc(var(--tw-card-radius, 0.875rem) + 6px);
  border: 1px solid var(--tw-panel-border, rgba(51, 65, 85, 0.9));
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--tw-panel-ink, #e2e8f0) 6%, transparent), transparent 60%),
    color-mix(in srgb, var(--tw-panel-bg, #0f172a) 72%, transparent);
  box-shadow:
    0 18px 40px -18px rgba(0, 0, 0, 0.75),
    inset 0 1px 0 color-mix(in srgb, var(--tw-panel-ink, #e2e8f0) 10%, transparent);
  backdrop-filter: blur(14px) saturate(1.2);
}

@media (max-width: 640px) {
  .dock-shelf {
    --dock-base: 38px;
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

/* ── Card ──────────────────────────────────────────────────────────────── */
.dock-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.dock-card {
  --card-size: calc(var(--dock-base) * var(--s, 1));
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--card-size);
  height: var(--card-size);
  border-radius: var(--tw-card-radius, 0.875rem);
  border: 1px solid var(--tw-card-border, rgba(51, 65, 85, 0.9));
  background:
    radial-gradient(120% 90% at 30% 15%, color-mix(in srgb, var(--tint) 26%, transparent), transparent 65%),
    var(--tw-card-bg, rgba(15, 23, 42, 0.85));
  color: color-mix(in srgb, var(--tint) 72%, var(--tw-card-ink, #e2e8f0));
  box-shadow:
    0 8px 18px -10px rgba(0, 0, 0, 0.8),
    inset 0 1px 0 color-mix(in srgb, var(--tw-card-ink, #e2e8f0) 12%, transparent);
  cursor: pointer;
  transition:
    width 0.16s cubic-bezier(0.2, 0.8, 0.2, 1),
    height 0.16s cubic-bezier(0.2, 0.8, 0.2, 1),
    transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1),
    border-color 0.2s ease,
    box-shadow 0.25s ease;
}

.dock-card:hover,
.dock-card:focus-visible {
  transform: translateY(-5px);
  border-color: color-mix(in srgb, var(--tw-accent, #f59e0b) 65%, var(--tw-card-border, #334155));
  box-shadow:
    0 14px 28px -12px color-mix(in srgb, var(--tint) 70%, transparent),
    0 0 0 1px color-mix(in srgb, var(--tw-accent, #f59e0b) 30%, transparent),
    inset 0 1px 0 color-mix(in srgb, var(--tw-card-ink, #e2e8f0) 18%, transparent);
  outline: none;
}

.dock-card:active {
  transform: translateY(-2px) scale(0.94);
}

.dock-card--ideas.is-active {
  border-color: var(--tw-accent, #f59e0b);
  box-shadow:
    0 0 22px -4px color-mix(in srgb, var(--tw-accent, #f59e0b) 70%, transparent),
    inset 0 0 0 1px color-mix(in srgb, var(--tw-accent, #f59e0b) 35%, transparent);
}

.dock-icon {
  width: 46%;
  height: 46%;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.45));
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.dock-card:hover .dock-icon {
  transform: rotate(-6deg) scale(1.06);
}

.dock-badge {
  position: absolute;
  top: -5px;
  right: -5px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9999px;
  font: 800 10px/18px var(--tw-font-label, ui-sans-serif, system-ui, sans-serif);
  text-align: center;
  color: #0b1120;
  background: color-mix(in srgb, var(--tint) 85%, #ffffff);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.5);
}

/* Label bubble above the hovered card. */
.dock-label {
  position: absolute;
  bottom: calc(var(--dock-base) * var(--s, 1) + 14px);
  left: 50%;
  padding: 3px 9px;
  border-radius: 8px;
  white-space: nowrap;
  pointer-events: none;
  font: 700 10px/1.4 var(--tw-font-label, ui-sans-serif, system-ui, sans-serif);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--tw-panel-ink, #e2e8f0);
  background: var(--tw-panel-bg, #0f172a);
  border: 1px solid var(--tw-panel-border, rgba(51, 65, 85, 0.9));
  box-shadow: 0 8px 18px -8px rgba(0, 0, 0, 0.7);
  opacity: 0;
  transform: translate(-50%, 6px) scale(0.9);
  transition:
    opacity 0.15s ease,
    transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1),
    bottom 0.16s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.dock-item:hover .dock-label,
.dock-item:focus-within .dock-label {
  opacity: 1;
  transform: translate(-50%, 0) scale(1);
}

/* "Running app" dot: the tracked quest. */
.dock-dot {
  position: absolute;
  bottom: -6px;
  width: 4px;
  height: 4px;
  border-radius: 9999px;
  background: var(--tint);
  box-shadow: 0 0 6px var(--tint);
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
  0% { transform: translateY(0); }
  30% { transform: translateY(-14px) scale(1.04); }
  55% { transform: translateY(0) scale(0.97, 1.03); }
  75% { transform: translateY(-5px); }
  100% { transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .dock-card,
  .dock-label,
  .dock-icon {
    transition: none;
  }
  .dock-card.is-glowing,
  .dock-card.is-bouncing {
    animation: none;
  }
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
