<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { settingsService } from '@/services/settingsService'
import { testService } from '@/services/testService'
import WizardTestResult from './WizardTestResult.vue'
import ElevenLabsVoiceField from '@/components/common/ElevenLabsVoiceField.vue'
import { TTS_MODELS, needsKey, wizardStyles } from './wizardPresets'

const ttsForm = settingsService.ttsForm
const configuredKeys = computed(() => settingsService.configuredKeys.value)

const PROVIDERS = [
  { id: 'google', name: 'Google Gemini TTS' },
  { id: 'elevenlabs', name: 'ElevenLabs' },
]

const enabled = ref(ttsForm.value.enabled)
const provider = ref(ttsForm.value.provider || 'google')
const model = ref(ttsForm.value.selected_model)
const voice = ref(ttsForm.value.selected_voice)
const elevenLabsVoiceId = ref(ttsForm.value.elevenlabs_voice_id)
const errorMessage = ref('')

const models = computed(() => TTS_MODELS[provider.value] ?? [])
const voices = computed(() => ttsForm.value.voice_catalog)
const providerNeedsKey = computed((): boolean => needsKey(provider.value, configuredKeys.value))

watch(provider, () => {
  if (!models.value.some((entry) => entry.id === model.value)) {
    model.value = models.value[0]?.id ?? ''
  }
})

async function save(): Promise<boolean> {
  errorMessage.value = ''
  if (enabled.value && provider.value === 'elevenlabs' && !elevenLabsVoiceId.value.trim()) {
    errorMessage.value = 'Choose a narrator voice, or turn narration off.'
    return false
  }
  await settingsService.saveTTSSettings({
    ...ttsForm.value,
    enabled: enabled.value,
    provider: provider.value,
    selected_model: model.value,
    selected_voice: voice.value,
    elevenlabs_voice_id: elevenLabsVoiceId.value.trim(),
  })
  if (settingsService.statusMessage.value?.type === 'error') {
    errorMessage.value = settingsService.statusMessage.value.text
    return false
  }
  return true
}

async function saveAndTest(): Promise<void> {
  if (await save()) {
    await testService.testTTS()
  }
}

defineExpose({ save })
</script>

<template>
  <div class="space-y-5">
    <div>
      <h3 class="text-lg font-black text-white mb-2">Voice narration</h3>
      <p :class="wizardStyles.hint">
        Optional: let the Game Master read the story aloud. This uses a cloud TTS provider.
      </p>
    </div>

    <label class="flex items-center gap-3 cursor-pointer select-none">
      <input v-model="enabled" type="checkbox" class="w-4 h-4 accent-emerald-400" />
      <span class="text-sm font-bold text-white">Enable voice narration</span>
    </label>

    <template v-if="enabled">
      <div class="grid sm:grid-cols-2 gap-4">
        <div>
          <label :class="wizardStyles.label" for="wizard-tts-provider">Provider</label>
          <select id="wizard-tts-provider" v-model="provider" :class="wizardStyles.input">
            <option v-for="entry in PROVIDERS" :key="entry.id" :value="entry.id" class="bg-slate-900">
              {{ entry.name }}
            </option>
          </select>
        </div>
        <div>
          <label :class="wizardStyles.label" for="wizard-tts-model">Model</label>
          <select id="wizard-tts-model" v-model="model" :class="wizardStyles.input">
            <option v-for="entry in models" :key="entry.id" :value="entry.id" class="bg-slate-900">
              {{ entry.name }}
            </option>
          </select>
        </div>
      </div>

      <p v-if="providerNeedsKey" class="text-xs text-amber-400">
        No API key for this provider yet. Go back to the API keys page to add it.
      </p>

      <div v-if="provider === 'google'">
        <label :class="wizardStyles.label" for="wizard-tts-voice">Narrator voice</label>
        <select id="wizard-tts-voice" v-model="voice" :class="wizardStyles.input">
          <option v-for="entry in voices" :key="entry.name" :value="entry.name" class="bg-slate-900">
            {{ entry.name }}{{ entry.description ? ` — ${entry.description}` : '' }}
          </option>
        </select>
      </div>
      <div v-else>
        <label :class="wizardStyles.label" for="wizard-tts-eleven">Narrator voice</label>
        <ElevenLabsVoiceField v-model="elevenLabsVoiceId" input-id="wizard-tts-eleven" :input-class="wizardStyles.input" />
      </div>

      <div class="flex flex-wrap items-center gap-4">
        <button type="button" :class="wizardStyles.secondaryButton" :disabled="providerNeedsKey" @click="saveAndTest">
          Save &amp; play sample
        </button>
        <WizardTestResult test-key="tts" />
      </div>
    </template>

    <p v-if="errorMessage" :class="wizardStyles.error">{{ errorMessage }}</p>
  </div>
</template>
