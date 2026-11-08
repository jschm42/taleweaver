<script setup lang="ts">
/**
 * OpenAICompatibleTtsFields — Settings for any speech server with the OpenAI speech API
 * (POST {base}/audio/speech): local servers such as Kokoro-FastAPI, Speaches or LocalAI, or
 * hosted ones such as OpenAI and OpenRouter. Models and voices are loaded from the server where
 * it lists them; any id can be typed in.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '@/composables/useApi'
import type { SpeechVoiceList } from '@/types'

const baseUrl = defineModel<string>('baseUrl', { required: true })
const model = defineModel<string>('model', { required: true })
const voice = defineModel<string>('voice', { required: true })
const format = defineModel<string>('format', { required: true })
const instructions = defineModel<string>('instructions', { required: true })

const props = withDefaults(defineProps<{
  inputClass: string
  idPrefix?: string
  showAdvanced?: boolean
}>(), { idPrefix: 'tts-compat', showAdvanced: true })

const VOICE_SOURCE_TEXT: Record<SpeechVoiceList['source'], string> = {
  server: 'Voices listed by the server.',
  model: 'Voices listed for this model.',
  suggested: 'OpenAI\'s voice names (the server lists none). Any voice id can be typed.',
  none: 'No voice list for this model. Leave empty for the model\'s default voice, or enter a voice id of the provider.',
}

const models = ref<string[]>([])
const voices = ref<string[]>([])
const voiceSource = ref<SpeechVoiceList['source'] | null>(null)
const isLoading = ref(false)
const loadError = ref('')

const ids = computed(() => ({
  url: `${props.idPrefix}-url`,
  model: `${props.idPrefix}-model`,
  modelList: `${props.idPrefix}-model-list`,
  voice: `${props.idPrefix}-voice`,
  voiceList: `${props.idPrefix}-voice-list`,
  format: `${props.idPrefix}-format`,
  instructions: `${props.idPrefix}-instructions`,
}))

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

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
    loadError.value = 'Enter the Base URL first.'
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
    <div class="space-y-2">
      <label :for="ids.url" class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Base URL</label>
      <div class="flex gap-2">
        <input
          :id="ids.url"
          v-model.trim="baseUrl"
          type="url"
          placeholder="http://127.0.0.1:8880/v1"
          :class="[inputClass, 'font-mono flex-1']"
        />
        <button
          type="button"
          :disabled="isLoading"
          class="px-4 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 disabled:opacity-50 cursor-pointer"
          @click="loadFromServer"
        >
          {{ isLoading ? 'Loading…' : 'Load models & voices' }}
        </button>
      </div>
      <p class="text-[11px] text-slate-500">
        Ends in <code class="text-slate-400">/v1</code>. Examples: <code class="text-slate-400">http://127.0.0.1:8880/v1</code> (Kokoro-FastAPI),
        <code class="text-slate-400">https://api.openai.com/v1</code>, <code class="text-slate-400">https://openrouter.ai/api/v1</code>.
        The key is the <strong>OpenAI-Compatible API Key</strong> from Provider Keys (optional; OpenRouter URLs fall back to the OpenRouter key).
      </p>
      <p v-if="loadError" class="text-[11px] text-amber-400">{{ loadError }}</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div class="space-y-2">
        <label :for="ids.model" class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Model</label>
        <input
          :id="ids.model"
          v-model.trim="model"
          type="text"
          :list="ids.modelList"
          autocomplete="off"
          placeholder="e.g. kokoro, tts-1, openai/gpt-4o-mini-tts"
          :class="[inputClass, 'font-mono']"
        />
        <datalist :id="ids.modelList">
          <option v-for="entry in models" :key="entry" :value="entry" />
        </datalist>
        <p v-if="models.length" class="text-[11px] text-slate-500">{{ models.length }} models from the server.</p>
      </div>

      <div class="space-y-2">
        <label :for="ids.voice" class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Narrator Voice <span class="normal-case font-normal text-slate-600">(optional)</span></label>
        <input
          :id="ids.voice"
          v-model.trim="voice"
          type="text"
          :list="ids.voiceList"
          autocomplete="off"
          placeholder="empty = model default; e.g. af_heart, alloy"
          :class="[inputClass, 'font-mono']"
        />
        <datalist :id="ids.voiceList">
          <option v-for="entry in voices" :key="entry" :value="entry" />
        </datalist>
        <p v-if="voiceSource" class="text-[11px] text-slate-500">{{ VOICE_SOURCE_TEXT[voiceSource] }}</p>
      </div>
    </div>

    <div v-if="showAdvanced" class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div class="space-y-2">
        <label :for="ids.format" class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Audio Format</label>
        <select :id="ids.format" v-model="format" :class="[inputClass, '[color-scheme:dark]']">
          <option value="mp3" class="bg-slate-900">MP3</option>
          <option value="wav" class="bg-slate-900">WAV</option>
          <option value="pcm" class="bg-slate-900">PCM (24 kHz, stored as WAV)</option>
        </select>
        <p class="text-[11px] text-slate-500">Some models only return PCM.</p>
      </div>
      <div class="space-y-2 md:col-span-2">
        <label :for="ids.instructions" class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Instructions (optional)</label>
        <textarea
          :id="ids.instructions"
          v-model="instructions"
          rows="2"
          maxlength="2000"
          placeholder="e.g. Calm, warm storyteller voice with dramatic pauses."
          :class="inputClass"
        ></textarea>
        <p class="text-[11px] text-slate-500">Sent only when filled; models without support ignore or reject it.</p>
      </div>
    </div>
  </div>
</template>
