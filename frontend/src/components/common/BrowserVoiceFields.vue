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
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const narrator = defineModel<string>('narrator', { default: '' })
const characters = defineModel<string[]>('characters', { default: () => [] })

/** `inputClass` is kept for callers that still pass it; the fields use the Workbench inputs. */
defineProps<{
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

const languageOptions = computed(() => [
  { value: ALL_LANGUAGES, label: `All languages (${voices.value.length} voices)` },
  ...languages.value.map((code) => ({ value: code, label: code.toUpperCase() })),
])

const narratorOptions = computed(() => {
  const keepUnknown = narrator.value && !shownVoices.value.some((v) => v.name === narrator.value)
  return [
    { value: '', label: 'Automatic (best voice for the story language)' },
    ...(keepUnknown ? [{ value: narrator.value, label: narrator.value }] : []),
    ...shownVoices.value.map((v) => ({ value: v.name, label: `${v.name} (${v.lang})` })),
  ]
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
    <UiNotice v-if="!supported" tone="warn">
      This browser has no built-in speech. Open the settings in Edge, Chrome or Firefox to choose voices.
    </UiNotice>
    <template v-else>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <UiField id="browser-voice-language" label="Language filter">
          <UiSelect v-model="language" :options="languageOptions" />
        </UiField>
        <UiField id="browser-voice-narrator" label="Narrator voice">
          <div class="flex gap-2">
            <UiSelect
              :model-value="narrator"
              :options="narratorOptions"
              class="min-w-0"
              @update:model-value="(value) => (narrator = String(value ?? ''))"
            />
            <UiIconButton
              :icon="Volume2"
              label="Play a sample with the narrator voice"
              variant="secondary"
              :disabled="!narrator"
              @click="preview(narrator)"
            />
          </div>
        </UiField>
      </div>

      <div class="space-y-2">
        <div class="flex items-baseline justify-between gap-2">
          <p class="wb-label">
            Character voices <span class="wb-hint">({{ characters.length }} chosen; none means automatic)</span>
          </p>
          <UiButton v-if="characters.length" variant="ghost" size="sm" @click="characters = []">Clear</UiButton>
        </div>
        <div class="max-h-64 divide-y divide-wb-line overflow-y-auto rounded-xl border border-wb-line-strong bg-wb-raised">
          <p v-if="shownVoices.length === 0" class="wb-hint p-3">No voices for this language.</p>
          <div v-for="entry in shownVoices" :key="entry.name" class="flex items-center gap-3 px-3 py-2">
            <UiCheckbox
              :model-value="isCharacterVoice(entry.name)"
              :label="entry.name"
              :description="`${entry.lang}${entry.localService ? '' : ' · online'}`"
              class="min-w-0 flex-1"
              @update:model-value="toggleCharacterVoice(entry.name)"
            />
            <UiIconButton
              :icon="Volume2"
              :label="`Play a sample with ${entry.name}`"
              size="sm"
              :class="{ '!text-wb-accent-text': previewing === entry.name }"
              @click="preview(entry.name)"
            />
          </div>
        </div>
      </div>

      <p class="wb-hint">
        Every character keeps one of the chosen voices for the whole session. Players hear these voices only if their browser
        has them (voices differ between browsers and systems); otherwise their browser picks voices for the story language.
        "Online" voices need an internet connection.
      </p>
      <p v-if="missingNames.length" class="wb-hint !text-wb-warn-text">Not available in this browser: {{ missingNames.join(', ') }}</p>
    </template>
  </div>
</template>
