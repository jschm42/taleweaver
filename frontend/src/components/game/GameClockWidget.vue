<script setup lang="ts">
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
</script>

<template>
  <div class="z-10">
    <div class="relative group flex flex-col items-end select-none game-clock" :class="{ 'clock-tick': props.clockTick }">
      <template v-if="props.gameTime">
        <div class="flex items-center gap-2 sm:gap-2.5 px-2.5 py-1 sm:px-3.5 sm:py-1.5 bg-slate-900/80 border border-slate-700/60 rounded-xl backdrop-blur-md shadow-lg transition-all">
          <svg v-if="!props.gameTime.isUnits" xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 sm:h-4 sm:w-4 text-amber-500/80 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 sm:h-4 sm:w-4 text-cyan-400/90 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0zM13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <div class="flex flex-col items-end min-w-0">
            <span
              class="text-[9px] sm:text-xs font-black uppercase tracking-widest leading-none mb-0.5 sm:mb-1 whitespace-nowrap truncate max-w-[120px]"
              :class="props.gameTime.isUnits ? 'text-cyan-400/70' : 'text-amber-500/60'"
            >
              {{ props.gameTime.dateShort }}
            </span>
            <span
              class="clock-time text-sm sm:text-lg font-black tracking-widest leading-none tabular-nums"
              :class="props.gameTime.isUnits ? 'text-cyan-300' : 'text-amber-300'"
            >
              {{ props.gameTime.time }}
            </span>
          </div>
        </div>
        <div class="pointer-events-none absolute right-0 top-full mt-2 w-max max-w-xs rounded-lg border border-slate-700/60 bg-slate-900/95 px-3 py-2 text-[11px] font-semibold text-slate-200 shadow-2xl opacity-0 transition-opacity duration-200 group-hover:opacity-100">
          {{ props.gameTime.isUnits ? `In-game time units (${props.gameTime.dateShort}) of your current session.` : 'In-game time of your current session.' }}
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
@font-face {
  font-family: 'OrbitronClock';
  src: url('/assets/fonts/Orbitron-VariableFont_wght.ttf') format('truetype');
  font-weight: 100 900;
  font-style: normal;
}

.game-clock .clock-time,
.game-clock .clock-date {
  font-family: 'OrbitronClock', monospace;
}

.clock-tick span {
  animation: clockPulse 0.6s ease-out;
}

@keyframes clockPulse {
  0%   { color: #fbbf24; text-shadow: 0 0 12px rgba(251,191,36,0.8); }
  100% { color: inherit;  text-shadow: none; }
}
</style>

