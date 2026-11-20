<script setup lang="ts">
/**
 * OpenAICompatibleTtsFields — Settings for any speech server with the OpenAI speech API
 * (POST {base}/audio/speech): local servers such as Kokoro-FastAPI, Speaches or LocalAI, or
 * hosted ones such as OpenAI and OpenRouter. Models and voices are loaded from the server where
 * it lists them; any id can be typed in.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Download } from 'lucide-vue-next'
import { api } from '@/composables/useApi'
import type { SpeechVoiceList } from '@/types'
import UiButton from '@/components/ui/UiButton.vue'
import UiCombobox from '@/components/ui/UiCombobox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const baseUrl = defineModel<string>('baseUrl', { required: true })
const model = defineModel<string>('model', { required: true })
const voice = defineModel<string>('voice', { required: true })
const format = defineModel<string>('format', { required: true })
const instructions = defineModel<string>('instructions', { required: true })

const props = withDefaults(defineProps<{
  /** Kept for callers that still pass it; the fields use the Workbench inputs. */
  inputClass?: string
  idPrefix?: string
  showAdvanced?: boolean
}>(), { inputClass: '', idPrefix: 'tts-compat', showAdvanced: true })

const VOICE_SOURCE_TEXT: Record<SpeechVoiceList['source'], string> = {
  server: 'Voices listed by the server.',
  model: 'Voices listed for this model.',
  suggested: 'OpenAI\'s voice names (the server lists none). Any voice id can be typed.',
  none: 'No voice list for this model. Leave empty for the model\'s default voice, or enter a voice id of the provider.',
}

const FORMATS = [
  { value: 'mp3', label: 'MP3' },
  { value: 'wav', label: 'WAV' },
  { value: 'pcm', label: 'PCM (24 kHz, stored as WAV)' },
]

const models = ref<string[]>([])
const voices = ref<string[]>([])
const voiceSource = ref<SpeechVoiceList['source'] | null>(null)
const isLoading = ref(false)
const loadError = ref('')

const ids = computed(() => ({
  url: `${props.idPrefix}-url`,
  model: `${props.idPrefix}-model`,
  voice: `${props.idPrefix}-voice`,
  format: `${props.idPrefix}-format`,
  instructions: `${props.idPrefix}-instructions`,
}))

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

const trimmed = (value: string | number | null): string => String(value ?? '').trim()

async function loadVoices(): Promise<void> {
  if (!baseUrl.value.trim()) return
  try {
    const result = await api.getSpeechVoices(baseUrl.value.trim(), model.value.trim())
    voices.value = result.voices
    voiceSource.value = result.source
  } catch (error) {
    voices.value = []
    voiceSource.value = null
    loadError.value = errorText(error, 'Could not load voices.')
  }
}

async function loadFromServer(): Promise<void> {
  if (!baseUrl.value.trim()) {
    loadError.value = 'Enter the base URL first.'
    return
  }
  isLoading.value = true
  loadError.value = ''
  try {
    models.value = (await api.getSpeechModels(baseUrl.value.trim())).models
  } catch (error) {
    models.value = []
    loadError.value = errorText(error, 'Could not load models; enter the model id manually.')
  }
  await loadVoices()
  isLoading.value = false
}

const VOICE_RELOAD_DEBOUNCE_MS = 600
let voiceTimer: ReturnType<typeof setTimeout> | undefined

watch(model, (next, previous) => {
  if (next.trim() === previous.trim()) return
  clearTimeout(voiceTimer)
  voiceTimer = setTimeout(() => void loadVoices(), VOICE_RELOAD_DEBOUNCE_MS)
})

onMounted(() => {
  if (baseUrl.value.trim()) void loadFromServer()
})

onBeforeUnmount(() => clearTimeout(voiceTimer))
</script>

<template>
  <div class="space-y-4">
    <UiField :id="ids.url" label="Base URL" :error="loadError || null">
      <div class="flex flex-col gap-2 sm:flex-row">
        <UiInput
          :model-value="baseUrl"
          type="url"
          placeholder="http://127.0.0.1:8880/v1"
          class="wb-mono"
          @update:model-value="(value) => (baseUrl = trimmed(value))"
        />
        <UiButton :icon="Download" :loading="isLoading" class="shrink-0" @click="loadFromServer">Load models and voices</UiButton>
      </div>
    </UiField>
    <p class="wb-hint">
      Ends in <code class="wb-mono">/v1</code>, e.g. <code class="wb-mono">http://127.0.0.1:8880/v1</code> (Kokoro-FastAPI),
      <code class="wb-mono">https://api.openai.com/v1</code> or <code class="wb-mono">https://openrouter.ai/api/v1</code>.
      The key is the optional OpenAI-compatible speech key under API keys (separate from the LLM key; OpenRouter URLs fall
      back to the OpenRouter key).
    </p>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <UiField :id="ids.model" label="Model" :hint="models.length ? `${models.length} models from the server.` : ''">
        <UiCombobox
          :model-value="model"
          :options="models"
          mono
          toggle-label="Show all models"
          placeholder="e.g. kokoro, tts-1, openai/gpt-4o-mini-tts"
          @update:model-value="(value) => (model = trimmed(value))"
        />
      </UiField>

      <UiField
        :id="ids.voice"
        label="Narrator voice"
        :hint="voiceSource ? VOICE_SOURCE_TEXT[voiceSource] : 'Optional; empty uses the model default.'"
      >
        <UiCombobox
          :model-value="voice"
          :options="voices"
          mono
          toggle-label="Show all voices"
          placeholder="e.g. af_heart, alloy"
          @update:model-value="(value) => (voice = trimmed(value))"
        />
      </UiField>
    </div>

    <div v-if="showAdvanced" class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <UiField :id="ids.format" label="Audio format" hint="Some models only return PCM.">
        <UiSelect v-model="format" :options="FORMATS" />
      </UiField>
      <UiField
        :id="ids.instructions"
        label="Instructions"
        hint="Optional; sent only when filled. Models without support ignore or reject it."
        class="md:col-span-2"
      >
        <UiTextarea v-model="instructions" :rows="2" maxlength="2000" placeholder="e.g. Calm, warm storyteller voice with dramatic pauses." />
      </UiField>
    </div>
  </div>
</template>
