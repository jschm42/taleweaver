<script setup lang="ts">
/**
 * FooterXp — ornamental experience display right of the dock cards.
 *
 * The experience total in gilded type. When XP rises, the number counts up to the new total,
 * flashes gold and a "+N XP" floats up from it.
 */
import { onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps<{
  exp: number
}>()

const COUNT_UP_MS = 900
const GAIN_VISIBLE_MS = 2200

const shown = ref(props.exp || 0)
const gains = ref<{ id: number; amount: number }[]>([])
const isGaining = ref(false)
let frame = 0
let gainId = 0
let gainTimer: ReturnType<typeof setTimeout> | null = null

const prefersReducedMotion = (): boolean =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function countTo(target: number): void {
  cancelAnimationFrame(frame)
  const start = shown.value
  if (prefersReducedMotion() || start === target) {
    shown.value = target
    return
  }
  const begin = performance.now()
  const step = (now: number) => {
    const t = Math.min(1, (now - begin) / COUNT_UP_MS)
    const eased = 1 - Math.pow(1 - t, 3)
    shown.value = Math.round(start + (target - start) * eased)
    if (t < 1) {
      frame = requestAnimationFrame(step)
    }
  }
  frame = requestAnimationFrame(step)
}

function announceGain(amount: number): void {
  const id = ++gainId
  gains.value = [...gains.value, { id, amount }]
  isGaining.value = true
  if (gainTimer) clearTimeout(gainTimer)
  gainTimer = setTimeout(() => {
    isGaining.value = false
  }, 1200)
  setTimeout(() => {
    gains.value = gains.value.filter((gain) => gain.id !== id)
  }, GAIN_VISIBLE_MS)
}

watch(
  () => props.exp || 0,
  (next, previous) => {
    if (next > (previous ?? next)) {
      announceGain(next - (previous ?? next))
    }
    countTo(next)
  }
)

onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  if (gainTimer) clearTimeout(gainTimer)
})
</script>

<template>
  <div class="fxp" :class="{ 'is-gaining': isGaining }" :title="`${props.exp || 0} experience points`">
    <div class="fxp-text">
      <span class="fxp-label">Experience</span>
      <span class="fxp-value">{{ shown }}<small>XP</small></span>
      <span v-for="gain in gains" :key="gain.id" class="fxp-gain" aria-hidden="true">+{{ gain.amount }} XP</span>
    </div>
  </div>
</template>

<style scoped>
.fxp {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  user-select: none;
}

/* ── Text ─────────────────────────────────────────────────────────────── */
.fxp-text {
  display: flex;
  position: relative;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1;
}

.fxp-label {
  font: 800 9px/1.2 var(--tw-font-label, ui-sans-serif, system-ui, sans-serif);
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: #fbbf24;
}

.fxp-value {
  margin-top: 3px;
  transform-origin: left center;
  font-family: 'Acme', sans-serif;
  font-size: 1.45rem;
  letter-spacing: 0.04em;
  font-variant-numeric: tabular-nums;
  color: #fef3c7;
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.8), 0 0 14px rgba(251, 191, 36, 0.25);
}

.fxp-value small {
  margin-left: 0.3rem;
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  color: #fbbf24;
}

.fxp-gain {
  position: absolute;
  bottom: 100%;
  left: 50%;
  white-space: nowrap;
  padding: 1px 8px;
  border-radius: 9999px;
  font: 800 11px/1.5 var(--tw-font-label, ui-sans-serif, system-ui, sans-serif);
  letter-spacing: 0.08em;
  color: #fef3c7;
  background: rgba(120, 53, 15, 0.85);
  border: 1px solid rgba(251, 191, 36, 0.7);
  box-shadow: 0 0 12px rgba(251, 191, 36, 0.5);
  pointer-events: none;
  animation: fxp-float 2.2s ease-out forwards;
}

/* XP gained: the number flares gold. */
.fxp.is-gaining .fxp-value {
  color: #fbbf24;
  animation: fxp-flare 1.2s ease-out;
}

@keyframes fxp-float {
  0% { opacity: 0; transform: translate(-50%, 8px) scale(0.8); }
  15% { opacity: 1; transform: translate(-50%, -4px) scale(1.08); }
  25% { transform: translate(-50%, -4px) scale(1); }
  80% { opacity: 1; }
  100% { opacity: 0; transform: translate(-50%, -22px); }
}

@keyframes fxp-flare {
  0% { transform: scale(1); text-shadow: 0 2px 6px rgba(0, 0, 0, 0.8); }
  25% { transform: scale(1.12); text-shadow: 0 0 16px rgba(251, 191, 36, 0.9); }
  100% { transform: scale(1); text-shadow: 0 2px 6px rgba(0, 0, 0, 0.8), 0 0 14px rgba(251, 191, 36, 0.25); }
}

@media (prefers-reduced-motion: reduce) {
  .fxp.is-gaining .fxp-value {
    animation: none;
  }

  .fxp-gain {
    animation-name: fxp-fade;
  }
}

@keyframes fxp-fade {
  0%, 100% { opacity: 0; transform: translate(-50%, -4px); }
  15%, 80% { opacity: 1; transform: translate(-50%, -4px); }
}
</style>
