<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import { ArrowRight, Volume2 } from 'lucide-vue-next'
import { api } from '@/composables/useApi'
import { cloneValue, useDraft } from '@/composables/useDraft'
import ElevenLabsVoiceField from '@/components/common/ElevenLabsVoiceField.vue'
import OpenAICompatibleTtsFields from '@/components/common/OpenAICompatibleTtsFields.vue'
import BrowserVoiceFields from '@/components/common/BrowserVoiceFields.vue'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiToggle from '@/components/ui/UiToggle.vue'
import { CONTROL_INPUT_CLASS } from '@/components/ui/fieldContext'
import TestResultNote from './TestResultNote.vue'

const props = defineProps<{
  ttsForm: any
  configuredKeys: any
  isSubmitting: boolean
  testResults: any
}>()

const emit = defineEmits<{
  (e: 'save', payload: any): void
  (e: 'test', payload: any): void
  (e: 'switchSection', section: string): void
}>()

const { draft: localForm, isDirty, changedCount, reset } = useDraft(() => props.ttsForm)
const elevenLabsModelsList = ref<Array<{ model_id: string, name: string }>>([])

const PROVIDERS = [
  { value: 'google', label: 'Google Cloud TTS' },
  { value: 'elevenlabs', label: 'ElevenLabs' },
  { value: 'custom_openai', label: 'OpenAI-compatible (local or hosted)' },
  { value: 'browser', label: 'Browser voice (free, local, for testing)' },
]

const VOICE_LIST = [
  'Zephyr', 'Puck', 'Charon', 'Kore', 'Fenrir', 'Leda', 'Orus', 'Aoede', 'Callirrhoe',
  'Autonoe', 'Enceladus', 'Iapetus', 'Umbriel', 'Algieba', 'Despina', 'Erinome',
  'Algenib', 'Rasalgethi', 'Laomedeia', 'Achernar', 'Alnilam', 'Schedar', 'Gacrux',
  'Pulcherrima', 'Achird', 'Zubenelgenubi', 'Vindemiatrix', 'Sadachbia', 'Sadaltager', 'Sulafat'
]

const GEMINI_TTS_MODELS = [
  { id: 'gemini-3.8-flash-tts', name: 'Gemini 3.8 Flash TTS' },
  { id: 'gemini-3.8-flash-lite-tts', name: 'Gemini 3.8 Flash Lite TTS' },
]

async function fetchElevenLabsModels() {
  try {
    const models = await api.getElevenLabsModels()
    if (models && models.length > 0) {
      elevenLabsModelsList.value = models
    }
  } catch (err) {
    console.error('Failed to fetch ElevenLabs models:', err)
  }
}

onMounted(() => {
  if (localForm.value.provider === 'elevenlabs') {
    fetchElevenLabsModels()
  }
})

const vocalTagsSupported = computed(() => {
  if (localForm.value.provider === 'google') return true
  if (localForm.value.provider === 'elevenlabs' && (localForm.value.selected_model === 'eleven_v3' || localForm.value.selected_model.startsWith('eleven_v4'))) return true
  return false
})

const isCompatible = computed((): boolean => localForm.value.provider === 'custom_openai')
// Browser speech runs in each player's browser: no key, no model, no vocal tags.
const isBrowser = computed((): boolean => localForm.value.provider === 'browser')
const hasServerModel = computed((): boolean => !isCompatible.value && !isBrowser.value)

// The OpenAI-compatible and browser providers work without a key, so they never warn.
const isTtsKeyMissing = computed(() => {
  const provider = localForm.value.provider
  if (provider === 'custom_openai' || provider === 'browser') return false
  return !props.configuredKeys[provider]
})

function formatVoiceLabel(voiceName: string): string {
  const entry = localForm.value.voice_catalog.find((voice: any) => voice.name === voiceName)
  if (!entry) return voiceName
  const detailParts = [entry.gender, entry.description].filter(Boolean)
  if (detailParts.length === 0) return voiceName
  return `${voiceName} (${detailParts.join(', ')})`
}

const voiceOptions = computed(() => VOICE_LIST.map((voice) => ({ value: voice, label: formatVoiceLabel(voice) })))
const modelOptions = computed(() =>
  localForm.value.provider === 'google'
    ? GEMINI_TTS_MODELS.map((model) => ({ value: model.id, label: model.name }))
    : elevenLabsModelsList.value.map((model) => ({ value: model.model_id, label: model.name })),
)

watch(() => localForm.value.provider, (newProvider) => {
  if (newProvider === 'elevenlabs') {
    fetchElevenLabsModels()
    if (!localForm.value.selected_model.startsWith('eleven_')) {
      localForm.value.selected_model = 'eleven_v4'
    }
  } else if (newProvider === 'google' && !localForm.value.selected_model.startsWith('gemini-')) {
    localForm.value.selected_model = 'gemini-3.8-flash-tts'
  } else if (newProvider === 'custom_openai' && /^(gemini-|eleven_)/.test(localForm.value.selected_model)) {
    localForm.value.selected_model = ''
  }
})
</script>

<template>
  <div class="space-y-6">
    <PageHeader
      title="Text-to-speech"
      description="Narration with Gemini, ElevenLabs, an OpenAI-compatible speech server (local or hosted) or the free browser voice."
    >
      <template #actions>
        <UiButton
          v-if="localForm.enabled"
          :icon="Volume2"
          :loading="testResults['tts']?.status === 'loading'"
          title="Saves the settings, then plays a test sentence"
          @click="emit('test', cloneValue(localForm))"
        >
          Test speech
        </UiButton>
      </template>
    </PageHeader>

    <UiNotice v-if="isTtsKeyMissing" tone="warn" title="API key missing">
      No key for {{ localForm.provider === 'google' ? 'Google Gemini' : 'ElevenLabs' }}. Add one before turning on speech.
      <template #action>
        <UiButton size="sm" @click="emit('switchSection', 'keys')">Open API keys</UiButton>
      </template>
    </UiNotice>

    <TestResultNote :result="testResults['tts']" />

    <UiCard>
      <UiToggle v-model="localForm.enabled" label="Enable text-to-speech" description="Read the narration and dialogue aloud during play." />
    </UiCard>

    <template v-if="localForm.enabled">
      <UiCard title="Provider and voice">
        <div class="space-y-5">
          <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
            <UiField label="Provider">
              <UiSelect v-model="localForm.provider" :options="PROVIDERS" />
            </UiField>
            <UiField v-if="localForm.provider === 'google'" label="Narrator voice">
              <UiSelect v-model="localForm.selected_voice" :options="voiceOptions" />
            </UiField>
            <UiField
              v-if="localForm.provider === 'elevenlabs'"
              label="Narrator voice"
              hint="Characters get their own voices from the voice list automatically."
            >
              <ElevenLabsVoiceField v-model="localForm.elevenlabs_voice_id" :input-class="CONTROL_INPUT_CLASS" />
            </UiField>
          </div>

          <div v-if="isBrowser" class="space-y-4">
            <UiNotice>
              Each player's browser reads the story with its built-in voices (Web Speech API): free, no key, no server
              load. Quality depends on the browser: Edge has very good "Natural" voices, Chrome Google voices, Firefox the
              system voices. Vocal tags and audio downloads are not available.
            </UiNotice>
            <BrowserVoiceFields
              v-model:narrator="localForm.browser_voice"
              v-model:characters="localForm.browser_character_voices"
              :input-class="CONTROL_INPUT_CLASS"
            />
          </div>

          <div v-if="isCompatible" class="space-y-3">
            <OpenAICompatibleTtsFields
              v-model:base-url="localForm.custom_openai_url"
              v-model:model="localForm.selected_model"
              v-model:voice="localForm.custom_openai_voice"
              v-model:format="localForm.custom_openai_format"
              v-model:instructions="localForm.custom_openai_instructions"
              id-prefix="admin-tts-compat"
              :input-class="CONTROL_INPUT_CLASS"
            />
            <p class="wb-hint">
              Characters speak with the voices set under Character voices (else the narrator voice); vocal tags are removed before synthesis.
            </p>
          </div>

          <UiField v-if="hasServerModel" :label="localForm.provider === 'google' ? 'Gemini model' : 'ElevenLabs model'">
            <UiSelect v-model="localForm.selected_model" :options="modelOptions" class="md:max-w-sm" />
          </UiField>
        </div>
      </UiCard>

      <UiCard title="Playback">
        <div class="space-y-5">
          <UiToggle
            v-if="hasServerModel"
            v-model="localForm.use_vocal_tags"
            :disabled="!vocalTagsSupported"
            label="Vocal tags"
            :description="vocalTagsSupported ? 'Emotional markers such as [shouting] or (whispering).' : 'Not supported by this model.'"
          />
          <UiToggle
            v-if="localForm.provider === 'google' && localForm.selected_model.startsWith('gemini-')"
            v-model="localForm.use_streaming"
            label="Streaming API"
            description="Streams the audio (Server-Sent Events), so playback starts sooner. Off uses one plain request per line."
          />
          <p v-if="localForm.provider === 'elevenlabs'" class="wb-hint">
            ElevenLabs always streams: each line starts while it is still generated, and every character speaks with their own voice.
          </p>
          <UiToggle
            v-model="localForm.auto_speak"
            label="Start speech automatically"
            description="Games start with speech on; players can still turn it off. Off: players turn it on themselves."
          />
          <UiField label="Playback speed" :hint="`${localForm.speech_rate?.toFixed(2)}× (0.5–2.0)`">
            <input
              v-model.number="localForm.speech_rate"
              type="range"
              min="0.5"
              max="2.0"
              step="0.05"
              class="h-2 w-full cursor-pointer accent-wb-accent md:max-w-sm"
            />
          </UiField>
        </div>
      </UiCard>

      <UiCard v-if="!isBrowser" title="Character voices">
        <template #actions>
          <UiButton size="sm" :icon-right="ArrowRight" @click="emit('switchSection', 'voice-map')">Character voices</UiButton>
        </template>
        <p class="wb-body text-wb-muted">
          NPCs and the protagonist get a voice from the voice list. ElevenLabs speaks it directly; for Google TTS and
          OpenAI-compatible servers, assign matching voices on the Character voices page. Unassigned voices use the narrator voice.
        </p>
      </UiCard>
    </template>

    <UiSaveBar
      :dirty="isDirty"
      :count="changedCount"
      :saving="isSubmitting"
      @save="emit('save', cloneValue(localForm))"
      @discard="reset"
    />
  </div>
</template>
