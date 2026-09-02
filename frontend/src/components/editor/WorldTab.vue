<script setup lang="ts">
import PlotTab from '@/components/editor/PlotTab.vue'
import { Save, X } from 'lucide-vue-next'
import { computed } from 'vue'

const props = defineProps<{
  form: any
  adventure: any
  debugData: any
  referenceOptions?: Array<{ id: string; name?: string; imageUrl?: string | null }>
  editingField: string | null
  tempValue: string
  isSaving: boolean
  isBatchGenerating: Record<string, boolean>
  isQuickGenerating: Record<string, boolean>
  isGeneratingField: Record<string, boolean>
  activeMenuId: string | null
  fixNewlines: (text: string) => string
}>()

const emit = defineEmits<{
  (e: 'quick-regen', kind: string, id: string): void
  (e: 'open-regen-dialog', kind: string, id: string, label: string): void
  (e: 'open-upload-picker', kind: string, id: string, label: string): void
  (e: 'download-asset', path: string, label: string): void
  (e: 'open-text-edit', ...args: any[]): void
  (e: 'toggle-menu', id: string, event: MouseEvent): void
  (e: 'start-edit', field: string, value: string): void
  (e: 'save-field'): void
  (e: 'cancel-edit'): void
  (e: 'generate-field', field: string): void
  (e: 'update:tempValue', val: string): void
  (e: 'update:mode', val: 'rpg' | 'story' | 'chat'): void
  (e: 'save-changes'): void
  (e: 'update:pacing', val: number): void
  (e: 'update:max-time-per-turn', val: number | null): void
  (e: 'update:clock-enabled', val: boolean): void
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

function buildVisualImageUrl(imagePath?: string | null) {
  if (!imagePath) return ''
  return imagePath
}

function getCoverNarrativeContext() {
  if (!props.debugData) return ''
  return props.debugData.adventure?.plot || props.debugData.adventure?.original_prompt || ''
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
    if (isNaN(dayNum) || dayNum < 1 || !Number.isInteger(dayNum)) {
      errors.initial_day = 'Start day must be an integer >= 1.'
    }

    if (!cfg.start_time || !/^([01]\d|2[0-3]):([0-5]\d)$/.test(cfg.start_time)) {
      errors.start_time = 'Start time must be a valid time in HH:MM format (00:00 - 23:59).'
    }

    const pacingVal = getCalendarPacingValue()
    if (isNaN(pacingVal) || pacingVal < 1) {
      errors.pacing = 'Turn pacing must be at least 1.'
    }

    const maxValStr = getCalendarMaxValue()
    if (maxValStr) {
      const maxVal = Number(maxValStr)
      if (isNaN(maxVal) || maxVal < 1) {
        errors.max_time = 'Max limit must be at least 1.'
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
    if (isNaN(initVal)) {
      errors.initial_value = 'Initial value must be a valid number.'
    }

    const pacing = Number(props.form?.time_per_turn ?? 1)
    if (isNaN(pacing) || pacing <= 0) {
      errors.units_pacing = 'Turn pacing must be greater than 0.'
    }

    const maxTime = props.form?.max_time_per_turn
    if (maxTime !== null && maxTime !== undefined && maxTime !== '') {
      const maxNum = Number(maxTime)
      if (isNaN(maxNum) || maxNum <= 0) {
        errors.units_max = 'Max limit must be greater than 0.'
      } else if (!isNaN(pacing) && maxNum < pacing) {
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
    } catch (e) {}
  }
  return {
    dateShort: `${dayLabel} ${initialDay}`,
    time: timeDisplay,
    isUnits: false,
  }
})

const URL_PATTERN = /^(https?:\/\/)[^\s/$.?#].[^\s]*$/i

const licenseUrlInvalid = computed(() => {
  if (props.editingField !== 'license_url') return false
  if (!props.tempValue.trim()) return false
  return !URL_PATTERN.test(props.tempValue.trim())
})
</script>

<template>
  <div class="space-y-8 animate-page-in">
    <!-- General Chronicle Settings -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 bg-slate-900/40 p-6 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
      <div class="space-y-2">
        <div class="flex justify-between items-center">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Chronicle Title</label>
          <span v-if="editingField === 'title'" :class="['text-[10px] font-bold tracking-widest', (!tempValue.trim() || tempValue.length > 50) ? 'text-red-500' : 'text-emerald-500/50']">
            {{ tempValue.length }} / 50
          </span>
        </div>
        <div v-if="editingField === 'title'" class="flex gap-2 animate-fade-in">
          <input :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLInputElement).value)" @keyup.enter="(!tempValue.trim() || tempValue.length > 50) ? null : emit('save-field')" @keyup.esc="emit('cancel-edit')" type="text" maxlength="50" class="flex-grow bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all" />
          <button @click="emit('save-field')" :disabled="isSaving || !tempValue.trim() || tempValue.length > 50" class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg disabled:opacity-50">
            <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
            <Save v-else class="w-4 h-4" />
          </button>
          <button @click="emit('cancel-edit')" class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-xl transition-all">
            <X class="w-4 h-4" />
          </button>
        </div>
        <div v-else @click="emit('start-edit', 'title', form.title)" class="group cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center">
          <span class="text-sm font-bold text-white">{{ form.title }}</span>
          <i class="ra ra-quill-pen text-xs text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity"></i>
        </div>
      </div>

      <div class="space-y-2">
        <div class="flex justify-between items-center">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Version</label>
          <span v-if="editingField === 'version'" :class="['text-[10px] font-bold tracking-widest', tempValue.length > 15 ? 'text-red-500' : 'text-emerald-500/50']">
            {{ tempValue.length }} / 15
          </span>
        </div>
        <div v-if="editingField === 'version'" class="flex gap-2 animate-fade-in">
          <input :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLInputElement).value)" @keyup.enter="tempValue.length > 15 ? null : emit('save-field')" @keyup.esc="emit('cancel-edit')" type="text" maxlength="15" placeholder="e.g. 1.0.0" class="flex-grow bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all" />
          <button @click="emit('save-field')" :disabled="isSaving || tempValue.length > 15" class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg disabled:opacity-50">
            <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
            <Save v-else class="w-4 h-4" />
          </button>
          <button @click="emit('cancel-edit')" class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-xl transition-all">
            <X class="w-4 h-4" />
          </button>
        </div>
        <div v-else @click="emit('start-edit', 'version', form.version)" class="group cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center">
          <span v-if="form.version" class="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 uppercase tracking-widest">v{{ form.version }}</span>
          <span v-else class="text-xs italic text-slate-600 uppercase tracking-widest">No version set</span>
          <i class="ra ra-quill-pen text-xs text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity"></i>
        </div>
      </div>

      <!-- Adventure Style -->
      <div class="space-y-2">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Adventure Style</label>
        <div class="grid grid-cols-3 gap-2">
          <button
            @click="emit('update:mode', 'rpg')"
            class="px-4 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all border"
            :class="form.rule_enforcement_mode === 'rpg' ? 'bg-emerald-600/80 border-emerald-500 text-white' : 'bg-black/40 border-white/10 text-slate-400 hover:text-white'"
          >
            RPG
          </button>
          <button
            @click="emit('update:mode', 'story')"
            class="px-4 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all border"
            :class="form.rule_enforcement_mode === 'story' ? 'bg-emerald-600/80 border-emerald-500 text-white' : 'bg-black/40 border-white/10 text-slate-400 hover:text-white'"
          >
            Story
          </button>
          <button
            @click="emit('update:mode', 'chat')"
            class="px-4 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all border"
            :class="form.rule_enforcement_mode === 'chat' ? 'bg-emerald-600/80 border-emerald-500 text-white' : 'bg-black/40 border-white/10 text-slate-400 hover:text-white'"
          >
            Chat
          </button>
        </div>
      </div>
    </div>

    <!-- Unified In-Game Time System & Pacing Panel -->
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
                :value="form.time_config?.day_label || 'Day'"
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
                step="1"
                :value="form.time_config?.initial_day ?? 1"
                @input="handleInitialDayInput"
                placeholder="1"
                class="w-full bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold outline-none transition-all"
                :class="timeValidationErrors.initial_day ? 'border-red-500/80 focus:ring-2 ring-red-500/20' : 'border-amber-500/50 focus:ring-2 ring-amber-500/20'"
              />
              <p v-if="timeValidationErrors.initial_day" class="text-[10px] text-red-400 font-bold">{{ timeValidationErrors.initial_day }}</p>
              <p v-else class="text-[10px] text-slate-500">Initial day number at adventure start (default: 1).</p>
            </div>

            <!-- Start Time -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-amber-400 uppercase tracking-[0.2em]">Start Time</label>
              <input
                type="time"
                :value="form.time_config?.start_time || '08:00'"
                @input="handleStartTimeInput"
                class="w-full bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold outline-none transition-all"
                :class="timeValidationErrors.start_time ? 'border-red-500/80 focus:ring-2 ring-red-500/20' : 'border-amber-500/50 focus:ring-2 ring-amber-500/20'"
              />
              <p v-if="timeValidationErrors.start_time" class="text-[10px] text-red-400 font-bold">{{ timeValidationErrors.start_time }}</p>
              <p v-else class="text-[10px] text-slate-500">Time of day when the adventure begins.</p>
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
              <p v-else class="text-[10px] text-slate-500">Standard in-game time advancement each turn.</p>
            </div>

            <!-- Max Time per Turn (GM Limit) -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-slate-400 uppercase tracking-[0.2em]">Max Time per Turn (GM Limit)</label>
              <div class="flex gap-2">
                <input
                  type="number"
                  min="1"
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
              <p v-else class="text-[10px] text-slate-500">Maximum time advancement allowed per turn for complex GM actions.</p>
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
                :value="form.time_config?.unit_name || 'Blobs'"
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
                step="any"
                placeholder="0"
                class="w-full bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold outline-none transition-all"
                :class="timeValidationErrors.initial_value ? 'border-red-500/80 focus:ring-2 ring-red-500/20' : 'border-cyan-500/50 focus:ring-2 ring-cyan-500/20'"
              />
              <p v-if="timeValidationErrors.initial_value" class="text-[10px] text-red-400 font-bold">{{ timeValidationErrors.initial_value }}</p>
              <p v-else class="text-[10px] text-slate-500">Starting numeric counter value when adventure begins.</p>
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
                :value="form.time_per_turn ?? 1"
                @input="handleUnitsPacingChange"
                placeholder="e.g. 1"
                class="w-full bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold outline-none transition-all"
                :class="timeValidationErrors.units_pacing ? 'border-red-500/80 focus:ring-2 ring-red-500/20' : 'border-cyan-500/50 focus:ring-2 ring-cyan-500/20'"
              />
              <p v-if="timeValidationErrors.units_pacing" class="text-[10px] text-red-400 font-bold">{{ timeValidationErrors.units_pacing }}</p>
              <p v-else class="text-[10px] text-slate-500">Default {{ form.time_config?.unit_name || 'units' }} that elapse automatically each turn.</p>
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
                :value="form.max_time_per_turn ?? ''"
                @input="handleUnitsMaxChange"
                placeholder="e.g. 10 (Optional)"
                class="w-full bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold outline-none transition-all"
                :class="timeValidationErrors.units_max ? 'border-red-500/80 focus:ring-2 ring-red-500/20' : 'border-cyan-500/50 focus:ring-2 ring-cyan-500/20'"
              />
              <p v-if="timeValidationErrors.units_max" class="text-[10px] text-red-400 font-bold">{{ timeValidationErrors.units_max }}</p>
              <p v-else class="text-[10px] text-slate-500">Maximum {{ form.time_config?.unit_name || 'units' }} allowed per turn for complex GM actions.</p>
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

    <!-- Creator, Copyright & License Info -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 bg-slate-900/40 p-6 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
      <!-- Creator -->
      <div class="space-y-2">
        <div class="flex justify-between items-center">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Creator</label>
          <span v-if="editingField === 'creator'" :class="['text-[10px] font-bold tracking-widest', (!tempValue.trim() || tempValue.length > 100) ? 'text-red-500' : 'text-emerald-500/50']">
            {{ tempValue.length }} / 100
          </span>
        </div>
        <div v-if="editingField === 'creator'" class="flex gap-2 animate-fade-in">
          <input :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLInputElement).value)" @keyup.enter="(!tempValue.trim() || tempValue.length > 100) ? null : emit('save-field')" @keyup.esc="emit('cancel-edit')" type="text" maxlength="100" placeholder="e.g. Jane Doe" :class="['flex-grow bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all', (!tempValue.trim() || tempValue.length > 100) ? 'border-red-500/50' : 'border-emerald-500/50']" />
          <button @click="emit('save-field')" :disabled="isSaving || !tempValue.trim() || tempValue.length > 100" class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg disabled:opacity-50">
            <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
            <Save v-else class="w-4 h-4" />
          </button>
          <button @click="emit('cancel-edit')" class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-xl transition-all">
            <X class="w-4 h-4" />
          </button>
        </div>
        <div v-else @click="emit('start-edit', 'creator', form.creator)" class="group cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center">
          <span v-if="form.creator" class="text-sm font-bold text-white">{{ form.creator }}</span>
          <span v-else class="text-xs italic text-slate-600 uppercase tracking-widest">No creator set</span>
          <i class="ra ra-quill-pen text-xs text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity"></i>
        </div>
      </div>

      <!-- Copyright -->
      <div class="space-y-2">
        <div class="flex justify-between items-center">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Copyright</label>
          <span v-if="editingField === 'copyright'" :class="['text-[10px] font-bold tracking-widest', (!tempValue.trim() || tempValue.length > 100) ? 'text-red-500' : 'text-emerald-500/50']">
            {{ tempValue.length }} / 100
          </span>
        </div>
        <div v-if="editingField === 'copyright'" class="flex gap-2 animate-fade-in">
          <input :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLInputElement).value)" @keyup.enter="(!tempValue.trim() || tempValue.length > 100) ? null : emit('save-field')" @keyup.esc="emit('cancel-edit')" type="text" maxlength="100" placeholder="e.g. Copyright (c) 2026" :class="['flex-grow bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all', (!tempValue.trim() || tempValue.length > 100) ? 'border-red-500/50' : 'border-emerald-500/50']" />
          <button @click="emit('save-field')" :disabled="isSaving || !tempValue.trim() || tempValue.length > 100" class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg disabled:opacity-50">
            <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
            <Save v-else class="w-4 h-4" />
          </button>
          <button @click="emit('cancel-edit')" class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-xl transition-all">
            <X class="w-4 h-4" />
          </button>
        </div>
        <div v-else @click="emit('start-edit', 'copyright', form.copyright)" class="group cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center">
          <span v-if="form.copyright" class="text-sm font-bold text-white">{{ form.copyright }}</span>
          <span v-else class="text-xs italic text-slate-600 uppercase tracking-widest">No copyright set</span>
          <i class="ra ra-quill-pen text-xs text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity"></i>
        </div>
      </div>

      <!-- License -->
      <div class="space-y-2">
        <div class="flex justify-between items-center">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">License</label>
          <span v-if="editingField === 'license'" :class="['text-[10px] font-bold tracking-widest', (!tempValue.trim() || tempValue.length > 100) ? 'text-red-500' : 'text-emerald-500/50']">
            {{ tempValue.length }} / 100
          </span>
        </div>
        <div v-if="editingField === 'license'" class="flex gap-2 animate-fade-in">
          <input :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLInputElement).value)" @keyup.enter="(!tempValue.trim() || tempValue.length > 100) ? null : emit('save-field')" @keyup.esc="emit('cancel-edit')" type="text" maxlength="100" placeholder="e.g. MIT, CC-BY-4.0" :class="['flex-grow bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all', (!tempValue.trim() || tempValue.length > 100) ? 'border-red-500/50' : 'border-emerald-500/50']" />
          <button @click="emit('save-field')" :disabled="isSaving || !tempValue.trim() || tempValue.length > 100" class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg disabled:opacity-50">
            <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
            <Save v-else class="w-4 h-4" />
          </button>
          <button @click="emit('cancel-edit')" class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-xl transition-all">
            <X class="w-4 h-4" />
          </button>
        </div>
        <div v-else @click="emit('start-edit', 'license', form.license)" class="group cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center">
          <span v-if="form.license" class="text-sm font-bold text-white">{{ form.license }}</span>
          <span v-else class="text-xs italic text-slate-600 uppercase tracking-widest">No license set</span>
          <i class="ra ra-quill-pen text-xs text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity"></i>
        </div>
      </div>
    </div>

    <!-- License URL -->
    <div class="bg-slate-900/40 p-6 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl space-y-2">
      <div class="flex justify-between items-center">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">License URL</label>
        <span v-if="editingField === 'license_url'" :class="['text-[10px] font-bold tracking-widest', (licenseUrlInvalid || tempValue.length > 500) ? 'text-red-500' : 'text-emerald-500/50']">
          {{ tempValue.length }} / 500
        </span>
      </div>
      <div v-if="editingField === 'license_url'" class="flex gap-2 animate-fade-in">
        <input :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLInputElement).value)" @keyup.enter="(licenseUrlInvalid || tempValue.length > 500) ? null : emit('save-field')" @keyup.esc="emit('cancel-edit')" type="url" maxlength="500" placeholder="e.g. https://creativecommons.org/licenses/by-nc/4.0/" :class="['flex-grow bg-black/60 border rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all', (licenseUrlInvalid || tempValue.length > 500) ? 'border-red-500/50' : 'border-emerald-500/50']" />
        <button @click="emit('save-field')" :disabled="isSaving || licenseUrlInvalid || tempValue.length > 500" class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg disabled:opacity-50">
          <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
          <Save v-else class="w-4 h-4" />
        </button>
        <button @click="emit('cancel-edit')" class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-xl transition-all">
          <X class="w-4 h-4" />
        </button>
      </div>
      <div v-else @click="emit('start-edit', 'license_url', form.license_url || '')" class="group cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center gap-3">
        <a v-if="form.license_url" :href="form.license_url" target="_blank" rel="noopener noreferrer" @click.stop class="text-sm font-bold text-aether-primary hover:underline truncate">{{ form.license_url }}</a>
        <span v-else class="text-xs italic text-slate-600 uppercase tracking-widest">No license URL set</span>
        <i class="ra ra-quill-pen text-xs text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity"></i>
      </div>
    </div>

    <div class="bg-slate-900/40 p-6 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl space-y-2">
      <div class="flex justify-between items-center">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Teaser (Max 300 Characters)</label>
        <span v-if="editingField === 'teaser'" :class="['text-[10px] font-bold tracking-widest', tempValue.length > 300 ? 'text-red-500' : 'text-emerald-500/50']">
          {{ tempValue.length }} / 300
        </span>
      </div>
      <div v-if="editingField === 'teaser'" class="flex gap-2 animate-fade-in">
        <textarea
          :value="tempValue"
          @input="emit('update:tempValue', ($event.target as HTMLTextAreaElement).value)"
          @keyup.esc="emit('cancel-edit')"
          maxlength="300"
          rows="3"
          placeholder="A short, catchy teaser for your adventure..."
          class="flex-grow bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:ring-2 ring-emerald-500/20 outline-none transition-all resize-y min-h-[80px]"
        />
        <div class="flex flex-col gap-2">
          <button @click="emit('save-field')" :disabled="isSaving || tempValue.length > 300" class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg disabled:opacity-50">
            <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
            <Save v-else class="w-4 h-4" />
          </button>
          <button @click="emit('cancel-edit')" class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-xl transition-all">
            <X class="w-4 h-4" />
          </button>
        </div>
      </div>
      <div v-else @click="emit('start-edit', 'teaser', form.teaser || '')" class="group cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-3 transition-all duration-300 shadow-inner min-h-[80px]">
        <p v-if="form.teaser" class="text-sm font-bold text-emerald-500/80 whitespace-pre-wrap leading-relaxed">{{ form.teaser }}</p>
        <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest">No teaser set. Click to add a short tagline for your adventure.</p>
      </div>
    </div>

    <section v-if="debugData?.adventure" class="space-y-4 bg-slate-900/40 p-8 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">World Essence</h3>
        <button @click="emit('quick-regen', 'cover', debugData.adventure.id)" :disabled="isBatchGenerating['cover']" class="px-4 py-2 rounded-xl bg-white/5 hover:bg-emerald-500/10 border border-white/5 text-xs font-bold text-emerald-400 uppercase tracking-widest flex items-center gap-2 transition-all">
          <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['cover'] }"></i>
          Regenerate Cover
        </button>
      </div>
      <div class="relative group aspect-[3/2] bg-slate-900 border border-white/5 rounded-[2rem] overflow-hidden shadow-2xl max-w-2xl mx-auto">
        <img v-if="debugData.adventure.image_url" :src="buildVisualImageUrl(debugData.adventure.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-1000" />
        <div v-if="isQuickGenerating['cover_' + debugData.adventure.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
          <div class="flex flex-col items-center gap-2">
            <i class="ra ra-cycle animate-spin text-3xl text-emerald-500"></i>
            <span class="text-xs font-black text-emerald-500 uppercase tracking-widest">Reweaving Essence...</span>
          </div>
        </div>
        <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-transparent"></div>
        <div class="absolute inset-x-0 bottom-0 p-6">
          <div class="flex justify-between items-end gap-12">
            <div class="space-y-2 max-w-3xl">
              <h4 class="text-xl font-black text-white tracking-tight">{{ debugData.adventure.title }}</h4>
              <p v-if="debugData.adventure.teaser" class="text-xs font-bold text-emerald-500/80 uppercase tracking-widest">{{ debugData.adventure.teaser }}</p>
              <p v-else class="text-xs font-bold text-slate-500/40 uppercase tracking-widest italic">No teaser set...</p>
              <p class="text-sm text-slate-400 leading-relaxed line-clamp-1">{{ getCoverNarrativeContext() }}</p>
            </div>
            <div class="relative shrink-0">
              <button @click="emit('toggle-menu', debugData.adventure.id, $event)" class="w-10 h-10 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
                <div class="flex flex-col gap-0.5">
                  <div class="w-1.5 h-1.5 bg-white rounded-full"></div>
                  <div class="w-1.5 h-1.5 bg-white rounded-full"></div>
                  <div class="w-1.5 h-1.5 bg-white rounded-full"></div>
                </div>
              </button>
              <div v-if="activeMenuId === debugData.adventure.id" class="absolute right-0 bottom-full mb-3 w-56 bg-slate-900 border border-white/20 rounded-xl shadow-2xl overflow-hidden py-2 z-50 animate-fade-in ring-1 ring-white/10">
                <button @click="emit('quick-regen', 'cover', debugData.adventure.id)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-emerald-600 hover:text-white transition-all uppercase tracking-widest">Quick Regenerate</button>
                <button @click="emit('open-regen-dialog', 'cover', debugData.adventure.id, debugData.adventure.title)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-cyan-600 hover:text-white transition-all uppercase tracking-widest">Regenerate (Prompt)</button>
                <button @click="emit('open-upload-picker', 'cover', debugData.adventure.id, debugData.adventure.title)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-amber-600 hover:text-white transition-all uppercase tracking-widest">Upload Custom Cover</button>
                <button v-if="debugData.adventure.image_url" @click="emit('download-asset', debugData.adventure.image_url, `${debugData.adventure.title || 'adventure'}_cover`)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-violet-600 hover:text-white transition-all uppercase tracking-widest">Download Cover</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <PlotTab
      :form="form"
      :adventure="adventure"
      :reference-options="referenceOptions || []"
      :editing-field="editingField"
      :temp-value="tempValue"
      :is-saving="isSaving"
      :is-generating-field="isGeneratingField"
      :fix-newlines="fixNewlines"
      @update:temp-value="emit('update:tempValue', $event)"
      @update:mode="emit('update:mode', $event)"
      @start-edit="(field, value) => emit('start-edit', field, value)"
      @save-field="emit('save-field')"
      @cancel-edit="emit('cancel-edit')"
      @generate-field="emit('generate-field', $event)"
      @save-changes="emit('save-changes')"
    />
  </div>
</template>

<style scoped>
.animate-page-in { animation: pageIn 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
.animate-fade-in { animation: fadeIn 0.3s ease-out forwards; }
@keyframes pageIn { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
</style>
