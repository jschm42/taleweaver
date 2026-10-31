<script setup lang="ts">
/**
 * FooterClock — ornamental in-game clock left of the dock cards.
 *
 * A gilded day/night dial: the sky takes the colour of the time of day, and a wheel carrying
 * sun and moon turns with the in-game time (sun on top at noon, moon at midnight) behind the
 * horizon. Custom time-unit systems show an hourglass instead. Pulses when the time advances.
 */
import { computed } from 'vue'
import { Hourglass } from 'lucide-vue-next'
import { DAY_PHASE_LABELS, dayPhase, minuteOfDay, type GameTimeView } from './gameClockTime'

const props = defineProps<{
  gameTime: GameTimeView | null
  clockTick?: boolean
}>()

const minute = computed(() => minuteOfDay(props.gameTime))
const phase = computed(() => dayPhase(minute.value))
const phaseLabel = computed(() => (props.gameTime?.isUnits ? props.gameTime.unitName || 'Time' : DAY_PHASE_LABELS[phase.value]))
/** Noon puts the sun on top, midnight the moon; the sun rises on the left and sets on the right. */
const wheelRotation = computed(() => `rotate(${(minute.value ?? 12 * 60) * 0.25 - 180}deg)`)

const tooltip = computed(() => {
  if (!props.gameTime) {
    return ''
  }
  if (props.gameTime.isUnits) {
    return `In-game time units (${props.gameTime.dateShort}) of your current session.`
  }
  return `${phaseLabel.value} · ${props.gameTime.dateShort} · In-game time of your current session.`
})

// Fixed star positions (percent of the dial), shown at night and dawn.
const STARS = [
  { x: 24, y: 22, s: 2 },
  { x: 70, y: 16, s: 1.5 },
  { x: 52, y: 30, s: 1 },
  { x: 34, y: 38, s: 1.5 },
  { x: 80, y: 36, s: 1 },
  { x: 16, y: 42, s: 1 },
]
</script>

<template>
  <div
    v-if="props.gameTime"
    class="fclock"
    :class="[`is-${phase}`, { 'is-tick': props.clockTick, 'is-units': props.gameTime.isUnits }]"
    role="timer"
    :aria-label="tooltip"
    :title="tooltip"
  >
    <div class="fclock-dial" aria-hidden="true">
      <template v-if="!props.gameTime.isUnits">
        <div class="fclock-sky">
          <span
            v-for="(star, idx) in STARS"
            :key="idx"
            class="fclock-star"
            :style="{ left: `${star.x}%`, top: `${star.y}%`, width: `${star.s}px`, height: `${star.s}px` }"
          ></span>
        </div>
        <div class="fclock-wheel" :style="{ transform: wheelRotation }">
          <span class="fclock-sun"></span>
          <span class="fclock-moon"></span>
        </div>
        <div class="fclock-ground"></div>
      </template>
      <div v-else class="fclock-sky fclock-sky--units">
        <Hourglass class="fclock-hourglass" />
      </div>
      <span class="fclock-ticks"></span>
    </div>

    <div class="fclock-text">
      <span class="fclock-phase">{{ phaseLabel }}</span>
      <span class="fclock-time">{{ props.gameTime.time }}</span>
      <span class="fclock-date">{{ props.gameTime.dateShort }}</span>
    </div>
  </div>
</template>

<style scoped>
.fclock {
  --sky-top: #1e3a8a;
  --sky-bottom: #fbbf24;
  --glow: #fbbf24;
  display: flex;
  align-items: center;
  gap: 0.8rem;
  user-select: none;
}

.fclock.is-night { --sky-top: #070b24; --sky-bottom: #312e81; --glow: #a5b4fc; }
.fclock.is-dawn { --sky-top: #4c1d95; --sky-bottom: #fb923c; --glow: #fdba74; }
.fclock.is-day { --sky-top: #0ea5e9; --sky-bottom: #fde68a; --glow: #fbbf24; }
.fclock.is-dusk { --sky-top: #3b0764; --sky-bottom: #f43f5e; --glow: #fda4af; }
.fclock.is-units { --glow: #67e8f9; }

/* ── Dial ─────────────────────────────────────────────────────────────── */
.fclock-dial {
  position: relative;
  width: 62px;
  height: 62px;
  flex-shrink: 0;
  border-radius: 9999px;
  overflow: hidden;
  border: 2px solid #b08d4a;
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.6),
    0 0 0 4px rgba(176, 141, 74, 0.18),
    0 10px 22px -10px rgba(0, 0, 0, 0.9),
    0 0 18px -6px var(--glow);
  transition: box-shadow 0.6s ease;
}

.fclock-sky {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, var(--sky-top), var(--sky-bottom) 58%);
  transition: background 1.2s ease;
}

.fclock-sky--units {
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 50% 40%, #164e63, #020617 75%);
}

.fclock-hourglass {
  width: 46%;
  height: 46%;
  color: #67e8f9;
  filter: drop-shadow(0 0 6px rgba(103, 232, 249, 0.6));
}

.fclock-star {
  position: absolute;
  border-radius: 9999px;
  background: #fff;
  box-shadow: 0 0 4px #fff;
  opacity: 0;
  transition: opacity 1s ease;
}

.is-night .fclock-star { opacity: 0.9; }
.is-dawn .fclock-star,
.is-dusk .fclock-star { opacity: 0.35; }

/* Sun on top, moon at the bottom; the wheel turns with the time. */
.fclock-wheel {
  position: absolute;
  inset: 0;
  transition: transform 1.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.fclock-sun,
.fclock-moon {
  position: absolute;
  left: 50%;
  width: 15px;
  height: 15px;
  margin-left: -7.5px;
  border-radius: 9999px;
}

.fclock-sun {
  top: 9%;
  background: radial-gradient(circle at 40% 40%, #fffbeb, #fbbf24 55%, #f59e0b);
  box-shadow: 0 0 10px 3px rgba(251, 191, 36, 0.75);
}

.fclock-moon {
  bottom: 9%;
  background: radial-gradient(circle at 35% 35%, #f8fafc, #cbd5e1 70%);
  box-shadow: 0 0 8px 2px rgba(203, 213, 225, 0.55);
  /* Crescent: a shadow disc bites into the moon. */
  -webkit-mask: radial-gradient(circle at 72% 30%, transparent 42%, #000 44%);
  mask: radial-gradient(circle at 72% 30%, transparent 42%, #000 44%);
}

.fclock-ground {
  position: absolute;
  inset: 58% 0 0;
  background: linear-gradient(180deg, #1c1917, #0c0a09);
  border-top: 1.5px solid #b08d4a;
  box-shadow: 0 -2px 8px -2px var(--glow);
}

/* Gilded hour ticks around the rim. */
.fclock-ticks {
  position: absolute;
  inset: 0;
  border-radius: 9999px;
  background: repeating-conic-gradient(from -1deg, rgba(245, 222, 160, 0.85) 0 2deg, transparent 2deg 30deg);
  -webkit-mask: radial-gradient(circle, transparent 78%, #000 79%, #000 92%, transparent 93%);
  mask: radial-gradient(circle, transparent 78%, #000 79%, #000 92%, transparent 93%);
  pointer-events: none;
}

/* ── Text ─────────────────────────────────────────────────────────────── */
.fclock-text {
  display: flex;
  flex-direction: column;
  line-height: 1;
  min-width: 0;
}

.fclock-phase {
  font: 800 9px/1.2 var(--tw-font-label, ui-sans-serif, system-ui, sans-serif);
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--glow);
  transition: color 1s ease;
}

.fclock-time {
  margin-top: 3px;
  font-family: 'Acme', sans-serif;
  font-size: 1.45rem;
  letter-spacing: 0.04em;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  color: #fef3c7;
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.8), 0 0 14px rgba(251, 191, 36, 0.25);
}

.fclock-date {
  margin-top: 4px;
  max-width: 9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font: 700 9px/1.2 var(--tw-font-label, ui-sans-serif, system-ui, sans-serif);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(203, 213, 225, 0.7);
}

/* Time advanced: the dial flares and the time flashes gold. */
.fclock.is-tick .fclock-dial {
  animation: fclock-flare 0.8s ease-out;
}

.fclock.is-tick .fclock-time {
  animation: fclock-flash 0.8s ease-out;
}

@keyframes fclock-flare {
  0% { box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.6), 0 0 0 4px rgba(251, 191, 36, 0.5), 0 0 26px 2px var(--glow); }
}

@keyframes fclock-flash {
  0% { color: #fbbf24; transform: scale(1.06); }
}

@media (prefers-reduced-motion: reduce) {
  .fclock-wheel,
  .fclock-sky,
  .fclock-star {
    transition: none;
  }

  .fclock.is-tick .fclock-dial,
  .fclock.is-tick .fclock-time {
    animation: none;
  }
}
</style>
