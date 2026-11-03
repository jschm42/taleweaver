<script setup lang="ts">
// Editor tab for the in-game clock: time system (game days or custom units), start time,
// pacing per narration tick, GM time limit and whether the GM may change the time at all.
import GmTimeControlToggle from '@/components/editor/GmTimeControlToggle.vue'
import { Save, X } from 'lucide-vue-next'
import { computed } from 'vue'

const props = defineProps<{
  form: any
  adventure: any
  isSaving: boolean
}>()

const emit = defineEmits<{
  (e: 'save-changes'): void
  (e: 'update:pacing', val: number): void
  (e: 'update:max-time-per-turn', val: number | null): void
  (e: 'update:clock-enabled', val: boolean): void
  (e: 'update:gm-time-control', val: boolean): void
  (e: 'update:time-system', val: 'calendar' | 'units' | 'relative'): void
  (e: 'update:start-date', val: string): void
  (e: 'update:start-time', val: string): void
  (e: 'update:day-label', val: string): void
  (e: 'update:initial-day', val: number): void
  (e: 'update:time-format', val: '24h' | '12h'): void
  (e: 'update:unit-name', val: string): void
  (e: 'update:initial-value', val: number): void
  (e: 'update:calendar-pacing-value', val: number): void
  (e: 'update:calendar-pacing-unit', val: string): void
  (e: 'update:calendar-max-value', val: number | null): void
  (e: 'update:calendar-max-unit', val: string): void
}>()

const CALENDAR_UNIT_FACTORS: Record<string, number> = {
  minutes: 1,
  hours: 60,
  days: 1440,
  weeks: 10080,
  years: 525600,
  Minutes: 1,
  Hours: 60,
  Days: 1440,
  Weeks: 10080,
  Years: 525600,
}

const CALENDAR_UNITS = [
  { value: 'Minutes', label: 'Minutes' },
  { value: 'Hours', label: 'Hours' },
  { value: 'Days', label: 'Days' },
  { value: 'Weeks', label: 'Weeks' },
  { value: 'Years', label: 'Years' },
] as const

function getCalendarPacingValue(): number {
  if (props.form?.time_config?.calendar_pacing_value !== undefined && props.form?.time_config?.calendar_pacing_value !== null) {
    const parsed = Number(props.form.time_config.calendar_pacing_value)
    return isNaN(parsed) || parsed < 1 ? 5 : parsed
  }
  const t = props.form?.time_per_turn || 5
  if (t >= 525600 && t % 525600 === 0) return t / 525600
  if (t >= 10080 && t % 10080 === 0) return t / 10080
  if (t >= 1440 && t % 1440 === 0) return t / 1440
  if (t >= 60 && t % 60 === 0) return t / 60
  return t
}

function getCalendarPacingUnit(): string {
  return props.form?.time_config?.calendar_pacing_unit || 'Minutes'
}

function getCalendarMaxValue(): string {
  if (props.form?.time_config?.calendar_max_value !== undefined && props.form?.time_config?.calendar_max_value !== null) {
    return String(props.form.time_config.calendar_max_value)
  }
  if (props.form?.max_time_per_turn === undefined || props.form?.max_time_per_turn === null) {
    return ''
  }
  const t = props.form.max_time_per_turn
  if (t >= 525600 && t % 525600 === 0) return String(t / 525600)
  if (t >= 10080 && t % 10080 === 0) return String(t / 10080)
  if (t >= 1440 && t % 1440 === 0) return String(t / 1440)
  if (t >= 60 && t % 60 === 0) return String(t / 60)
  return String(t)
}

function getCalendarMaxUnit(): string {
  return props.form?.time_config?.calendar_max_unit || 'Minutes'
}

function handleCalendarPacingValueChange(event: Event) {
  const target = event.target as HTMLInputElement
  const raw = Number(target.value)
  const val = isNaN(raw) ? 1 : raw
  const unit = getCalendarPacingUnit()
  const factor = CALENDAR_UNIT_FACTORS[unit] || 1
  emit('update:calendar-pacing-value', val)
  emit('update:pacing', val * factor)
}

function handleCalendarPacingUnitChange(event: Event) {
  const target = event.target as HTMLSelectElement
  const unit = target.value
  const val = getCalendarPacingValue()
  const factor = CALENDAR_UNIT_FACTORS[unit] || 1
  emit('update:calendar-pacing-unit', unit)
  emit('update:pacing', val * factor)
}

function handleCalendarMaxValueChange(event: Event) {
  const target = event.target as HTMLInputElement
  const raw = target.value.trim()
  if (!raw) {
    emit('update:calendar-max-value', null)
    emit('update:max-time-per-turn', null)
    return
  }
  const val = Number(raw)
  const unit = getCalendarMaxUnit()
  const factor = CALENDAR_UNIT_FACTORS[unit] || 1
  emit('update:calendar-max-value', isNaN(val) ? null : val)
  emit('update:max-time-per-turn', isNaN(val) ? null : val * factor)
}

function handleCalendarMaxUnitChange(event: Event) {
  const target = event.target as HTMLSelectElement
  const unit = target.value
  emit('update:calendar-max-unit', unit)
  const maxValStr = getCalendarMaxValue()
  if (maxValStr) {
    const val = Number(maxValStr) || 1
    const factor = CALENDAR_UNIT_FACTORS[unit] || 1
    emit('update:max-time-per-turn', val * factor)
  }
}

function handleUnitsPacingChange(event: Event) {
  const target = event.target as HTMLInputElement
  const val = parseFloat(target.value)
  emit('update:pacing', isNaN(val) ? 1 : val)
}

function handleUnitsMaxChange(event: Event) {
  const target = event.target as HTMLInputElement
  const raw = target.value.trim()
  if (!raw) {
    emit('update:max-time-per-turn', null)
    return
  }
  const val = parseFloat(raw)
  emit('update:max-time-per-turn', isNaN(val) ? null : val)
}

function handleStartTimeInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:start-time', target.value || '08:00')
}

function handleDayLabelInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:day-label', target.value)
}

function handleInitialDayInput(event: Event) {
  const target = event.target as HTMLInputElement
  const val = parseInt(target.value, 10)
  emit('update:initial-day', isNaN(val) ? 1 : val)
}

function handleUnitNameInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:unit-name', target.value)
}

function handleInitialValueInput(event: Event) {
  const target = event.target as HTMLInputElement
  const val = parseFloat(target.value)
  emit('update:initial-value', isNaN(val) ? 0 : val)
}

function handleTimeFormatInput(val: '24h' | '12h') {
  emit('update:time-format', val)
}

const time12Parts = computed(() => {
  const raw = props.form?.time_config?.start_time || '08:00'
  let h = 8
  let m = 0
  try {
    const [hRaw, mRaw] = String(raw).split(':').map(Number)
    if (!isNaN(hRaw)) h = hRaw
    if (!isNaN(mRaw)) m = mRaw
  } catch {
    // Unparseable start time: keep the 08:00 default.
  }

  const isPM = h >= 12
  const h12 = h % 12 || 12
  return {
    hour12: h12,
    minute: m,
    minuteStr: m.toString().padStart(2, '0'),
    ampm: (isPM ? 'PM' : 'AM') as 'AM' | 'PM',
  }
})

function update12hTime(newHour12: number, newMinute: number, newAmpm: 'AM' | 'PM') {
  const h12Clamped = Math.max(1, Math.min(12, Number(newHour12) || 12))
  const mClamped = Math.max(0, Math.min(59, Number(newMinute) || 0))
  let h24 = 0
  if (newAmpm === 'PM') {
    h24 = (h12Clamped % 12) + 12
  } else {
    h24 = h12Clamped % 12
  }
  const formatted24h = `${h24.toString().padStart(2, '0')}:${mClamped.toString().padStart(2, '0')}`
  emit('update:start-time', formatted24h)
}

function handle12hHourInput(event: Event) {
  const target = event.target as HTMLInputElement
  const rawVal = parseInt(target.value, 10)
  const clamped = isNaN(rawVal) ? 1 : Math.max(1, Math.min(12, rawVal))
  update12hTime(clamped, time12Parts.value.minute, time12Parts.value.ampm)
}

function handle12hMinuteInput(event: Event) {
  const target = event.target as HTMLInputElement
  const rawVal = parseInt(target.value, 10)
  const clamped = isNaN(rawVal) ? 0 : Math.max(0, Math.min(59, rawVal))
  update12hTime(time12Parts.value.hour12, clamped, time12Parts.value.ampm)
}

function handle12hAmpmChange(newAmpm: 'AM' | 'PM') {
  update12hTime(time12Parts.value.hour12, time12Parts.value.minute, newAmpm)
}

const timeValidationErrors = computed(() => {
  const errors: Record<string, string> = {}
  if (!props.form?.clock_enabled) return errors

  const sys = props.form?.time_system === 'units' ? 'units' : 'relative'
  const cfg = props.form?.time_config || {}

  if (sys === 'relative') {
    const dayLabel = (cfg.day_label ?? 'Day').trim()
    if (!dayLabel) {
      errors.day_label = 'Day label is required (e.g. "Day", "Sol").'
    } else if (dayLabel.length > 30) {
      errors.day_label = 'Day label must be at most 30 characters.'
    }

    const dayNum = Number(cfg.initial_day ?? 1)
    if (isNaN(dayNum) || !isFinite(dayNum) || dayNum < 1 || !Number.isInteger(dayNum)) {
      errors.initial_day = 'Start day must be an integer >= 1.'
    } else if (dayNum > 10000) {
      errors.initial_day = 'Start day cannot exceed 10,000.'
    }

    if (!cfg.start_time || !/^([01]\d|2[0-3]):([0-5]\d)$/.test(cfg.start_time)) {
      errors.start_time = 'Start time must be a valid time in HH:MM format (00:00 - 23:59).'
    }

    const pacingVal = getCalendarPacingValue()
    if (isNaN(pacingVal) || !isFinite(pacingVal) || pacingVal < 1) {
      errors.pacing = 'Turn pacing must be at least 1.'
    } else if (pacingVal > 10000) {
      errors.pacing = 'Turn pacing cannot exceed 10,000.'
    }

    const maxValStr = getCalendarMaxValue()
    if (maxValStr) {
      const maxVal = Number(maxValStr)
      if (isNaN(maxVal) || !isFinite(maxVal) || maxVal < 1) {
        errors.max_time = 'Max limit must be at least 1.'
      } else if (maxVal > 10000) {
        errors.max_time = 'Max limit cannot exceed 10,000.'
      } else {
        const pacingUnit = getCalendarPacingUnit()
        const maxUnit = getCalendarMaxUnit()
        const pacingTotalMinutes = pacingVal * (CALENDAR_UNIT_FACTORS[pacingUnit] || 1)
        const maxTotalMinutes = maxVal * (CALENDAR_UNIT_FACTORS[maxUnit] || 1)
        if (maxTotalMinutes < pacingTotalMinutes) {
          errors.max_time = 'Max limit cannot be less than turn pacing.'
        }
      }
    }
  } else {
    // units mode
    const unitName = (cfg.unit_name ?? 'Blobs').trim()
    if (!unitName) {
      errors.unit_name = 'Unit name is required (e.g. "Lightyears", "Blobs").'
    } else if (unitName.length > 30) {
      errors.unit_name = 'Unit name must be at most 30 characters.'
    }

    const initVal = Number(cfg.initial_value ?? 0)
    if (isNaN(initVal) || !isFinite(initVal)) {
      errors.initial_value = 'Initial value must be a valid number.'
    } else if (initVal < 0) {
      errors.initial_value = 'Initial value must be at least 0.'
    } else if (initVal > 10000) {
      errors.initial_value = 'Initial value cannot exceed 10,000.'
    }

    const pacing = Number(props.form?.time_per_turn ?? 1)
    if (isNaN(pacing) || !isFinite(pacing) || pacing <= 0) {
      errors.units_pacing = 'Turn pacing must be greater than 0.'
    } else if (pacing > 10000) {
      errors.units_pacing = 'Turn pacing cannot exceed 10,000.'
    }

    const maxTime = props.form?.max_time_per_turn
    if (maxTime !== null && maxTime !== undefined && maxTime !== '') {
      const maxNum = Number(maxTime)
      if (isNaN(maxNum) || !isFinite(maxNum) || maxNum <= 0) {
        errors.units_max = 'Max limit must be greater than 0.'
      } else if (maxNum > 10000) {
        errors.units_max = 'Max limit cannot exceed 10,000.'
      } else if (!isNaN(pacing) && isFinite(pacing) && maxNum < pacing) {
        errors.units_max = 'Max limit cannot be less than turn pacing.'
      }
    }
  }

  return errors
})

const hasTimeValidationErrors = computed(() => {
  return Object.keys(timeValidationErrors.value).length > 0
})

const clockConfigChanged = computed(() => {
  const advClock = !!props.adventure?.clock_enabled
  const advTimeConfig = props.adventure?.time_config || {}
  const formTimeConfig = props.form?.time_config || {}
  const advTimeSystem = props.adventure?.time_system === 'units' ? 'units' : 'relative'
  const formTimeSystem = props.form?.time_system === 'units' ? 'units' : 'relative'
  const advPacing = props.adventure?.time_per_turn ?? 5
  const formPacing = props.form?.time_per_turn ?? 5
  const advMaxTime = props.adventure?.max_time_per_turn ?? null
  const formMaxTime = props.form?.max_time_per_turn ?? null

  return (
    !!props.form?.clock_enabled !== advClock
    || formTimeSystem !== advTimeSystem
    || formPacing !== advPacing
    || formMaxTime !== advMaxTime
    || (props.form?.gm_time_control ?? true) !== (props.adventure?.gm_time_control ?? true)
    || (formTimeConfig.start_time || '08:00') !== (advTimeConfig.start_time || '08:00')
    || (formTimeConfig.day_label || 'Day') !== (advTimeConfig.day_label || 'Day')
    || Number(formTimeConfig.initial_day ?? 1) !== Number(advTimeConfig.initial_day ?? 1)
    || (formTimeConfig.time_format || '24h') !== (advTimeConfig.time_format || '24h')
    || (formTimeConfig.unit_name || 'Blobs') !== (advTimeConfig.unit_name || 'Blobs')
    || Number(formTimeConfig.initial_value ?? 0) !== Number(advTimeConfig.initial_value ?? 0)
    || formTimeConfig.calendar_pacing_value !== advTimeConfig.calendar_pacing_value
    || formTimeConfig.calendar_pacing_unit !== advTimeConfig.calendar_pacing_unit
    || formTimeConfig.calendar_max_value !== advTimeConfig.calendar_max_value
    || formTimeConfig.calendar_max_unit !== advTimeConfig.calendar_max_unit
  )
})

function discardClockConfig() {
  const advTimeConfig = props.adventure?.time_config || {}
  emit('update:clock-enabled', !!props.adventure?.clock_enabled)
  emit('update:time-system', props.adventure?.time_system === 'units' ? 'units' : 'relative')
  emit('update:pacing', props.adventure?.time_per_turn ?? 5)
  emit('update:max-time-per-turn', props.adventure?.max_time_per_turn ?? null)
  emit('update:gm-time-control', props.adventure?.gm_time_control ?? true)
  emit('update:start-time', advTimeConfig.start_time || '08:00')
  emit('update:day-label', advTimeConfig.day_label || 'Day')
  emit('update:initial-day', advTimeConfig.initial_day ?? 1)
  emit('update:time-format', advTimeConfig.time_format || '24h')
  emit('update:unit-name', advTimeConfig.unit_name || 'Blobs')
  emit('update:initial-value', advTimeConfig.initial_value ?? 0)
  if (advTimeConfig.calendar_pacing_value !== undefined) {
    emit('update:calendar-pacing-value', advTimeConfig.calendar_pacing_value)
  }
  if (advTimeConfig.calendar_pacing_unit) {
    emit('update:calendar-pacing-unit', advTimeConfig.calendar_pacing_unit)
  }
  if (advTimeConfig.calendar_max_value !== undefined) {
    emit('update:calendar-max-value', advTimeConfig.calendar_max_value)
  }
  if (advTimeConfig.calendar_max_unit) {
    emit('update:calendar-max-unit', advTimeConfig.calendar_max_unit)
  }
}

const previewGameTime = computed(() => {
  const sys = props.form?.time_system === 'units' ? 'units' : 'relative'
  const timeConfig = props.form?.time_config || {}
  if (sys === 'units') {
    const unitName = timeConfig.unit_name?.trim() || 'Blobs'
    const initialVal = Number(timeConfig.initial_value ?? 0)
    return {
      dateShort: unitName,
      time: isNaN(initialVal) ? '0' : String(initialVal),
      isUnits: true,
    }
  }
  const timeStr = timeConfig.start_time || '08:00'
  const dayLabel = timeConfig.day_label?.trim() || 'Day'
  const initialDay = Math.max(1, Number(timeConfig.initial_day ?? 1) || 1)
  let timeDisplay = timeStr
  if (timeConfig.time_format === '12h') {
    try {
      const [h, m] = timeStr.split(':').map(Number)
      if (!isNaN(h) && !isNaN(m)) {
        const h12 = h % 12 || 12
        const ampm = h >= 12 ? 'PM' : 'AM'
        timeDisplay = `${h12.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')} ${ampm}`
      }
    } catch {
      // Unparseable start time: keep the 24h display.
    }
  }
  return {
    dateShort: `${dayLabel} ${initialDay}`,
    time: timeDisplay,
    isUnits: false,
  }
})
</script>

<template>
  <div class="space-y-8 animate-page-in">
    <!-- In-Game Time System & Pacing -->
    <div class="bg-slate-900/40 p-6 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl space-y-6">
      <div class="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 border-b border-white/5 pb-4">
        <div>
          <label class="block text-xs font-black text-slate-400 uppercase tracking-[0.2em]">In-Game Time System & Pacing</label>
          <p class="text-xs text-slate-500 mt-0.5">Configure game days or custom time units, round pacing, and GM time limits.</p>
        </div>
        <div class="flex items-center gap-3 self-end sm:self-auto">
          <div v-if="clockConfigChanged" class="flex items-center gap-2 animate-fade-in mr-2">
            <button
              @click="emit('save-changes')"
              :disabled="isSaving || hasTimeValidationErrors"
              class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center"
              :title="hasTimeValidationErrors ? 'Please fix validation errors before saving' : 'Save changes'"
            >
              <i v-if="isSaving" class="ra ra-cycle animate-spin text-sm"></i>
              <Save v-else class="w-4 h-4" />
            </button>
            <button
              @click="discardClockConfig"
              :disabled="isSaving"
              class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-xl transition-all flex items-center justify-center"
              title="Discard changes"
            >
              <X class="w-4 h-4" />
            </button>
          </div>
          <button
            @click="emit('update:clock-enabled', !form.clock_enabled)"
            class="relative w-12 h-6 rounded-full transition-colors"
            :class="form.clock_enabled ? 'bg-emerald-500' : 'bg-slate-700'"
          >
            <div :class="['absolute top-1 w-4 h-4 bg-white rounded-full transition-all shadow-sm', form.clock_enabled ? 'left-7' : 'left-1']"></div>
          </button>
          <span class="text-xs font-bold uppercase tracking-widest" :class="form.clock_enabled ? 'text-emerald-400' : 'text-slate-500'">
            {{ form.clock_enabled ? 'Enabled' : 'Disabled' }}
          </span>
        </div>
      </div>

      <div v-if="form.clock_enabled" class="space-y-6 animate-fade-in">
        <!-- System Switcher: 2-mode Grid -->
        <div class="space-y-2">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Time System Type</label>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <button
              @click="emit('update:time-system', 'relative')"
              class="flex items-center gap-3 p-3.5 rounded-2xl text-xs font-black uppercase tracking-widest transition-all border text-left"
              :class="(form.time_system !== 'units') ? 'bg-amber-600/30 border-amber-500 text-white shadow-lg ring-1 ring-amber-500/50' : 'bg-black/40 border-white/10 text-slate-400 hover:text-white hover:border-white/20'"
            >
              <div class="p-2 rounded-xl bg-amber-500/20 text-amber-400">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              </div>
              <div>
                <div class="font-black text-sm">🪐 Game Day & Time</div>
                <div class="text-[10px] text-slate-400 font-normal mt-0.5">Day / Sol count, time of day & turn pacing</div>
              </div>
            </button>

            <button
              @click="emit('update:time-system', 'units')"
              class="flex items-center gap-3 p-3.5 rounded-2xl text-xs font-black uppercase tracking-widest transition-all border text-left"
              :class="form.time_system === 'units' ? 'bg-cyan-600/30 border-cyan-500 text-white shadow-lg ring-1 ring-cyan-500/50' : 'bg-black/40 border-white/10 text-slate-400 hover:text-white hover:border-white/20'"
            >
              <div class="p-2 rounded-xl bg-cyan-500/20 text-cyan-400">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0zM13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div>
                <div class="font-black text-sm">⏳ Custom Time Units</div>
                <div class="text-[10px] text-slate-400 font-normal mt-0.5">e.g. Lightyears, Blobs, Cycles, Sandglasses</div>
              </div>
            </button>
          </div>
        </div>

        <!-- Mode 1: Game Day & Time (Relative) -->
        <div v-if="form.time_system !== 'units'" class="space-y-6">
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 bg-black/30 p-5 rounded-2xl border border-white/5">
            <!-- Day Label -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-amber-400 uppercase tracking-[0.2em]">Day Label</label>
              <input
                :value="form.time_config?.day_label ?? 'Day'"
                @input="handleDayLabelInput"
                type="text"
                maxlength="30"
                placeholder="e.g. Day, Sol, Cycle, Tag"
                class="w-full bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold outline-none transition-all"
                :class="timeValidationErrors.day_label ? 'border-red-500/80 focus:ring-2 ring-red-500/20' : 'border-amber-500/50 focus:ring-2 ring-amber-500/20'"
              />
              <p v-if="timeValidationErrors.day_label" class="text-[10px] text-red-400 font-bold">{{ timeValidationErrors.day_label }}</p>
              <p v-else class="text-[10px] text-slate-500">Label in HUD and GM prompt (e.g. "Day 1", "Sol 42").</p>
            </div>

            <!-- Start Day -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-amber-400 uppercase tracking-[0.2em]">Start Day</label>
              <input
                type="number"
                min="1"
                max="10000"
                step="1"
                :value="form.time_config?.initial_day ?? 1"
                @input="handleInitialDayInput"
                placeholder="1"
                class="w-full bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold outline-none transition-all"
                :class="timeValidationErrors.initial_day ? 'border-red-500/80 focus:ring-2 ring-red-500/20' : 'border-amber-500/50 focus:ring-2 ring-amber-500/20'"
              />
              <p v-if="timeValidationErrors.initial_day" class="text-[10px] text-red-400 font-bold">{{ timeValidationErrors.initial_day }}</p>
              <p v-else class="text-[10px] text-slate-500">Initial day number at adventure start (default: 1, max: 10,000).</p>
            </div>

            <!-- Start Time -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-amber-400 uppercase tracking-[0.2em]">Start Time</label>
              
              <!-- 24h mode input -->
              <input
                v-if="form.time_config?.time_format !== '12h'"
                type="time"
                :value="form.time_config?.start_time || '08:00'"
                @input="handleStartTimeInput"
                class="w-full bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold outline-none transition-all"
                :class="timeValidationErrors.start_time ? 'border-red-500/80 focus:ring-2 ring-red-500/20' : 'border-amber-500/50 focus:ring-2 ring-amber-500/20'"
              />

              <!-- 12h mode input: Hour (1-12) : Minute (00-59) + AM/PM toggle -->
              <div
                v-else
                class="flex items-center gap-1.5 bg-black/60 border rounded-xl px-3 py-1.5 transition-all"
                :class="timeValidationErrors.start_time ? 'border-red-500/80 focus-within:ring-2 ring-red-500/20' : 'border-amber-500/50 focus-within:ring-2 ring-amber-500/20'"
              >
                <!-- 1-12 Hour Input -->
                <input
                  type="number"
                  min="1"
                  max="12"
                  step="1"
                  :value="time12Parts.hour12"
                  @input="handle12hHourInput"
                  class="w-10 bg-transparent text-white text-sm font-bold text-center outline-none"
                  title="Hour (1-12)"
                />
                <span class="text-amber-400 font-bold">:</span>
                <!-- 00-59 Minute Input -->
                <input
                  type="number"
                  min="0"
                  max="59"
                  step="1"
                  :value="time12Parts.minuteStr"
                  @input="handle12hMinuteInput"
                  class="w-10 bg-transparent text-white text-sm font-bold text-center outline-none"
                  title="Minute (00-59)"
                />
                <!-- AM / PM Switcher -->
                <div class="flex bg-black/50 p-0.5 rounded-lg border border-white/10 ml-auto">
                  <button
                    type="button"
                    @click="handle12hAmpmChange('AM')"
                    class="px-2 py-1 rounded text-[10px] font-black uppercase transition-all"
                    :class="time12Parts.ampm === 'AM' ? 'bg-amber-500 text-slate-950 font-black shadow-sm' : 'text-slate-400 hover:text-white'"
                  >
                    AM
                  </button>
                  <button
                    type="button"
                    @click="handle12hAmpmChange('PM')"
                    class="px-2 py-1 rounded text-[10px] font-black uppercase transition-all"
                    :class="time12Parts.ampm === 'PM' ? 'bg-amber-500 text-slate-950 font-black shadow-sm' : 'text-slate-400 hover:text-white'"
                  >
                    PM
                  </button>
                </div>
              </div>

              <p v-if="timeValidationErrors.start_time" class="text-[10px] text-red-400 font-bold">{{ timeValidationErrors.start_time }}</p>
              <p v-else class="text-[10px] text-slate-500">
                {{ form.time_config?.time_format === '12h' ? '12-hour start time with AM/PM.' : 'Time of day when the adventure begins.' }}
              </p>
            </div>

            <!-- Time Format -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-amber-400 uppercase tracking-[0.2em]">Time Format</label>
              <div class="grid grid-cols-2 gap-1 bg-black/60 p-1 rounded-xl border border-amber-500/50">
                <button
                  type="button"
                  @click="handleTimeFormatInput('24h')"
                  class="py-2 px-2 rounded-lg text-xs font-black uppercase tracking-wider transition-all text-center"
                  :class="(form.time_config?.time_format || '24h') === '24h' ? 'bg-amber-500 text-slate-950 shadow-sm' : 'text-slate-400 hover:text-white'"
                >
                  24h
                </button>
                <button
                  type="button"
                  @click="handleTimeFormatInput('12h')"
                  class="py-2 px-2 rounded-lg text-xs font-black uppercase tracking-wider transition-all text-center"
                  :class="form.time_config?.time_format === '12h' ? 'bg-amber-500 text-slate-950 shadow-sm' : 'text-slate-400 hover:text-white'"
                >
                  12h (AM/PM)
                </button>
              </div>
              <p class="text-[10px] text-slate-500">24-hour clock (14:00) or 12h (02:00 PM).</p>
            </div>
          </div>

          <!-- Pacing & GM Max Limit -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6 bg-black/30 p-5 rounded-2xl border border-white/5">
            <!-- Pacing -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-amber-400 uppercase tracking-[0.2em]">Round Pacing (Time per Turn)</label>
              <div class="flex gap-2">
                <input
                  type="number"
                  min="1"
                  max="10000"
                  step="1"
                  :value="getCalendarPacingValue()"
                  @input="handleCalendarPacingValueChange"
                  class="w-1/3 bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold outline-none transition-all text-center"
                  :class="timeValidationErrors.pacing ? 'border-red-500/80 focus:ring-2 ring-red-500/20' : 'border-amber-500/50 focus:ring-2 ring-amber-500/20'"
                />
                <select
                  :value="getCalendarPacingUnit()"
                  @change="handleCalendarPacingUnitChange"
                  class="w-2/3 bg-black/60 border border-amber-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-amber-500/20 outline-none transition-all cursor-pointer"
                >
                  <option v-for="u in CALENDAR_UNITS" :key="u.value" :value="u.value" class="bg-slate-900 text-white">
                    {{ u.label }}
                  </option>
                </select>
              </div>
              <p v-if="timeValidationErrors.pacing" class="text-[10px] text-red-400 font-bold">{{ timeValidationErrors.pacing }}</p>
              <p v-else class="text-[10px] text-slate-500">Time that passes after every narrated player message (max: 10,000). Scripts can change it in-game with tw.time.set_minutes_per_tick().</p>
            </div>

            <!-- Max Time per Turn (GM Limit) -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-slate-400 uppercase tracking-[0.2em]">Max Time per Turn (GM Limit)</label>
              <div class="flex gap-2">
                <input
                  type="number"
                  min="1"
                  max="10000"
                  step="1"
                  placeholder="Uncapped (Optional)"
                  :value="getCalendarMaxValue()"
                  @input="handleCalendarMaxValueChange"
                  class="w-1/3 bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold outline-none transition-all text-center"
                  :class="timeValidationErrors.max_time ? 'border-red-500/80 focus:ring-2 ring-red-500/20' : 'border-amber-500/50 focus:ring-2 ring-amber-500/20'"
                />
                <select
                  :value="getCalendarMaxUnit()"
                  @change="handleCalendarMaxUnitChange"
                  class="w-2/3 bg-black/60 border border-amber-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-amber-500/20 outline-none transition-all cursor-pointer"
                >
                  <option v-for="u in CALENDAR_UNITS" :key="u.value" :value="u.value" class="bg-slate-900 text-white">
                    {{ u.label }}
                  </option>
                </select>
              </div>
              <p v-if="timeValidationErrors.max_time" class="text-[10px] text-red-400 font-bold">{{ timeValidationErrors.max_time }}</p>
              <p v-else class="text-[10px] text-slate-500">Caps pacing plus the GM's extra time for one message (max: 10,000).</p>
            </div>
          </div>
        </div>

        <!-- Mode 2: Custom Time Units -->
        <div v-else class="space-y-6">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6 bg-black/30 p-5 rounded-2xl border border-white/5">
            <!-- Unit Name -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-cyan-400 uppercase tracking-[0.2em]">Time Unit Name</label>
              <input
                :value="form.time_config?.unit_name ?? 'Blobs'"
                @input="handleUnitNameInput"
                type="text"
                maxlength="30"
                placeholder="e.g. Days, Lightyears, Blobs, Cycles, Sandglasses"
                class="w-full bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold outline-none transition-all"
                :class="timeValidationErrors.unit_name ? 'border-red-500/80 focus:ring-2 ring-red-500/20' : 'border-cyan-500/50 focus:ring-2 ring-cyan-500/20'"
              />
              <p v-if="timeValidationErrors.unit_name" class="text-[10px] text-red-400 font-bold">{{ timeValidationErrors.unit_name }}</p>
              <p v-else class="text-[10px] text-slate-500">Custom time unit name (e.g. "Lightyears", "Blobs").</p>
            </div>

            <!-- Initial Value -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-cyan-400 uppercase tracking-[0.2em]">Initial Value</label>
              <input
                :value="form.time_config?.initial_value ?? 0"
                @input="handleInitialValueInput"
                type="number"
                min="0"
                max="10000"
                step="any"
                placeholder="0"
                class="w-full bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold outline-none transition-all"
                :class="timeValidationErrors.initial_value ? 'border-red-500/80 focus:ring-2 ring-red-500/20' : 'border-cyan-500/50 focus:ring-2 ring-cyan-500/20'"
              />
              <p v-if="timeValidationErrors.initial_value" class="text-[10px] text-red-400 font-bold">{{ timeValidationErrors.initial_value }}</p>
              <p v-else class="text-[10px] text-slate-500">Starting numeric counter value (0 - 10,000).</p>
            </div>
          </div>

          <!-- Units Pacing & GM Max Limit -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6 bg-black/30 p-5 rounded-2xl border border-white/5">
            <!-- Pacing -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-cyan-400 uppercase tracking-[0.2em]">
                Round Pacing ({{ form.time_config?.unit_name || 'Units' }} per Turn)
              </label>
              <input
                type="number"
                step="any"
                min="0.001"
                max="10000"
                :value="form.time_per_turn ?? 1"
                @input="handleUnitsPacingChange"
                placeholder="e.g. 1"
                class="w-full bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold outline-none transition-all"
                :class="timeValidationErrors.units_pacing ? 'border-red-500/80 focus:ring-2 ring-red-500/20' : 'border-cyan-500/50 focus:ring-2 ring-cyan-500/20'"
              />
              <p v-if="timeValidationErrors.units_pacing" class="text-[10px] text-red-400 font-bold">{{ timeValidationErrors.units_pacing }}</p>
              <p v-else class="text-[10px] text-slate-500">Default {{ form.time_config?.unit_name || 'units' }} that elapse after every narrated player message (max: 10,000). Scripts can change it with tw.time.set_minutes_per_tick().</p>
            </div>

            <!-- Max Units (GM Limit) -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-slate-400 uppercase tracking-[0.2em]">
                Max {{ form.time_config?.unit_name || 'Units' }} per Turn (GM Limit)
              </label>
              <input
                type="number"
                step="any"
                min="0.001"
                max="10000"
                :value="form.max_time_per_turn ?? ''"
                @input="handleUnitsMaxChange"
                placeholder="e.g. 10 (Optional)"
                class="w-full bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold outline-none transition-all"
                :class="timeValidationErrors.units_max ? 'border-red-500/80 focus:ring-2 ring-red-500/20' : 'border-cyan-500/50 focus:ring-2 ring-cyan-500/20'"
              />
              <p v-if="timeValidationErrors.units_max" class="text-[10px] text-red-400 font-bold">{{ timeValidationErrors.units_max }}</p>
              <p v-else class="text-[10px] text-slate-500">Maximum {{ form.time_config?.unit_name || 'units' }} allowed per turn (max: 10,000).</p>
            </div>
          </div>
        </div>

        <!-- Live Widget Preview -->
        <div class="flex items-center justify-between p-4 rounded-2xl bg-black/40 border border-white/10">
          <div class="space-y-1">
            <span class="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Live In-Game Clock Preview</span>
            <p class="text-xs text-slate-500">How the in-game clock widget appears during gameplay:</p>
          </div>
          <div class="flex items-center gap-2.5 px-3.5 py-1.5 bg-slate-900/90 border border-slate-700/60 rounded-xl backdrop-blur-md shadow-lg">
            <svg v-if="!previewGameTime.isUnits" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-amber-500/80 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-cyan-400/90 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0zM13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <div class="flex flex-col items-end min-w-0">
              <span
                class="text-xs font-black uppercase tracking-widest leading-none mb-1 whitespace-nowrap truncate max-w-[140px]"
                :class="previewGameTime.isUnits ? 'text-cyan-400/70' : 'text-amber-500/60'"
              >
                {{ previewGameTime.dateShort }}
              </span>
              <span
                class="text-lg font-black tracking-widest leading-none tabular-nums"
                :class="previewGameTime.isUnits ? 'text-cyan-300' : 'text-amber-300'"
                style="font-family: monospace;"
              >
                {{ previewGameTime.time }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <GmTimeControlToggle
      :model-value="form.gm_time_control ?? true"
      @update:model-value="emit('update:gm-time-control', $event)"
    />
  </div>
</template>
