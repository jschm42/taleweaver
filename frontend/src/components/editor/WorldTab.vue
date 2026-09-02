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
  { value: 'Minutes', label: 'Minuten (Minutes)' },
  { value: 'Hours', label: 'Stunden (Hours)' },
  { value: 'Days', label: 'Tage (Days)' },
  { value: 'Weeks', label: 'Wochen (Weeks)' },
  { value: 'Years', label: 'Jahre (Years)' },
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
  if (props.form?.time_config?.calendar_pacing_unit) {
    return props.form.time_config.calendar_pacing_unit
  }
  const t = props.form?.time_per_turn || 5
  if (t >= 525600 && t % 525600 === 0) return 'Years'
  if (t >= 10080 && t % 10080 === 0) return 'Weeks'
  if (t >= 1440 && t % 1440 === 0) return 'Days'
  if (t >= 60 && t % 60 === 0) return 'Hours'
  return 'Minutes'
}

function getCalendarMaxValue(): string {
  if (props.form?.time_config?.calendar_max_value !== undefined && props.form?.time_config?.calendar_max_value !== null) {
    return props.form.time_config.calendar_max_value === '' ? '' : String(props.form.time_config.calendar_max_value)
  }
  const mt = props.form?.max_time_per_turn
  if (mt && mt > 0) {
    if (mt >= 525600 && mt % 525600 === 0) return String(mt / 525600)
    if (mt >= 10080 && mt % 10080 === 0) return String(mt / 10080)
    if (mt >= 1440 && mt % 1440 === 0) return String(mt / 1440)
    if (mt >= 60 && mt % 60 === 0) return String(mt / 60)
    return String(mt)
  }
  return ''
}

function getCalendarMaxUnit(): string {
  if (props.form?.time_config?.calendar_max_unit) {
    return props.form.time_config.calendar_max_unit
  }
  const mt = props.form?.max_time_per_turn
  if (mt && mt > 0) {
    if (mt >= 525600 && mt % 525600 === 0) return 'Years'
    if (mt >= 10080 && mt % 10080 === 0) return 'Weeks'
    if (mt >= 1440 && mt % 1440 === 0) return 'Days'
    if (mt >= 60 && mt % 60 === 0) return 'Hours'
    return 'Minutes'
  }
  return 'Minutes'
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
  const val = parseInt(target.value) || 1
  emit('update:calendar-pacing-value', val)
  const unit = getCalendarPacingUnit()
  const factor = CALENDAR_UNIT_FACTORS[unit] || 1
  emit('update:pacing', val * factor)
}

function handleCalendarPacingUnitChange(event: Event) {
  const target = event.target as HTMLSelectElement
  const unit = target.value
  emit('update:calendar-pacing-unit', unit)
  const val = getCalendarPacingValue()
  const factor = CALENDAR_UNIT_FACTORS[unit] || 1
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
  const val = parseInt(raw)
  if (isNaN(val) || val <= 0) {
    emit('update:calendar-max-value', null)
    emit('update:max-time-per-turn', null)
    return
  }
  emit('update:calendar-max-value', val)
  const unit = getCalendarMaxUnit()
  const factor = CALENDAR_UNIT_FACTORS[unit] || 1
  emit('update:max-time-per-turn', val * factor)
}

function handleCalendarMaxUnitChange(event: Event) {
  const target = event.target as HTMLSelectElement
  const unit = target.value
  emit('update:calendar-max-unit', unit)
  const raw = getCalendarMaxValue()
  if (raw) {
    const val = parseInt(raw)
    const factor = CALENDAR_UNIT_FACTORS[unit] || 1
    emit('update:max-time-per-turn', val * factor)
  }
}

function handleUnitsPacingChange(event: Event) {
  const target = event.target as HTMLInputElement
  const val = parseFloat(target.value)
  emit('update:pacing', isNaN(val) || val <= 0 ? 1 : val)
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

function handleStartDateInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:start-date', target.value || '2026-01-01')
}

function handleStartTimeInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:start-time', target.value || '08:00')
}

function handleDayLabelInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:day-label', target.value || 'Day')
}

function handleUnitNameInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:unit-name', target.value || 'Blobs')
}

function handleInitialValueInput(event: Event) {
  const target = event.target as HTMLInputElement
  const val = parseFloat(target.value)
  emit('update:initial-value', isNaN(val) ? 0 : val)
}

const clockConfigChanged = computed(() => {
  const advClock = !!props.adventure?.clock_enabled
  const advTimeConfig = props.adventure?.time_config || {}
  const formTimeConfig = props.form?.time_config || {}
  const advTimeSystem = props.adventure?.time_system || 'calendar'
  const formTimeSystem = props.form?.time_system || 'calendar'
  const advPacing = props.adventure?.time_per_turn ?? 5
  const formPacing = props.form?.time_per_turn ?? 5
  const advMaxTime = props.adventure?.max_time_per_turn ?? null
  const formMaxTime = props.form?.max_time_per_turn ?? null

  return (
    !!props.form?.clock_enabled !== advClock
    || formTimeSystem !== advTimeSystem
    || formPacing !== advPacing
    || formMaxTime !== advMaxTime
    || (formTimeConfig.start_date || '2026-01-01') !== (advTimeConfig.start_date || '2026-01-01')
    || (formTimeConfig.start_time || '08:00') !== (advTimeConfig.start_time || '08:00')
    || (formTimeConfig.day_label || 'Day') !== (advTimeConfig.day_label || 'Day')
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
  emit('update:time-system', props.adventure?.time_system || 'calendar')
  emit('update:pacing', props.adventure?.time_per_turn ?? 5)
  emit('update:max-time-per-turn', props.adventure?.max_time_per_turn ?? null)
  emit('update:start-date', advTimeConfig.start_date || '2026-01-01')
  emit('update:start-time', advTimeConfig.start_time || '08:00')
  emit('update:day-label', advTimeConfig.day_label || 'Day')
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
  const isUnits = (props.form?.time_system || 'calendar') === 'units'
  const timeConfig = props.form?.time_config || {}
  if (isUnits) {
    const unitName = timeConfig.unit_name || 'Blobs'
    const initialVal = Number(timeConfig.initial_value ?? 0)
    return {
      dateShort: unitName,
      time: String(initialVal),
      isUnits: true,
    }
  }
  const dateStr = timeConfig.start_date || '2026-01-01'
  const timeStr = timeConfig.start_time || '08:00'
  try {
    const dt = new Date(`${dateStr}T${timeStr}`)
    if (!isNaN(dt.getTime())) {
      const d = dt.getDate().toString().padStart(2, '0')
      const m = (dt.getMonth() + 1).toString().padStart(2, '0')
      const y = dt.getFullYear()
      return {
        dateShort: `${d}.${m}.${y}`,
        time: timeStr,
        isUnits: false,
      }
    }
  } catch (e) {}
  return {
    dateShort: timeConfig.day_label || 'Day 1',
    time: timeStr,
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

    <!-- Unified In-Game Zeitsystem & Pacing Panel -->
    <div class="bg-slate-900/40 p-6 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl space-y-6">
      <div class="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 border-b border-white/5 pb-4">
        <div>
          <label class="block text-xs font-black text-slate-400 uppercase tracking-[0.2em]">In-Game Zeitsystem & Pacing</label>
          <p class="text-xs text-slate-500 mt-0.5">Konfiguriere Kalender-Modus oder benutzerdefinierte Zeiteinheiten, Runden-Pacing und GM-Zeitlimits.</p>
        </div>
        <div class="flex items-center gap-3 self-end sm:self-auto">
          <div v-if="clockConfigChanged" class="flex items-center gap-2 animate-fade-in mr-2">
            <button
              @click="emit('save-changes')"
              :disabled="isSaving"
              class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg disabled:opacity-50 flex items-center justify-center"
              title="Speichern"
            >
              <i v-if="isSaving" class="ra ra-cycle animate-spin text-sm"></i>
              <Save v-else class="w-4 h-4" />
            </button>
            <button
              @click="discardClockConfig"
              :disabled="isSaving"
              class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-xl transition-all flex items-center justify-center"
              title="Abbrechen"
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
            {{ form.clock_enabled ? 'Aktiviert' : 'Deaktiviert' }}
          </span>
        </div>
      </div>

      <div v-if="form.clock_enabled" class="space-y-6 animate-fade-in">
        <!-- System Switcher -->
        <div class="space-y-2">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Zeitsystem Typ</label>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-xl">
            <button
              @click="emit('update:time-system', 'calendar')"
              class="flex items-center gap-3 p-3.5 rounded-2xl text-xs font-black uppercase tracking-widest transition-all border text-left"
              :class="(form.time_system || 'calendar') === 'calendar' ? 'bg-emerald-600/30 border-emerald-500 text-white shadow-lg ring-1 ring-emerald-500/50' : 'bg-black/40 border-white/10 text-slate-400 hover:text-white hover:border-white/20'"
            >
              <div class="p-2 rounded-xl bg-emerald-500/20 text-emerald-400">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <div class="font-black text-sm">📅 Kalender & Uhrzeit</div>
                <div class="text-[10px] text-slate-400 font-normal mt-0.5">Datum, Uhrzeit & flexible Runden-Zeiteinheiten</div>
              </div>
            </button>

            <button
              @click="emit('update:time-system', 'units')"
              class="flex items-center gap-3 p-3.5 rounded-2xl text-xs font-black uppercase tracking-widest transition-all border text-left"
              :class="(form.time_system || 'calendar') === 'units' ? 'bg-cyan-600/30 border-cyan-500 text-white shadow-lg ring-1 ring-cyan-500/50' : 'bg-black/40 border-white/10 text-slate-400 hover:text-white hover:border-white/20'"
            >
              <div class="p-2 rounded-xl bg-cyan-500/20 text-cyan-400">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0zM13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div>
                <div class="font-black text-sm">⏳ Zeiteinheiten</div>
                <div class="text-[10px] text-slate-400 font-normal mt-0.5">z. B. Days, Lightyears, Blobs, Zyklen</div>
              </div>
            </button>
          </div>
        </div>

        <!-- Mode 1: Kalender Konfiguration -->
        <div v-if="(form.time_system || 'calendar') !== 'units'" class="space-y-6">
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6 bg-black/30 p-5 rounded-2xl border border-white/5">
            <div class="space-y-2">
              <label class="block text-xs font-black text-slate-400 uppercase tracking-[0.2em]">Start-Datum</label>
              <input
                type="date"
                :value="form.time_config?.start_date || '2026-01-01'"
                @input="handleStartDateInput"
                class="w-full bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all"
              />
              <p class="text-[10px] text-slate-500">Tag 1 startet an diesem In-Game-Datum.</p>
            </div>

            <div class="space-y-2">
              <label class="block text-xs font-black text-slate-400 uppercase tracking-[0.2em]">Start-Uhrzeit</label>
              <input
                type="time"
                :value="form.time_config?.start_time || '08:00'"
                @input="handleStartTimeInput"
                class="w-full bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all"
              />
              <p class="text-[10px] text-slate-500">Uhrzeit zu Beginn des Abenteuers.</p>
            </div>

            <div class="space-y-2">
              <label class="block text-xs font-black text-slate-400 uppercase tracking-[0.2em]">Tages-Bezeichnung (Optional)</label>
              <input
                :value="form.time_config?.day_label || 'Day'"
                @input="handleDayLabelInput"
                type="text"
                maxlength="20"
                placeholder="z. B. Tag, Day, Sol"
                class="w-full bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all"
              />
              <p class="text-[10px] text-slate-500">Wird für relative Datumsanzeigen verwendet.</p>
            </div>
          </div>

          <!-- Calendar Pacing & GM Max Limit -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6 bg-black/30 p-5 rounded-2xl border border-white/5">
            <!-- Pacing -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-emerald-400 uppercase tracking-[0.2em]">Runden-Pacing (Zeit pro Runde)</label>
              <div class="flex gap-2">
                <input
                  type="number"
                  min="1"
                  :value="getCalendarPacingValue()"
                  @input="handleCalendarPacingValueChange"
                  class="w-1/3 bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all text-center"
                />
                <select
                  :value="getCalendarPacingUnit()"
                  @change="handleCalendarPacingUnitChange"
                  class="w-2/3 bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all cursor-pointer"
                >
                  <option v-for="u in CALENDAR_UNITS" :key="u.value" :value="u.value" class="bg-slate-900 text-white">
                    {{ u.label }}
                  </option>
                </select>
              </div>
              <p class="text-[10px] text-slate-500">In jeder Spielrunde verstreicht dieser Zeitwert standardmäßig.</p>
            </div>

            <!-- Max Time per Turn (GM Limit) -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-slate-400 uppercase tracking-[0.2em]">Max. Zeit pro Runde (GM Limit)</label>
              <div class="flex gap-2">
                <input
                  type="number"
                  min="1"
                  placeholder="Frei (Optional)"
                  :value="getCalendarMaxValue()"
                  @input="handleCalendarMaxValueChange"
                  class="w-1/3 bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all text-center"
                />
                <select
                  :value="getCalendarMaxUnit()"
                  @change="handleCalendarMaxUnitChange"
                  class="w-2/3 bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all cursor-pointer"
                >
                  <option v-for="u in CALENDAR_UNITS" :key="u.value" :value="u.value" class="bg-slate-900 text-white">
                    {{ u.label }}
                  </option>
                </select>
              </div>
              <p class="text-[10px] text-slate-500">Maximales Zeitvergehen in einem Turn bei aufwendigen GM-Aktionen.</p>
            </div>
          </div>
        </div>

        <!-- Mode 2: Zeiteinheiten Konfiguration -->
        <div v-else class="space-y-6">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6 bg-black/30 p-5 rounded-2xl border border-white/5">
            <div class="space-y-2">
              <label class="block text-xs font-black text-cyan-400 uppercase tracking-[0.2em]">Name der Zeiteinheit</label>
              <input
                :value="form.time_config?.unit_name || 'Blobs'"
                @input="handleUnitNameInput"
                type="text"
                maxlength="30"
                placeholder="z. B. Days, Lightyears, Blobs, Zyklen, Stundengläser"
                class="w-full bg-black/60 border border-cyan-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-cyan-500/20 outline-none transition-all"
              />
              <p class="text-[10px] text-slate-500">Freie Bezeichnung der Einheit (z. B. "Lightyears", "Blobs").</p>
            </div>

            <div class="space-y-2">
              <label class="block text-xs font-black text-cyan-400 uppercase tracking-[0.2em]">Startwert</label>
              <input
                :value="form.time_config?.initial_value ?? 0"
                @input="handleInitialValueInput"
                type="number"
                step="any"
                placeholder="0"
                class="w-full bg-black/60 border border-cyan-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-cyan-500/20 outline-none transition-all"
              />
              <p class="text-[10px] text-slate-500">Numerischer Anfangswert beim Spielstart.</p>
            </div>
          </div>

          <!-- Units Pacing & GM Max Limit -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6 bg-black/30 p-5 rounded-2xl border border-white/5">
            <!-- Pacing -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-cyan-400 uppercase tracking-[0.2em]">
                Runden-Pacing ({{ form.time_config?.unit_name || 'Einheiten' }} pro Runde)
              </label>
              <input
                type="number"
                step="any"
                min="0.001"
                :value="form.time_per_turn ?? 1"
                @input="handleUnitsPacingChange"
                placeholder="z. B. 1"
                class="w-full bg-black/60 border border-cyan-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-cyan-500/20 outline-none transition-all"
              />
              <p class="text-[10px] text-slate-500">Standardmäßiges Vergehen von {{ form.time_config?.unit_name || 'Einheiten' }} in jeder Runde.</p>
            </div>

            <!-- Max Units (GM Limit) -->
            <div class="space-y-2">
              <label class="block text-xs font-black text-slate-400 uppercase tracking-[0.2em]">
                Max. {{ form.time_config?.unit_name || 'Einheiten' }} pro Runde (GM Limit)
              </label>
              <input
                type="number"
                step="any"
                min="0.001"
                :value="form.max_time_per_turn ?? ''"
                @input="handleUnitsMaxChange"
                placeholder="z. B. 10 (Optional)"
                class="w-full bg-black/60 border border-cyan-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-cyan-500/20 outline-none transition-all"
              />
              <p class="text-[10px] text-slate-500">Maximales Vergehen von {{ form.time_config?.unit_name || 'Einheiten' }} bei aufwendigen GM-Aktionen.</p>
            </div>
          </div>
        </div>

        <!-- Live Widget Preview -->
        <div class="flex items-center justify-between p-4 rounded-2xl bg-black/40 border border-white/10">
          <div class="space-y-1">
            <span class="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Live Vorschau In-Game Widget</span>
            <p class="text-xs text-slate-500">So wird die Zeitanzeige während des Spiels gerendert:</p>
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
