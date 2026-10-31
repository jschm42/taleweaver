<script setup lang="ts">
/**
 * GameClockWidget — Compact in-game clock for the immersive header.
 *
 * Shows a time-of-day icon framed by a ring that fills over the course of the day.
 * Custom time-unit systems get an hourglass and no ring.
 */
import { computed, type Component } from 'vue'
import { Sun, Moon, Sunrise, Sunset, Hourglass } from 'lucide-vue-next'
import { dayPhase, minuteOfDay as parseMinuteOfDay } from '@/components/game/immersive/gameClockTime'

const props = defineProps<{
  gameTime: {
    dateShort: string
    time: string
    isUnits?: boolean
    unitName?: string
    value?: string
  } | null
  clockTick: boolean
}>()

type DayPhase = { label: string; icon: Component; tone: string; ring: string }

const PHASES: Record<'dawn' | 'day' | 'dusk' | 'night', DayPhase> = {
  dawn: { label: 'Dawn', icon: Sunrise, tone: 'text-orange-300', ring: '#fdba74' },
  day: { label: 'Daytime', icon: Sun, tone: 'text-amber-300', ring: '#fbbf24' },
  dusk: { label: 'Dusk', icon: Sunset, tone: 'text-rose-300', ring: '#fda4af' },
  night: { label: 'Night', icon: Moon, tone: 'text-indigo-300', ring: '#a5b4fc' },
}

const RING_RADIUS = 15
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS

const minuteOfDay = computed<number | null>(() => parseMinuteOfDay(props.gameTime))

const phase = computed<DayPhase>(() => PHASES[dayPhase(minuteOfDay.value)])

const ringOffset = computed(() => {
  const fraction = (minuteOfDay.value ?? 0) / (24 * 60)
  return RING_CIRCUMFERENCE * (1 - fraction)
})

const tooltip = computed(() => {
  if (!props.gameTime) {
    return ''
  }
  if (props.gameTime.isUnits) {
    return `In-game time units (${props.gameTime.dateShort}) of your current session.`
  }
  return `${phase.value.label} · ${props.gameTime.dateShort} · In-game time of your current session.`
})
</script>

<template>
  <div
    v-if="props.gameTime"
    class="game-clock group relative flex h-9 shrink-0 select-none items-center gap-2 rounded-xl border border-slate-700/60 bg-slate-900/80 pl-1 pr-2.5 shadow-lg backdrop-blur-md transition-all sm:pr-3"
    :class="{ 'clock-tick': props.clockTick }"
    :aria-label="tooltip"
    role="timer"
  >
    <!-- Time-of-day icon with day-progress ring -->
    <div class="relative flex h-7 w-7 shrink-0 items-center justify-center">
      <svg v-if="!props.gameTime.isUnits" class="absolute inset-0 -rotate-90" viewBox="0 0 34 34" aria-hidden="true">
        <circle cx="17" cy="17" :r="RING_RADIUS" fill="none" stroke="rgba(51,65,85,0.7)" stroke-width="2" />
        <circle
          cx="17"
          cy="17"
          :r="RING_RADIUS"
          fill="none"
          :stroke="phase.ring"
          stroke-width="2"
          stroke-linecap="round"
          :stroke-dasharray="RING_CIRCUMFERENCE"
          :stroke-dashoffset="ringOffset"
          class="transition-[stroke-dashoffset] duration-700"
        />
      </svg>
      <Hourglass v-if="props.gameTime.isUnits" class="h-4 w-4 text-cyan-300" />
      <component :is="phase.icon" v-else :class="['h-3.5 w-3.5', phase.tone]" />
    </div>

    <div class="flex min-w-0 flex-col justify-center leading-none">
      <span class="clock-font hidden max-w-[7rem] truncate text-[9px] uppercase tracking-[0.18em] text-slate-400 sm:block">
        {{ props.gameTime.dateShort }}
      </span>
      <span
        class="clock-font clock-time whitespace-nowrap text-sm tabular-nums tracking-wider sm:mt-0.5"
        :class="props.gameTime.isUnits ? 'text-cyan-200' : 'text-slate-100'"
      >
        {{ props.gameTime.time }}
      </span>
    </div>

    <div
      class="pointer-events-none absolute right-0 top-full z-50 mt-2 w-max max-w-xs rounded-lg border border-slate-700/60 bg-slate-900/95 px-3 py-2 text-[11px] font-semibold text-slate-200 opacity-0 shadow-2xl transition-opacity duration-200 group-hover:opacity-100"
    >
      {{ tooltip }}
    </div>
  </div>
</template>

<style scoped>
.clock-font {
  font-family: 'Acme', sans-serif;
}

.clock-tick {
  animation: clockGlow 0.6s ease-out;
}

.clock-tick .clock-time {
  animation: clockPulse 0.6s ease-out;
}

@keyframes clockGlow {
  0% { border-color: rgba(251, 191, 36, 0.7); box-shadow: 0 0 16px -2px rgba(251, 191, 36, 0.5); }
  100% { border-color: rgba(51, 65, 85, 0.6); box-shadow: none; }
}

@keyframes clockPulse {
  0% { color: #fbbf24; }
  100% { color: inherit; }
}
</style>
