<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { settingsService } from '@/services/settingsService'
import { testService } from '@/services/testService'
import { configState } from '@/store/config'
import WizardModelPicker from './WizardModelPicker.vue'
import { LLM_PRESETS, needsKey, resolvePreset, wizardStyles, type SetupMode } from './wizardPresets'

const props = defineProps<{ mode: SetupMode }>()

const llmForm = settingsService.llmForm
const constants = settingsService.availableConstants
const configuredKeys = computed(() => settingsService.configuredKeys.value)
const providers = computed(() => constants.value.llm_providers)
const models = computed(() => constants.value.predefined_llm_models)

const story = reactive({ provider: '', model: '' })
const fast = reactive({ provider: '', model: '' })
const ollamaUrl = ref(llmForm.value.ollama_url || 'http://localhost:11434')
const errorMessage = ref('')

const usesOllama = computed((): boolean => story.provider === 'ollama' || fast.provider === 'ollama')

function defaultProvider(): string {
  if (props.mode === 'local') {
    return 'ollama'
  }
  const withKey = providers.value.find((entry) => !needsKey(entry.id, configuredKeys.value))
  return withKey?.id ?? 'openai'
}

function storyPreset(provider: string): string {
  return resolvePreset(LLM_PRESETS, provider, models.value[provider] ?? []).story
}

function fastPreset(provider: string): string {
  return resolvePreset(LLM_PRESETS, provider, models.value[provider] ?? []).fast
}

function hydrate(): void {
  if (configState.hasLlmConfig) {
    Object.assign(story, { provider: llmForm.value.complex_model_provider, model: llmForm.value.complex_model })
    Object.assign(fast, { provider: llmForm.value.small_model_provider, model: llmForm.value.small_model })
    return
  }
  const provider = defaultProvider()
  Object.assign(story, { provider, model: storyPreset(provider) })
  Object.assign(fast, { provider, model: fastPreset(provider) })
}

/** Self-hosted endpoints whose model list depends on the configured URL. */
function baseUrlFor(provider: string): string {
  if (provider === 'ollama') {
    return ollamaUrl.value
  }
  if (provider === 'custom_openai') {
    return llmForm.value.custom_openai_url
  }
  return provider === 'minimax' ? llmForm.value.minimax_url : ''
}

function runTest(key: string, role: { provider: string; model: string }): void {
  testService.testLlm(key, role.model, role.provider, ollamaUrl.value)
}

/** The generator follows the story model unless an admin already picked a different one. */
function generatorRole(): Record<string, string> {
  const form = llmForm.value
  const followsStory = !form.generator_model
    || (form.generator_model === form.complex_model && form.generator_model_provider === form.complex_model_provider)
  if (!followsStory) {
    return {}
  }
  return { generator_model: story.model.trim(), generator_model_provider: story.provider }
}

/** Fills empty secondary roles with the fast model; existing custom choices are left alone. */
function secondaryRoles(): Record<string, string> {
  const roles: Record<string, string> = {}
  if (!llmForm.value.play_agent_model) {
    roles.play_agent_model = fast.model.trim()
    roles.play_agent_model_provider = fast.provider
  }
  if (!llmForm.value.compression_model) {
    roles.compression_model = fast.model.trim()
    roles.compression_model_provider = fast.provider
  }
  return roles
}

async function save(): Promise<boolean> {
  errorMessage.value = ''
  if (!fast.model.trim() || !story.model.trim()) {
    errorMessage.value = 'Choose both models, or skip this page.'
    return false
  }
  await settingsService.saveLlmSettings({
    ...llmForm.value,
    ...generatorRole(),
    ...secondaryRoles(),
    small_model: fast.model.trim(),
    small_model_provider: fast.provider,
    complex_model: story.model.trim(),
    complex_model_provider: story.provider,
    preferred_provider: story.provider,
    ollama_url: ollamaUrl.value,
  })
  if (settingsService.statusMessage.value?.type === 'error') {
    errorMessage.value = settingsService.statusMessage.value.text
    return false
  }
  return true
}

hydrate()

defineExpose({ save })
</script>

<template>
  <div class="space-y-5">
    <div>
      <h3 class="text-lg font-black text-white mb-2">Intelligence</h3>
      <p :class="wizardStyles.hint">
        The Game Master uses a strong model for narration and world building, and a cheaper fast model
        for quick checks. They can come from different providers. This is required to play.
      </p>
    </div>

    <WizardModelPicker
      id="wizard-story"
      v-model:provider="story.provider"
      v-model:model="story.model"
      label="Story model"
      hint="Narration, world building, adventure generation."
      kind="llm"
      :providers="providers"
      :configured-keys="configuredKeys"
      :preset-for="storyPreset"
      :base-url-for="baseUrlFor"
      test-key="wizard-llm-story"
      test-label="Test connection"
      @test="runTest('wizard-llm-story', story)"
    />

    <WizardModelPicker
      id="wizard-fast"
      v-model:provider="fast.provider"
      v-model:model="fast.model"
      label="Fast model"
      hint="Command parsing, quick checks, history compression."
      kind="llm"
      :providers="providers"
      :configured-keys="configuredKeys"
      :preset-for="fastPreset"
      :base-url-for="baseUrlFor"
      test-key="wizard-llm-fast"
      test-label="Test connection"
      @test="runTest('wizard-llm-fast', fast)"
    />

    <div v-if="usesOllama">
      <label :class="wizardStyles.label" for="wizard-ollama-url">Ollama URL</label>
      <input id="wizard-ollama-url" v-model="ollamaUrl" :class="wizardStyles.input" />
    </div>

    <p v-if="errorMessage" :class="wizardStyles.error">{{ errorMessage }}</p>
  </div>
</template>
