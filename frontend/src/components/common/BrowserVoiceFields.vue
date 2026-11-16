<script setup lang="ts">
/**
 * BrowserVoiceFields — choose the voices of the "Browser Voice" TTS provider.
 *
 * Lists the voices of this browser (Web Speech API): the narrator voice and the voices
 * characters may use, each with a preview. Stored by name in the TTS settings
 * (`browser_voice`, `browser_character_voices`). Players' browsers use the chosen voices they
 * have; otherwise they pick voices for the story's language themselves.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Volume2 } from 'lucide-vue-next'
import { isBrowserTtsSupported, loadBrowserVoices, previewBrowserVoice } from '@/services/browserTts'

const narrator = defineModel<string>('narrator', { default: '' })
const characters = defineModel<string[]>('characters', { default: () => [] })

const props = defineProps<{
  inputClass?: string
}>()

const ALL_LANGUAGES = ''
const PREVIEW_TEXT = 'The old door creaks open. "Who goes there?" a voice whispers from the dark.'

const supported = isBrowserTtsSupported()
const voices = ref<SpeechSynthesisVoice[]>([])
const language = ref(ALL_LANGUAGES)
const previewing = ref<string | null>(null)

function languageOf(voice: SpeechSynthesisVoice): string {
  return voice.lang.slice(0, 2).toLowerCase()
}

async function refreshVoices(): Promise<void> {
  voices.value = [...(await loadBrowserVoices())].sort((a, b) => a.lang.localeCompare(b.lang) || a.name.localeCompare(b.name))
  if (language.value) return
  const own = navigator.language.slice(0, 2).toLowerCase()
  if (voices.value.some(v => languageOf(v) === own)) language.value = own
}

onMounted(() => {
  if (!supported) return
  void refreshVoices()
  window.speechSynthesis.addEventListener('voiceschanged', refreshVoices)
})
onUnmounted(() => {
  if (supported) window.speechSynthesis.removeEventListener('voiceschanged', refreshVoices)
})

const languages = computed(() => [...new Set(voices.value.map(languageOf))].sort())
const shownVoices = computed(() =>
  language.value ? voices.value.filter(v => languageOf(v) === language.value) : voices.value
)
/** Chosen names this browser does not have (still saved; other browsers may have them). */
const missingNames = computed(() => {
  const known = new Set(voices.value.map(v => v.name))
  return [narrator.value, ...characters.value].filter(name => name && !known.has(name))
})

function isCharacterVoice(name: string): boolean {
  return characters.value.includes(name)
}

function toggleCharacterVoice(name: string): void {
  characters.value = isCharacterVoice(name)
    ? characters.value.filter(entry => entry !== name)
    : [...characters.value, name]
}

async function preview(name: string): Promise<void> {
  previewing.value = name
  try {
    await previewBrowserVoice(name, PREVIEW_TEXT)
  } finally {
    if (previewing.value === name) previewing.value = null
  }
}
</script>

<template>
  <div class="space-y-4">
    <p v-if="!supported" class="text-xs text-amber-400">
      This browser has no built-in speech. Open the settings in Edge, Chrome or Firefox to choose voices.
    </p>
    <template v-else>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="space-y-2">
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider" for="browser-voice-language">
            Language filter
          </label>
          <select id="browser-voice-language" v-model="language" :class="props.inputClass">
            <option :value="ALL_LANGUAGES">All languages ({{ voices.length }} voices)</option>
            <option v-for="code in languages" :key="code" :value="code">{{ code.toUpperCase() }}</option>
          </select>
        </div>
        <div class="space-y-2">
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider" for="browser-voice-narrator">
            Narrator voice
          </label>
          <div class="flex gap-2">
            <select id="browser-voice-narrator" v-model="narrator" :class="[props.inputClass, 'min-w-0']">
              <option value="">Automatic (best voice for the story's language)</option>
              <option v-if="narrator && !shownVoices.some(v => v.name === narrator)" :value="narrator">{{ narrator }}</option>
              <option v-for="voice in shownVoices" :key="voice.name" :value="voice.name">
                {{ voice.name }} ({{ voice.lang }})
              </option>
            </select>
            <button
              type="button"
              class="shrink-0 px-3 rounded-xl border border-blue-500/40 bg-blue-500/10 text-blue-200 text-xs font-bold hover:bg-blue-500/20 disabled:opacity-40"
              :disabled="!narrator"
              title="Play a sample with the narrator voice"
              @click="preview(narrator)"
            >
              <Volume2 class="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <div class="space-y-2">
        <div class="flex items-baseline justify-between gap-2">
          <span class="block text-xs font-bold text-slate-500 uppercase tracking-wider">
            Character voices
            <span class="normal-case font-normal text-slate-400">({{ characters.length }} chosen; none = automatic)</span>
          </span>
          <button
            v-if="characters.length"
            type="button"
            class="text-[11px] text-slate-400 hover:text-white underline"
            @click="characters = []"
          >
            Clear
          </button>
        </div>
        <div class="max-h-64 overflow-y-auto rounded-xl border border-slate-800 bg-slate-900/60 divide-y divide-slate-800">
          <p v-if="shownVoices.length === 0" class="p-3 text-xs text-slate-500">No voices for this language.</p>
          <div v-for="voice in shownVoices" :key="voice.name" class="flex items-center gap-3 px-3 py-2">
            <label class="flex items-center gap-3 flex-1 min-w-0 cursor-pointer">
              <input
                type="checkbox"
                class="accent-blue-500"
                :checked="isCharacterVoice(voice.name)"
                @change="toggleCharacterVoice(voice.name)"
              />
              <span class="text-sm text-white truncate">{{ voice.name }}</span>
              <span class="text-[10px] text-slate-500 shrink-0">{{ voice.lang }}{{ voice.localService ? '' : ' · online' }}</span>
            </label>
            <button
              type="button"
              class="shrink-0 text-xs text-blue-300 hover:text-white"
              :class="{ 'animate-pulse': previewing === voice.name }"
              :title="`Play a sample with ${voice.name}`"
              @click="preview(voice.name)"
            >
              <Volume2 class="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <p class="text-[11px] text-slate-500">
        Every character keeps one of the chosen voices for the whole session. Players hear these voices only if
        their browser has them (voices differ between browsers and systems); otherwise their browser picks voices
        for the story's language itself. "Online" voices need an internet connection.
      </p>
      <p v-if="missingNames.length" class="text-[11px] text-amber-400/80">
        Not available in this browser: {{ missingNames.join(', ') }}
      </p>
    </template>
  </div>
</template>
