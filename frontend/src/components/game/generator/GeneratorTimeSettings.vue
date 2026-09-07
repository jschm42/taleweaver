<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Clock, Sun, Hourglass, Calendar, Timer } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    clockEnabled: boolean
    timeSystem: 'calendar' | 'units'
    dayLabel?: string
    initialDay?: number
    startTime?: string
    timeFormat?: '24h' | '12h'
    pacingMinutes?: number
    maxTimePerTurn?: number | null
    unitName?: string
    initialUnits?: number
    unitsPerTurn?: number
    maxUnitsPerTurn?: number | null
  }>(),
  {
    dayLabel: 'Day',
    initialDay: 1,
    startTime: '08:00',
    timeFormat: '24h',
    pacingMinutes: 5,
    maxTimePerTurn: null,
    unitName: 'Units',
    initialUnits: 0,
    unitsPerTurn: 1,
    maxUnitsPerTurn: null,
  }
)

const emit = defineEmits<{
  (e: 'update:clockEnabled', val: boolean): void
  (e: 'update:timeSystem', val: 'calendar' | 'units'): void
  (e: 'update:dayLabel', val: string): void
  (e: 'update:initialDay', val: number): void
  (e: 'update:startTime', val: string): void
  (e: 'update:timeFormat', val: '24h' | '12h'): void
  (e: 'update:pacingMinutes', val: number): void
  (e: 'update:maxTimePerTurn', val: number | null): void
  (e: 'update:unitName', val: string): void
  (e: 'update:initialUnits', val: number): void
  (e: 'update:unitsPerTurn', val: number): void
  (e: 'update:maxUnitsPerTurn', val: number | null): void
}>()

// 12-hour decomposition helpers
const time12Hour = ref(8)
const time12Minute = ref('00')
const time12Ampm = ref<'AM' | 'PM'>('AM')

function sync12hFrom24h(val: string) {
  const parts = (val || '08:00').split(':')
  let h = parseInt(parts[0] || '8', 10)
  const m = (parts[1] || '00').padStart(2, '0')
  if (isNaN(h)) h = 8
  const ampm = h >= 12 ? 'PM' : 'AM'
  const h12 = h % 12 === 0 ? 12 : h % 12
  time12Hour.value = h12
  time12Minute.value = m
  time12Ampm.value = ampm
}

watch(
  () => props.startTime,
  (newVal) => {
    sync12hFrom24h(newVal || '08:00')
  },
  { immediate: true }
)

function update12hTime() {
  let h24 = time12Hour.value % 12
  if (time12Ampm.value === 'PM') h24 += 12
  const hStr = String(h24).padStart(2, '0')
  const mStr = String(time12Minute.value).padStart(2, '0')
  emit('update:startTime', `${hStr}:${mStr}`)
}

function on12hHourChange(e: Event) {
  const target = e.target as HTMLInputElement
  let val = parseInt(target.value, 10)
  if (isNaN(val) || val < 1) val = 1
  if (val > 12) val = 12
  time12Hour.value = val
  update12hTime()
}

function on12hMinuteChange(e: Event) {
  const target = e.target as HTMLInputElement
  let val = parseInt(target.value, 10)
  if (isNaN(val) || val < 0) val = 0
  if (val > 59) val = 59
  time12Minute.value = String(val).padStart(2, '0')
  update12hTime()
}

function on12hAmpmChange(ampm: 'AM' | 'PM') {
  time12Ampm.value = ampm
  update12hTime()
}

const formattedPreview = computed(() => {
  if (!props.clockEnabled) return 'Disabled'
  if (props.timeSystem === 'units') {
    return `Start: ${props.initialUnits} ${props.unitName || 'Units'} (+${props.unitsPerTurn}/turn)`
  }
  return `${props.dayLabel || 'Day'} ${props.initialDay} • ${props.startTime} (+${props.pacingMinutes}m/turn)`
})
</script>

<template>
  <div class="bg-slate-950/40 p-4 sm:p-5 rounded-2xl border border-white/5 space-y-4">
    <!-- Header with Enable Toggle -->
    <div class="flex items-center justify-between gap-3">
      <div class="flex items-center gap-2.5 min-w-0">
        <div class="w-8 h-8 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 shrink-0">
          <Clock class="w-4 h-4" />
        </div>
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <span class="text-xs font-black uppercase tracking-widest text-slate-300">Time & Pacing System</span>
            <span
              class="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider hidden xs:inline-block"
              :class="props.clockEnabled ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-500'"
            >
              {{ props.clockEnabled ? 'Active' : 'Off' }}
            </span>
          </div>
          <p class="text-[10px] text-slate-500 truncate mt-0.5">
            {{ formattedPreview }}
          </p>
        </div>
      </div>

      <!-- Toggle Switch -->
      <button
        type="button"
        @click="emit('update:clockEnabled', !props.clockEnabled)"
        class="w-12 h-7 rounded-full p-1 transition-colors duration-200 ease-in-out focus:outline-none shrink-0"
        :class="props.clockEnabled ? 'bg-cyan-600' : 'bg-slate-800'"
        role="switch"
        :aria-checked="props.clockEnabled"
      >
        <div
          class="w-5 h-5 rounded-full bg-white shadow-md transform transition-transform duration-200 ease-in-out"
          :class="props.clockEnabled ? 'translate-x-5' : 'translate-x-0'"
        ></div>
      </button>
    </div>

    <!-- Active Settings Body -->
    <div v-if="props.clockEnabled" class="space-y-4 pt-1 animate-fade-in">
      <!-- Time System Selector -->
      <div class="space-y-2">
        <label class="block text-[10px] font-black uppercase tracking-widest text-slate-400">
          Time Progression Mode
        </label>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          <!-- Mode 1: Calendar / Game Day -->
          <button
            type="button"
            @click="emit('update:timeSystem', 'calendar')"
            :class="[
              'p-3 rounded-xl border flex items-start gap-3 transition-all text-left',
              props.timeSystem === 'calendar'
                ? 'bg-amber-500/10 border-amber-500/50 text-white shadow-sm ring-1 ring-amber-500/30'
                : 'bg-white/5 border-white/5 text-slate-400 hover:text-white hover:bg-white/10'
            ]"
          >
            <div
              :class="[
                'p-2 rounded-lg shrink-0 mt-0.5',
                props.timeSystem === 'calendar' ? 'bg-amber-500/20 text-amber-300' : 'bg-white/5 text-slate-500'
              ]"
            >
              <Sun class="w-4 h-4" />
            </div>
            <div class="min-w-0">
              <div class="text-xs font-bold flex items-center gap-1.5">
                <span>Game Day & Clock</span>
              </div>
              <p class="text-[10px] text-slate-400 mt-0.5 leading-snug">
                Day cycle, 24h/12h clock time & round turn minutes.
              </p>
            </div>
          </button>

          <!-- Mode 2: Custom Time Units -->
          <button
            type="button"
            @click="emit('update:timeSystem', 'units')"
            :class="[
              'p-3 rounded-xl border flex items-start gap-3 transition-all text-left',
              props.timeSystem === 'units'
                ? 'bg-cyan-500/10 border-cyan-500/50 text-white shadow-sm ring-1 ring-cyan-500/30'
                : 'bg-white/5 border-white/5 text-slate-400 hover:text-white hover:bg-white/10'
            ]"
          >
            <div
              :class="[
                'p-2 rounded-lg shrink-0 mt-0.5',
                props.timeSystem === 'units' ? 'bg-cyan-500/20 text-cyan-300' : 'bg-white/5 text-slate-500'
              ]"
            >
              <Hourglass class="w-4 h-4" />
            </div>
            <div class="min-w-0">
              <div class="text-xs font-bold flex items-center gap-1.5">
                <span>Custom Units</span>
              </div>
              <p class="text-[10px] text-slate-400 mt-0.5 leading-snug">
                Abstract counters (e.g. Cycles, Hours, Lightyears).
              </p>
            </div>
          </button>
        </div>
      </div>

      <!-- CALENDAR / DAY MODE CONTROLS -->
      <div v-if="props.timeSystem === 'calendar'" class="space-y-3.5 bg-black/40 p-4 rounded-xl border border-white/5">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <!-- Day Label -->
          <div class="space-y-1.5">
            <label class="block text-[10px] font-black uppercase tracking-widest text-amber-400/90">Day Label</label>
            <input
              :value="props.dayLabel"
              @input="emit('update:dayLabel', ($event.target as HTMLInputElement).value)"
              type="text"
              maxlength="30"
              placeholder="e.g. Day, Sol, Cycle"
              class="w-full px-3 py-2 bg-slate-900/90 border border-slate-700/80 rounded-lg text-white font-bold text-xs outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500/30 transition-all"
            />
          </div>

          <!-- Initial Day -->
          <div class="space-y-1.5">
            <label class="block text-[10px] font-black uppercase tracking-widest text-amber-400/90">Start Day</label>
            <input
              :value="props.initialDay"
              @input="emit('update:initialDay', Number(($event.target as HTMLInputElement).value) || 1)"
              type="number"
              min="1"
              max="10000"
              class="w-full px-3 py-2 bg-slate-900/90 border border-slate-700/80 rounded-lg text-white font-bold text-xs outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500/30 transition-all"
            />
          </div>

          <!-- Start Time (24h or 12h) -->
          <div class="space-y-1.5">
            <label class="block text-[10px] font-black uppercase tracking-widest text-amber-400/90">Start Time</label>
            <!-- 24h native picker -->
            <input
              v-if="props.timeFormat !== '12h'"
              type="time"
              :value="props.startTime"
              @input="emit('update:startTime', ($event.target as HTMLInputElement).value)"
              class="w-full px-3 py-2 bg-slate-900/90 border border-slate-700/80 rounded-lg text-white font-bold text-xs outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500/30 transition-all"
            />
            <!-- 12h custom selector -->
            <div
              v-else
              class="flex items-center gap-1 bg-slate-900/90 border border-slate-700/80 rounded-lg px-2 py-1 focus-within:border-amber-500 transition-all"
            >
              <input
                type="number"
                min="1"
                max="12"
                :value="time12Hour"
                @input="on12hHourChange"
                class="w-8 bg-transparent text-white font-bold text-xs text-center outline-none"
              />
              <span class="text-amber-400 font-bold">:</span>
              <input
                type="number"
                min="0"
                max="59"
                :value="time12Minute"
                @input="on12hMinuteChange"
                class="w-8 bg-transparent text-white font-bold text-xs text-center outline-none"
              />
              <div class="flex bg-black/60 p-0.5 rounded ml-auto">
                <button
                  type="button"
                  @click="on12hAmpmChange('AM')"
                  class="px-1.5 py-0.5 rounded text-[9px] font-black uppercase transition-all"
                  :class="time12Ampm === 'AM' ? 'bg-amber-500 text-slate-950 shadow-sm' : 'text-slate-400 hover:text-white'"
                >
                  AM
                </button>
                <button
                  type="button"
                  @click="on12hAmpmChange('PM')"
                  class="px-1.5 py-0.5 rounded text-[9px] font-black uppercase transition-all"
                  :class="time12Ampm === 'PM' ? 'bg-amber-500 text-slate-950 shadow-sm' : 'text-slate-400 hover:text-white'"
                >
                  PM
                </button>
              </div>
            </div>
          </div>

          <!-- Format Switcher -->
          <div class="space-y-1.5">
            <label class="block text-[10px] font-black uppercase tracking-widest text-amber-400/90">Time Format</label>
            <div class="grid grid-cols-2 gap-1 bg-slate-900/90 p-1 rounded-lg border border-slate-700/80">
              <button
                type="button"
                @click="emit('update:timeFormat', '24h')"
                class="py-1 px-2 rounded text-[10px] font-black uppercase tracking-wider transition-all"
                :class="props.timeFormat !== '12h' ? 'bg-amber-500 text-slate-950 shadow-sm' : 'text-slate-400 hover:text-white'"
              >
                24h
              </button>
              <button
                type="button"
                @click="emit('update:timeFormat', '12h')"
                class="py-1 px-2 rounded text-[10px] font-black uppercase tracking-wider transition-all"
                :class="props.timeFormat === '12h' ? 'bg-amber-500 text-slate-950 shadow-sm' : 'text-slate-400 hover:text-white'"
              >
                12h
              </button>
            </div>
          </div>
        </div>

        <!-- Pacing Row -->
        <div class="pt-2 border-t border-white/5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div class="flex items-center gap-2">
            <Timer class="w-4 h-4 text-amber-400 shrink-0" />
            <div>
              <span class="text-xs font-bold text-slate-200">Turn Pacing</span>
              <span class="text-[10px] text-slate-500 block">Game minutes advanced per player turn action</span>
            </div>
          </div>
          <div class="flex items-center gap-3 w-full sm:w-64">
            <input
              type="range"
              min="1"
              max="60"
              :value="props.pacingMinutes"
              @input="emit('update:pacingMinutes', Number(($event.target as HTMLInputElement).value))"
              class="w-full accent-amber-500 bg-white/10 h-1.5 rounded-lg appearance-none cursor-pointer"
            />
            <span class="text-xs font-mono font-bold text-amber-400 shrink-0 w-12 text-right">
              {{ props.pacingMinutes }} min
            </span>
          </div>
        </div>
      </div>

      <!-- UNITS MODE CONTROLS -->
      <div v-else class="space-y-3.5 bg-black/40 p-4 rounded-xl border border-white/5">
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <!-- Unit Name -->
          <div class="space-y-1.5">
            <label class="block text-[10px] font-black uppercase tracking-widest text-cyan-400/90">Unit Name</label>
            <input
              :value="props.unitName"
              @input="emit('update:unitName', ($event.target as HTMLInputElement).value)"
              type="text"
              maxlength="30"
              placeholder="e.g. Hours, Lightyears, Cycles"
              class="w-full px-3 py-2 bg-slate-900/90 border border-slate-700/80 rounded-lg text-white font-bold text-xs outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/30 transition-all"
            />
          </div>

          <!-- Initial Units -->
          <div class="space-y-1.5">
            <label class="block text-[10px] font-black uppercase tracking-widest text-cyan-400/90">Initial Value</label>
            <input
              :value="props.initialUnits"
              @input="emit('update:initialUnits', Number(($event.target as HTMLInputElement).value) || 0)"
              type="number"
              min="0"
              max="10000"
              class="w-full px-3 py-2 bg-slate-900/90 border border-slate-700/80 rounded-lg text-white font-bold text-xs outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/30 transition-all"
            />
          </div>

          <!-- Units Per Turn -->
          <div class="space-y-1.5">
            <label class="block text-[10px] font-black uppercase tracking-widest text-cyan-400/90">Units Per Turn</label>
            <input
              :value="props.unitsPerTurn"
              @input="emit('update:unitsPerTurn', Number(($event.target as HTMLInputElement).value) || 1)"
              type="number"
              min="1"
              max="100"
              class="w-full px-3 py-2 bg-slate-900/90 border border-slate-700/80 rounded-lg text-white font-bold text-xs outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/30 transition-all"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
