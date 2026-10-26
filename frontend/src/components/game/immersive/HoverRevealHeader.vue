<script setup lang="ts">
/**
 * HoverRevealHeader — Keeps the game header out of the way until it is needed.
 * Unpinned, it is hidden and slides in over the stage when the pointer reaches the top edge
 * (or the handle is tapped on touch devices). Pinned, it is part of the layout again.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ChevronDown, Pin, PinOff } from 'lucide-vue-next'
import { isGameHeaderPinned, toggleGameHeaderPin } from '@/store/layout'

const HIDE_DELAY_MS = 350

const root = ref<HTMLElement | null>(null)
const isRevealed = ref(false)
let hideTimer: ReturnType<typeof setTimeout> | null = null

const isVisible = computed(() => isGameHeaderPinned.value || isRevealed.value)

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

    <template v-else>
      <!-- Invisible hover strip along the top edge. -->
      <div class="absolute inset-x-0 top-0 h-3" aria-hidden="true"></div>
      <button
        type="button"
        class="absolute left-1/2 top-0 -translate-x-1/2 flex items-center rounded-b-lg border border-t-0 border-slate-700/50 bg-slate-950/60 px-3 py-0.5 text-slate-500 opacity-60 backdrop-blur-md hover:opacity-100 hover:text-slate-200 transition-opacity"
        title="Show the header"
        aria-label="Show the header"
        @click="reveal"
      >
        <ChevronDown class="w-3.5 h-3.5" />
      </button>
    </template>
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

@media (prefers-reduced-motion: reduce) {
  .animate-header-in {
    animation: none;
  }
}
</style>
