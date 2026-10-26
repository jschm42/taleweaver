<script setup lang="ts">
/**
 * SessionSettingsModal — Tabbed in-game settings (memory, voice, translation, display).
 *
 * Renders as a bottom sheet on mobile and as a centered dialog on larger screens.
 * All values are edited locally and only applied when the player saves.
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { Sliders, X, BrainCircuit, Volume2, Palette } from 'lucide-vue-next'
import SettingsMemoryTab from './settings/SettingsMemoryTab.vue'
import SettingsVoiceTab from './settings/SettingsVoiceTab.vue'
import SettingsTranslationTab from './settings/SettingsTranslationTab.vue'
import SettingsDisplayTab from './settings/SettingsDisplayTab.vue'
import type { SkinId, SkinPreference } from '@/skins/skinRegistry'
import type { TextDensity } from '@/skins/useTextDensity'
import { DEFAULT_NARRATION_STYLE, isNarrationStyle, type NarrationStyle } from './settings/narrationStyles'
import type { SessionSettingsPayload, SettingsTabId } from './settings/types'

const props = defineProps<{
  initialTurns?: number
  initialNarrationStyle?: string | null
  initialCompression?: boolean
  initialAutoSpeech?: boolean
  initialAutoSpeakNarration?: boolean
  initialAutoSpeakDialogues?: boolean
  initialLanguage?: string
  initialTab?: SettingsTabId
  initialSkin?: SkinPreference
  initialDensity?: TextDensity
  autoSkin?: SkinId
  autoSkinReason?: string
  ttsAvailable?: boolean
  isSaving?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', payload: SessionSettingsPayload): void
}>()

const TABS: { id: SettingsTabId; label: string }[] = [
  { id: 'memory', label: 'Narrator' },
  { id: 'voice', label: 'Voice' },
  { id: 'translation', label: 'Translation' },
  { id: 'display', label: 'Display' },
]

const activeTab = ref<SettingsTabId>(props.initialTab ?? 'memory')
const turns = ref(10)
const narrationStyle = ref<NarrationStyle>(
  isNarrationStyle(props.initialNarrationStyle) ? props.initialNarrationStyle : DEFAULT_NARRATION_STYLE
)
const enableCompression = ref(props.initialCompression ?? true)
const autoSpeech = ref(props.initialAutoSpeech ?? false)
const autoSpeakNarration = ref(props.initialAutoSpeakNarration ?? true)
const autoSpeakDialogues = ref(props.initialAutoSpeakDialogues ?? true)
const language = ref(props.initialLanguage ?? '')
const skin = ref<SkinPreference>(props.initialSkin ?? 'auto')
const density = ref<TextDensity>(props.initialDensity ?? 'comfortable')

if (typeof props.initialTurns === 'number' && props.initialTurns >= 1) {
  turns.value = Math.min(100, Math.max(1, props.initialTurns))
}

function isTabActive(id: SettingsTabId): boolean {
  if (id === 'memory') {
    return narrationStyle.value !== DEFAULT_NARRATION_STYLE
  }
  if (id === 'voice') {
    return !!props.ttsAvailable && autoSpeech.value
  }
  if (id === 'translation') {
    return !!language.value
  }
  if (id === 'display') {
    return skin.value !== 'auto' || density.value !== 'comfortable'
  }
  return false
}

function save() {
  emit('save', {
    turns: turns.value,
    narrationStyle: narrationStyle.value,
    enableCompression: enableCompression.value,
    autoSpeech: autoSpeech.value,
    autoSpeakNarration: autoSpeakNarration.value,
    autoSpeakDialogues: autoSpeakDialogues.value,
    language: language.value,
    skin: skin.value,
    density: density.value,
  })
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    emit('close')
  }
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => window.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <div
    class="fixed inset-0 z-50 flex items-end justify-center bg-black/75 backdrop-blur-sm sm:items-center sm:p-4 animate-fade-in"
    @click.self="emit('close')"
  >
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="session-settings-title"
      class="flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-3xl border border-white/10 bg-slate-900 shadow-2xl sm:max-h-[85vh] sm:max-w-xl sm:rounded-3xl animate-sheet-in"
      @click.stop
    >
      <!-- Mobile grab handle -->
      <div class="flex justify-center pt-2 sm:hidden" aria-hidden="true">
        <span class="h-1 w-10 rounded-full bg-slate-700"></span>
      </div>

      <!-- Header -->
      <div class="flex items-center justify-between gap-3 px-5 pb-3 pt-3 sm:px-6 sm:pt-5">
        <div class="flex min-w-0 items-center gap-3">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-amber-500/40 bg-amber-500/15">
            <Sliders class="h-5 w-5 text-amber-400" />
          </div>
          <div class="min-w-0">
            <h3 id="session-settings-title" class="font-display text-base font-black uppercase tracking-wider text-white sm:text-lg">
              Session Settings
            </h3>
            <p class="truncate text-xs text-slate-400">Applies to this adventure session only.</p>
          </div>
        </div>
        <button
          type="button"
          class="rounded-lg p-2 text-slate-400 transition-colors hover:bg-white/5 hover:text-white cursor-pointer"
          title="Close"
          aria-label="Close settings"
          @click="emit('close')"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <!-- Tabs -->
      <div class="px-5 sm:px-6">
        <div role="tablist" aria-label="Settings sections" class="grid grid-cols-4 gap-1 rounded-2xl border border-white/10 bg-slate-950/60 p-1">
          <button
            v-for="tab in TABS"
            :key="tab.id"
            type="button"
            role="tab"
            :aria-selected="activeTab === tab.id"
            class="relative flex flex-col items-center justify-center gap-1 rounded-xl px-1 py-2 text-[10px] font-black uppercase tracking-wider transition-all cursor-pointer sm:flex-row sm:gap-2 sm:px-2 sm:py-2.5 sm:text-[11px]"
            :class="
              activeTab === tab.id
                ? 'bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20'
                : 'text-slate-400 hover:bg-white/5 hover:text-white'
            "
            @click="activeTab = tab.id"
          >
            <BrainCircuit v-if="tab.id === 'memory'" class="h-4 w-4 shrink-0" />
            <Volume2 v-else-if="tab.id === 'voice'" class="h-4 w-4 shrink-0" />
            <Palette v-else-if="tab.id === 'display'" class="h-4 w-4 shrink-0" />
            <i v-else class="ra ra-fish shrink-0 text-sm"></i>
            <span class="max-w-full truncate">{{ tab.label }}</span>
            <span
              v-if="isTabActive(tab.id)"
              class="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full"
              :class="activeTab === tab.id ? 'bg-slate-950' : 'bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.8)]'"
            ></span>
          </button>
        </div>
      </div>

      <!-- Tab content -->
      <div class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-5 sm:px-6" role="tabpanel">
        <SettingsMemoryTab
          v-if="activeTab === 'memory'"
          v-model:narration-style="narrationStyle"
          v-model:turns="turns"
          v-model:enable-compression="enableCompression"
        />
        <SettingsVoiceTab
          v-else-if="activeTab === 'voice'"
          v-model:auto-speech="autoSpeech"
          v-model:auto-speak-narration="autoSpeakNarration"
          v-model:auto-speak-dialogues="autoSpeakDialogues"
          :tts-available="!!props.ttsAvailable"
        />
        <SettingsTranslationTab v-else-if="activeTab === 'translation'" v-model:language="language" />
        <SettingsDisplayTab
          v-else
          v-model:skin="skin"
          v-model:density="density"
          :auto-skin="props.autoSkin ?? 'classic'"
          :auto-reason="props.autoSkinReason ?? 'no tone set, using the default look'"
        />
      </div>

      <!-- Footer -->
      <div class="flex gap-3 border-t border-white/10 bg-slate-950/40 px-5 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:justify-end sm:px-6">
        <button
          type="button"
          class="flex-1 rounded-xl border border-white/15 px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-slate-300 transition-colors hover:bg-white/5 sm:flex-none cursor-pointer"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          type="button"
          class="flex flex-1 items-center justify-center gap-2 rounded-xl bg-amber-500 px-5 py-2.5 text-xs font-black uppercase tracking-widest text-slate-950 shadow-lg shadow-amber-500/20 transition-colors hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50 sm:flex-none cursor-pointer"
          :disabled="props.isSaving"
          @click="save"
        >
          <span v-if="props.isSaving" class="h-4 w-4 animate-spin rounded-full border-2 border-slate-950/30 border-t-slate-950"></span>
          {{ props.isSaving ? 'Saving...' : 'Save Settings' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.2s ease-out forwards;
}
.animate-sheet-in {
  animation: sheetIn 0.28s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes sheetIn {
  from { opacity: 0; transform: translateY(24px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
