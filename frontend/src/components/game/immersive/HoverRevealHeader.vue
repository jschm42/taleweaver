<script setup lang="ts">
/**
 * HoverRevealHeader — Keeps the game header out of the way until it is needed.
 * Unpinned, it is hidden and slides in over the stage when the pointer reaches the top edge
 * (or the handle is tapped on touch devices). Pinned, it is part of the layout again.
 * While hidden, a mouse approaching the top edge lights up a glow line and the handle, so the
 * player sees that a menu waits there.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ChevronDown, Pin, PinOff } from 'lucide-vue-next'
import { isGameHeaderPinned, toggleGameHeaderPin } from '@/store/layout'

const HIDE_DELAY_MS = 350
/** Distance from the top edge (px) at which the hidden header starts to announce itself. */
const NEAR_RANGE_PX = 140

const root = ref<HTMLElement | null>(null)
const isRevealed = ref(false)
let hideTimer: ReturnType<typeof setTimeout> | null = null

const isVisible = computed(() => isGameHeaderPinned.value || isRevealed.value)

// --- Proximity hint: 0 (far) .. 1 (at the edge), plus the pointer's x for the glow ---
const nearness = ref(0)
const nearX = ref(50)
let nearFrame = 0

function trackPointer(event: PointerEvent): void {
  if (event.pointerType !== 'mouse' || nearFrame) return
  const { clientX, clientY } = event
  nearFrame = requestAnimationFrame(() => {
    nearFrame = 0
    const box = root.value?.getBoundingClientRect()
    if (!box || !box.width) return
    const distance = Math.max(0, clientY - box.top)
    nearness.value = Math.max(0, 1 - distance / NEAR_RANGE_PX)
    nearX.value = Math.min(100, Math.max(0, ((clientX - box.left) / box.width) * 100))
  })
}

function stopTracking(): void {
  window.removeEventListener('pointermove', trackPointer)
  if (nearFrame) cancelAnimationFrame(nearFrame)
  nearFrame = 0
  nearness.value = 0
}

watch(
  isVisible,
  (visible) => {
    if (visible) {
      stopTracking()
      return
    }
    window.addEventListener('pointermove', trackPointer, { passive: true })
  },
  { immediate: true }
)

const hintStyle = computed(() => ({
  '--near': nearness.value.toFixed(3),
  '--near-x': `${nearX.value.toFixed(1)}%`,
}))

function clearHideTimer(): void {
  if (!hideTimer) return
  clearTimeout(hideTimer)
  hideTimer = null
}

function reveal(): void {
  clearHideTimer()
  isRevealed.value = true
}

function scheduleHide(): void {
  clearHideTimer()
  hideTimer = setTimeout(() => {
    isRevealed.value = false
  }, HIDE_DELAY_MS)
}

function handleFocusOut(event: FocusEvent): void {
  if (root.value?.contains(event.relatedTarget as Node | null)) return
  scheduleHide()
}

// Touch devices have no mouseleave: a tap outside hides the revealed header.
function handlePointerDownOutside(event: PointerEvent): void {
  if (root.value?.contains(event.target as Node | null)) return
  isRevealed.value = false
}

watch(isRevealed, (revealed) => {
  if (revealed) {
    document.addEventListener('pointerdown', handlePointerDownOutside)
    return
  }
  document.removeEventListener('pointerdown', handlePointerDownOutside)
})

onBeforeUnmount(() => {
  stopTracking()
  clearHideTimer()
  document.removeEventListener('pointerdown', handlePointerDownOutside)
})
</script>

<template>
  <div
    ref="root"
    class="relative z-40 shrink-0"
    @mouseenter="reveal"
    @mouseleave="scheduleHide"
    @focusin="reveal"
    @focusout="handleFocusOut"
  >
    <!-- Pinned: in the layout. Revealed by hover: floats over the stage so nothing jumps. -->
    <div v-if="isVisible" :class="isGameHeaderPinned ? 'relative' : 'absolute inset-x-0 top-0 animate-header-in'">
      <slot />
      <button
        type="button"
        class="absolute left-1/2 top-full -translate-x-1/2 flex items-center gap-1.5 rounded-b-lg border border-t-0 border-slate-700/60 bg-slate-950/80 px-3 py-0.5 text-[10px] font-bold uppercase tracking-widest backdrop-blur-md transition-colors"
        :class="isGameHeaderPinned ? 'text-amber-300 hover:text-amber-200' : 'text-slate-400 hover:text-slate-100'"
        :title="isGameHeaderPinned ? 'Unpin: show the header only on hover' : 'Pin the header so it stays visible'"
        :aria-pressed="isGameHeaderPinned"
        @click="toggleGameHeaderPin"
      >
        <PinOff v-if="isGameHeaderPinned" class="w-3 h-3" />
        <Pin v-else class="w-3 h-3" />
        <span class="hidden sm:inline">{{ isGameHeaderPinned ? 'Unpin' : 'Pin' }}</span>
      </button>
    </div>

    <div v-else :style="hintStyle">
      <!-- Invisible hover strip along the top edge. -->
      <div class="absolute inset-x-0 top-0 h-3" aria-hidden="true"></div>
      <!-- Proximity hint: a glow line along the edge, brightest above the pointer. -->
      <div class="header-hint-glow" aria-hidden="true"></div>
      <button
        type="button"
        class="header-hint-handle absolute left-1/2 top-0 flex items-center gap-1.5 rounded-b-lg border border-t-0 px-3 py-0.5 backdrop-blur-md"
        title="Show the header"
        aria-label="Show the header"
        @click="reveal"
      >
        <ChevronDown class="w-3.5 h-3.5" />
        <span class="header-hint-label">Menu</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.animate-header-in {
  animation: header-in 0.18s ease-out;
}

@keyframes header-in {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Hidden header: hints grow with --near (0 far .. 1 at the top edge). */
.header-hint-glow {
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  pointer-events: none;
  opacity: var(--near, 0);
  background: radial-gradient(
    40% 100% at var(--near-x, 50%) 0,
    var(--tw-accent, #f59e0b),
    color-mix(in srgb, var(--tw-accent, #f59e0b) 35%, transparent) 55%,
    transparent 100%
  );
  box-shadow: 0 0 calc(var(--near, 0) * 18px) color-mix(in srgb, var(--tw-accent, #f59e0b) 55%, transparent);
  transition: opacity 0.15s ease;
}

.header-hint-handle {
  transform: translate(-50%, calc(var(--near, 0) * 3px));
  opacity: calc(0.55 + var(--near, 0) * 0.45);
  color: color-mix(in srgb, var(--tw-accent, #f59e0b) calc(var(--near, 0) * 100%), #64748b);
  border-color: color-mix(in srgb, var(--tw-accent, #f59e0b) calc(var(--near, 0) * 70%), rgba(51, 65, 85, 0.5));
  background: rgba(2, 6, 23, 0.7);
  box-shadow: 0 4px calc(var(--near, 0) * 16px) color-mix(in srgb, var(--tw-accent, #f59e0b) calc(var(--near, 0) * 45%), transparent);
  transition: transform 0.15s ease, opacity 0.15s ease, color 0.15s ease;
}

.header-hint-handle:hover {
  opacity: 1;
  color: var(--tw-accent, #f59e0b);
}

/* The label fades in only when the pointer is close. */
.header-hint-label {
  max-width: calc(var(--near, 0) * 4rem);
  overflow: hidden;
  opacity: calc(var(--near, 0) * 2 - 0.8);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  white-space: nowrap;
  transition: max-width 0.15s ease, opacity 0.15s ease;
}

@media (prefers-reduced-motion: reduce) {
  .animate-header-in {
    animation: none;
  }

  .header-hint-glow,
  .header-hint-handle,
  .header-hint-label {
    transition: none;
  }
}
</style>
