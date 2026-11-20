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
const customOpenaiUrl = ref(llmForm.value.custom_openai_url || '')
const errorMessage = ref('')

const usesOllama = computed((): boolean => story.provider === 'ollama' || fast.provider === 'ollama')
const usesCustomOpenai = computed((): boolean => story.provider === 'custom_openai' || fast.provider === 'custom_openai')

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
  if (llmForm.value.custom_openai_url) {
    customOpenaiUrl.value = llmForm.value.custom_openai_url
  }
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
    return customOpenaiUrl.value
  }
  return ''
}

function runTest(key: string, role: { provider: string; model: string }): void {
  const customUrl = role.provider === 'custom_openai' ? customOpenaiUrl.value : undefined
  testService.testLlm(key, role.model, role.provider, ollamaUrl.value, undefined, customUrl)
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
  if (usesCustomOpenai.value && !customOpenaiUrl.value.trim()) {
    errorMessage.value = 'Please enter the Base URL for your OpenAI-Compatible endpoint.'
    return false
  }
  if (usesOllama.value && !ollamaUrl.value.trim()) {
    errorMessage.value = 'Please enter the Ollama URL.'
    return false
  }
  const generator = generatorRole()
  const secondary = secondaryRoles()
  const customUrl = usesCustomOpenai.value
    ? customOpenaiUrl.value.trim()
    : (llmForm.value.custom_openai_url || '')
  const generatorProvider = generator.generator_model_provider ?? llmForm.value.generator_model_provider
  const playAgentProvider = secondary.play_agent_model_provider ?? llmForm.value.play_agent_model_provider
  const compressionProvider = secondary.compression_model_provider ?? llmForm.value.compression_model_provider

  await settingsService.saveLlmSettings({
    ...llmForm.value,
    ...generator,
    ...secondary,
    small_model: fast.model.trim(),
    small_model_provider: fast.provider,
    complex_model: story.model.trim(),
    complex_model_provider: story.provider,
    preferred_provider: story.provider,
    ollama_url: ollamaUrl.value.trim(),
    custom_openai_url: customUrl,
    small_custom_openai_url: fast.provider === 'custom_openai'
      ? customUrl
      : llmForm.value.small_custom_openai_url,
    complex_custom_openai_url: story.provider === 'custom_openai'
      ? customUrl
      : llmForm.value.complex_custom_openai_url,
    generator_custom_openai_url: generatorProvider === 'custom_openai'
      ? (generator.generator_model_provider ? customUrl : (llmForm.value.generator_custom_openai_url || customUrl))
      : llmForm.value.generator_custom_openai_url,
    play_agent_custom_openai_url: playAgentProvider === 'custom_openai'
      ? (secondary.play_agent_model_provider ? customUrl : (llmForm.value.play_agent_custom_openai_url || customUrl))
      : llmForm.value.play_agent_custom_openai_url,
    compression_custom_openai_url: compressionProvider === 'custom_openai'
      ? (secondary.compression_model_provider ? customUrl : (llmForm.value.compression_custom_openai_url || customUrl))
      : llmForm.value.compression_custom_openai_url,
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

    <div v-if="usesCustomOpenai">
      <label :class="wizardStyles.label" for="wizard-custom-openai-url">OpenAI-Compatible Base URL</label>
      <input
        id="wizard-custom-openai-url"
        v-model="customOpenaiUrl"
        :class="wizardStyles.input"
        placeholder="http://localhost:8080/v1"
      />
      <p :class="[wizardStyles.hint, 'mt-1']">
        Endpoint URL ending in /v1 (e.g. http://localhost:8080/v1 or https://api.openai.com/v1).
      </p>
    </div>

    <p v-if="errorMessage" :class="wizardStyles.error">{{ errorMessage }}</p>
  </div>
</template>
