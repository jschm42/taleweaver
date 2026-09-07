<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Clock, Sun, Hourglass, Timer } from 'lucide-vue-next'
import InfoPopoverButton from '@/components/create-adventure/InfoPopoverButton.vue'
import { CREATE_ADVENTURE_HELP_TEXTS } from '@/constants/createAdventureHelpTexts'

export interface TimeConfigData {
  day_label?: string
  initial_day?: number
  start_time?: string
  time_format?: '24h' | '12h'
  pacing_minutes?: number
  max_time_per_turn?: number | null
  unit_name?: string
  initial_units?: number
  units_per_turn?: number
  max_units_per_turn?: number | null
}

const props = withDefaults(
  defineProps<{
    clockEnabled?: boolean
    timeAuto?: boolean
    timeSystem?: 'calendar' | 'units'
    pacingMinutes?: number
    timeConfig?: TimeConfigData | null
  }>(),
  {
    clockEnabled: true,
    timeAuto: true,
    timeSystem: 'calendar',
    pacingMinutes: 5,
    timeConfig: null,
  }
)

const emit = defineEmits<{
  (e: 'update:clockEnabled', val: boolean): void
  (e: 'update:timeAuto', val: boolean): void
  (e: 'update:timeSystem', val: 'calendar' | 'units'): void
  (e: 'update:pacingMinutes', val: number): void
  (e: 'update:timeConfig', val: TimeConfigData): void
}>()

// Local copy of timeConfig to avoid null issues
const localConfig = computed<TimeConfigData>(() => ({
  day_label: props.timeConfig?.day_label || 'Day',
  initial_day: props.timeConfig?.initial_day ?? 1,
  start_time: props.timeConfig?.start_time || '08:00',
  time_format: props.timeConfig?.time_format || '24h',
  pacing_minutes: props.timeConfig?.pacing_minutes ?? props.pacingMinutes ?? 5,
  max_time_per_turn: props.timeConfig?.max_time_per_turn ?? null,
  unit_name: props.timeConfig?.unit_name || 'Units',
  initial_units: props.timeConfig?.initial_units ?? 0,
  units_per_turn: props.timeConfig?.units_per_turn ?? 1,
  max_units_per_turn: props.timeConfig?.max_units_per_turn ?? null,
}))

function updateField<K extends keyof TimeConfigData>(key: K, val: TimeConfigData[K]) {
  const next = { ...localConfig.value, [key]: val }
  emit('update:timeConfig', next)
  if (key === 'pacing_minutes' && typeof val === 'number') {
    emit('update:pacingMinutes', val)
  }
}

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
  () => localConfig.value.start_time,
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
  updateField('start_time', `${hStr}:${mStr}`)
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

function toggleAutoMode() {
  emit('update:timeAuto', !props.timeAuto)
}
</script>

<template>
  <div class="p-4 sm:p-5 md:p-6 bg-emerald-500/5 border border-emerald-500/10 rounded-2xl space-y-4 md:space-y-6 transition-all">
    <!-- Header -->
    <div class="flex items-center justify-between gap-2 border-b border-white/5 pb-3">
      <div class="flex items-center gap-2 sm:gap-3 min-w-0">
        <div class="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
          <Clock class="w-4 h-4 sm:w-5 sm:h-5" />
        </div>
        <div class="min-w-0">
          <span class="text-xs sm:text-sm font-black text-white uppercase tracking-wider block truncate">
            In-Game Time & Pacing
          </span>
          <span class="text-[10px] text-white/40 uppercase tracking-widest">
            Day/night cycle, clock time, or custom units
          </span>
        </div>
      </div>

      <div class="flex items-center gap-2 shrink-0">
        <InfoPopoverButton title="Time & Pacing" :text="CREATE_ADVENTURE_HELP_TEXTS.timeSystem || CREATE_ADVENTURE_HELP_TEXTS.pacing" />
        <!-- Auto / Manual Toggle Button -->
        <button
          type="button"
          @click="toggleAutoMode"
          class="px-3 py-1 rounded-full text-xxs font-black uppercase tracking-wider transition-all border cursor-pointer select-none"
          :class="props.timeAuto ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
        >
          {{ props.timeAuto ? 'Auto Mode' : 'Manual' }}
        </button>
      </div>
    </div>

    <!-- Auto Mode Text -->
    <div v-if="props.timeAuto" class="text-xs text-white/40 italic uppercase tracking-wider py-2">
      ✨ AI will automatically determine optimal time progression, start time, and pacing based on your story idea.
    </div>

    <!-- Manual Configuration Panel -->
    <div v-else class="space-y-4 pt-1 animate-fade-in">
      <!-- Master Clock Enable Toggle -->
      <div class="flex items-center justify-between gap-3 p-3 rounded-xl border border-white/10 bg-black/20">
        <div class="space-y-0.5 min-w-0">
          <span class="text-xs font-black text-white/80 uppercase tracking-widest block truncate">Clock Progression Active</span>
          <span class="text-[10px] text-white/40 uppercase tracking-wider block">If disabled, the adventure will have no advancing timeline</span>
        </div>
        <button
          type="button"
          @click="emit('update:clockEnabled', !props.clockEnabled)"
          class="w-10 h-5 rounded-full relative cursor-pointer transition-colors shrink-0"
          :class="props.clockEnabled ? 'bg-emerald-500' : 'bg-slate-700'"
        >
          <div
            class="absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm"
            :class="props.clockEnabled ? 'left-6' : 'left-1'"
          ></div>
        </button>
      </div>

      <div v-if="props.clockEnabled" class="space-y-4">
        <!-- Mode Switcher -->
        <div class="space-y-1.5">
          <label class="block text-xxs font-black text-white/40 uppercase tracking-widest">
            Time System Type
          </label>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            <!-- Mode 1: Calendar / Game Day -->
            <button
              type="button"
              @click="emit('update:timeSystem', 'calendar')"
              :class="[
                'p-3 rounded-xl border flex items-start gap-3 transition-all text-left cursor-pointer',
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
                <div class="text-xs font-bold">Game Day & Clock</div>
                <p class="text-[10px] text-slate-400 mt-0.5 leading-snug">
                  Day count, 24h/12h clock time, and round minutes.
                </p>
              </div>
            </button>

            <!-- Mode 2: Custom Units -->
            <button
              type="button"
              @click="emit('update:timeSystem', 'units')"
              :class="[
                'p-3 rounded-xl border flex items-start gap-3 transition-all text-left cursor-pointer',
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
                <div class="text-xs font-bold">Custom Time Units</div>
                <p class="text-[10px] text-slate-400 mt-0.5 leading-snug">
                  Abstract counters (e.g. Cycles, Hours, Lightyears).
                </p>
              </div>
            </button>
          </div>
        </div>

        <!-- CALENDAR MODE CONTROLS -->
        <div v-if="props.timeSystem === 'calendar'" class="space-y-3.5 bg-black/30 p-4 rounded-xl border border-white/5">
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <!-- Day Label -->
            <div class="space-y-1.5">
              <label class="block text-xxs font-black uppercase tracking-widest text-amber-400/90">Day Label</label>
              <input
                :value="localConfig.day_label"
                @input="updateField('day_label', ($event.target as HTMLInputElement).value)"
                type="text"
                maxlength="30"
                placeholder="e.g. Day, Sol, Cycle"
                class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-bold text-xs outline-none focus:border-amber-500 transition-all"
              />
            </div>

            <!-- Start Day -->
            <div class="space-y-1.5">
              <label class="block text-xxs font-black uppercase tracking-widest text-amber-400/90">Start Day</label>
              <input
                :value="localConfig.initial_day"
                @input="updateField('initial_day', Number(($event.target as HTMLInputElement).value) || 1)"
                type="number"
                min="1"
                max="10000"
                class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-bold text-xs outline-none focus:border-amber-500 transition-all"
              />
            </div>

            <!-- Start Time -->
            <div class="space-y-1.5">
              <label class="block text-xxs font-black uppercase tracking-widest text-amber-400/90">Start Time</label>
              <input
                v-if="localConfig.time_format !== '12h'"
                type="time"
                :value="localConfig.start_time"
                @input="updateField('start_time', ($event.target as HTMLInputElement).value)"
                class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-bold text-xs outline-none focus:border-amber-500 transition-all"
              />
              <div
                v-else
                class="flex items-center gap-1 bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 focus-within:border-amber-500 transition-all"
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

            <!-- Time Format -->
            <div class="space-y-1.5">
              <label class="block text-xxs font-black uppercase tracking-widest text-amber-400/90">Time Format</label>
              <div class="grid grid-cols-2 gap-1 bg-slate-900 p-1 rounded-lg border border-slate-700">
                <button
                  type="button"
                  @click="updateField('time_format', '24h')"
                  class="py-1 px-2 rounded text-[10px] font-black uppercase tracking-wider transition-all text-center"
                  :class="localConfig.time_format !== '12h' ? 'bg-amber-500 text-slate-950 shadow-sm' : 'text-slate-400 hover:text-white'"
                >
                  24h
                </button>
                <button
                  type="button"
                  @click="updateField('time_format', '12h')"
                  class="py-1 px-2 rounded text-[10px] font-black uppercase tracking-wider transition-all text-center"
                  :class="localConfig.time_format === '12h' ? 'bg-amber-500 text-slate-950 shadow-sm' : 'text-slate-400 hover:text-white'"
                >
                  12h
                </button>
              </div>
            </div>
          </div>

          <!-- Turn Pacing Slider -->
          <div class="pt-2 border-t border-white/5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div class="flex items-center gap-2">
              <Timer class="w-4 h-4 text-amber-400 shrink-0" />
              <div>
                <span class="text-xs font-bold text-white/80">Turn Pacing</span>
                <span class="text-[10px] text-white/40 block">In-game minutes advanced per action</span>
              </div>
            </div>
            <div class="flex items-center gap-3 w-full sm:w-64">
              <input
                type="range"
                min="1"
                max="60"
                :value="localConfig.pacing_minutes"
                @input="updateField('pacing_minutes', Number(($event.target as HTMLInputElement).value))"
                class="w-full accent-emerald-500 bg-white/10 h-1.5 rounded-lg appearance-none cursor-pointer"
              />
              <span class="text-xs font-mono font-bold text-emerald-400 shrink-0 w-12 text-right">
                {{ localConfig.pacing_minutes }}m
              </span>
            </div>
          </div>
        </div>

        <!-- UNITS MODE CONTROLS -->
        <div v-else class="space-y-3.5 bg-black/30 p-4 rounded-xl border border-white/5">
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <!-- Unit Name -->
            <div class="space-y-1.5">
              <label class="block text-xxs font-black uppercase tracking-widest text-cyan-400/90">Unit Name</label>
              <input
                :value="localConfig.unit_name"
                @input="updateField('unit_name', ($event.target as HTMLInputElement).value)"
                type="text"
                maxlength="30"
                placeholder="e.g. Hours, Lightyears, Cycles"
                class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-bold text-xs outline-none focus:border-cyan-500 transition-all"
              />
            </div>

            <!-- Initial Units -->
            <div class="space-y-1.5">
              <label class="block text-xxs font-black uppercase tracking-widest text-cyan-400/90">Initial Value</label>
              <input
                :value="localConfig.initial_units"
                @input="updateField('initial_units', Number(($event.target as HTMLInputElement).value) || 0)"
                type="number"
                min="0"
                max="10000"
                class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-bold text-xs outline-none focus:border-cyan-500 transition-all"
              />
            </div>

            <!-- Units Per Turn -->
            <div class="space-y-1.5">
              <label class="block text-xxs font-black uppercase tracking-widest text-cyan-400/90">Units Per Turn</label>
              <input
                :value="localConfig.units_per_turn"
                @input="updateField('units_per_turn', Number(($event.target as HTMLInputElement).value) || 1)"
                type="number"
                min="1"
                max="100"
                class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-bold text-xs outline-none focus:border-cyan-500 transition-all"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
