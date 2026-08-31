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
  (e: 'update:clock-enabled', val: boolean): void
  (e: 'update:time-system', val: 'calendar' | 'relative'): void
  (e: 'update:start-time', val: string): void
  (e: 'update:day-label', val: string): void
}>()

function buildVisualImageUrl(imagePath?: string | null) {
  if (!imagePath) return ''
  return imagePath
}

function getCoverNarrativeContext() {
  if (!props.debugData) return ''
  return props.debugData.adventure?.plot || props.debugData.adventure?.original_prompt || ''
}

function handlePacingInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:pacing', parseInt(target.value))
}

function handleStartTimeInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:start-time', target.value || '08:00')
}

function handleDayLabelInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:day-label', target.value || 'Day')
}

const clockConfigChanged = computed(() => {
  const advClock = !!props.adventure?.clock_enabled
  const advTimeConfig = props.adventure?.time_config || {}
  const formTimeConfig = props.form?.time_config || {}
  const advTimeSystem = props.adventure?.time_system || 'calendar'
  const formTimeSystem = props.form?.time_system || 'calendar'
  return (
    !!props.form?.clock_enabled !== advClock
    || (formTimeSystem !== advTimeSystem)
    || (formTimeConfig.start_time || '08:00') !== (advTimeConfig.start_time || '08:00')
    || (formTimeConfig.day_label || 'Day') !== (advTimeConfig.day_label || 'Day')
  )
})

function discardClockConfig() {
  const advTimeConfig = props.adventure?.time_config || {}
  emit('update:clock-enabled', !!props.adventure?.clock_enabled)
  emit('update:time-system', (props.adventure?.time_system === 'relative' ? 'relative' : 'calendar'))
  emit('update:start-time', advTimeConfig.start_time || '08:00')
  emit('update:day-label', advTimeConfig.day_label || 'Day')
}

const URL_PATTERN = /^(https?:\/\/)[^\s/$.?#].[^\s]*$/i

const licenseUrlInvalid = computed(() => {
  if (props.editingField !== 'license_url') return false
  if (!props.tempValue.trim()) return false
  return !URL_PATTERN.test(props.tempValue.trim())
})
</script>

<template>
  <div class="space-y-8 animate-page-in">
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

      <div class="space-y-2">
        <div class="flex justify-between items-center">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">In-Game Pacing ({{ form.time_per_turn }}m)</label>
          <div v-if="form.time_per_turn !== adventure?.time_per_turn" class="flex gap-2 animate-fade-in">
            <button @click="emit('update:pacing', adventure.time_per_turn)" class="text-xs font-bold text-slate-500 hover:text-white uppercase transition-colors">Discard</button>
            <button @click="emit('save-changes')" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase transition-colors">Save</button>
          </div>
        </div>
        <input :value="form.time_per_turn" @input="handlePacingInput" type="range" min="1" max="60" class="w-full accent-emerald-500 h-2 bg-black/40 rounded-lg appearance-none cursor-pointer mt-3" />
      </div>
    </div>

    <!-- In-Game Clock & Time -->
    <div class="bg-slate-900/40 p-6 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
      <div class="flex justify-between items-center mb-6">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">In-Game Clock</label>
        <div class="flex items-center gap-3">
          <div v-if="clockConfigChanged" class="flex gap-2 animate-fade-in mr-2">
            <button @click="discardClockConfig" class="text-xs font-bold text-slate-500 hover:text-white uppercase transition-colors">Discard</button>
            <button @click="emit('save-changes')" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase transition-colors">Save</button>
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

      <div v-if="form.clock_enabled" class="grid grid-cols-1 md:grid-cols-3 gap-6 animate-fade-in">
        <div class="space-y-2">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Start Time</label>
          <input
            type="time"
            :value="form.time_config?.start_time || '08:00'"
            @input="handleStartTimeInput"
            class="w-full bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all"
          />
          <p class="text-[10px] text-slate-600 uppercase tracking-widest">The in-game clock starts at this time on day 1.</p>
        </div>

        <div class="space-y-2">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Time System</label>
          <div class="grid grid-cols-2 gap-2">
            <button
              @click="emit('update:time-system', 'calendar')"
              class="px-3 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all border"
              :class="(form.time_system || 'calendar') === 'calendar' ? 'bg-emerald-600/80 border-emerald-500 text-white' : 'bg-black/40 border-white/10 text-slate-400 hover:text-white'"
            >
              Calendar
            </button>
            <button
              @click="emit('update:time-system', 'relative')"
              class="px-3 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all border"
              :class="(form.time_system || 'calendar') === 'relative' ? 'bg-emerald-600/80 border-emerald-500 text-white' : 'bg-black/40 border-white/10 text-slate-400 hover:text-white'"
            >
              Relative
            </button>
          </div>
        </div>

        <div class="space-y-2">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Day Label</label>
          <input
            :value="form.time_config?.day_label || 'Day'"
            @input="handleDayLabelInput"
            type="text"
            maxlength="20"
            placeholder="Day"
            class="w-full bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all"
          />
          <p class="text-[10px] text-slate-600 uppercase tracking-widest">Name of a day, e.g. "Day" or "Sol".</p>
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
