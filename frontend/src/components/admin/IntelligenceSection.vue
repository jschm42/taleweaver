<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Copy, RefreshCw } from 'lucide-vue-next'
import { cloneValue, useDraft } from '@/composables/useDraft'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'
import UiToggle from '@/components/ui/UiToggle.vue'
import LlmPassCard from './LlmPassCard.vue'

const props = defineProps<{
  llmForm: any
  availableConstants: any
  configuredKeys: Record<string, { masked: string; is_env: boolean }>
  isSubmitting: boolean
  isLoadingOllamaModels: boolean
  testResults: Record<string, { status: string; message: string }>
}>()

interface TestPayload {
  key: string
  model: string
  provider: string
  openrouterProvider?: string
  customOpenaiUrl?: string
  customOpenaiResponseFormat?: string
  customOpenaiTimeout?: number
}

const emit = defineEmits<{
  (e: 'save', payload: any): void
  (e: 'test', payload: TestPayload): void
  (e: 'refreshOllamaModels', ollamaUrl?: string): void
  (e: 'switchSection', section: string): void
}>()

const num = (value: unknown, fallback: number): number => (typeof value === 'number' ? value : fallback)
const bool = (value: unknown, fallback: boolean): boolean => (typeof value === 'boolean' ? value : fallback)

const normalizeLocalForm = (data: any) => {
  const sharedTimeout = data?.custom_openai_timeout || 300
  const sharedFormat = data?.custom_openai_response_format || 'prompt'
  return {
    ...data,
    turns_before_compacting: num(data?.turns_before_compacting, 10),
    enable_history_compression: bool(data?.enable_history_compression, true),
    small_max_tokens: num(data?.small_max_tokens, 12288),
    complex_max_tokens: num(data?.complex_max_tokens, 24576),
    generator_max_tokens: num(data?.generator_max_tokens, 32768),
    compression_max_tokens: num(data?.compression_max_tokens, 4096),
    play_agent_allow_walkthrough: bool(data?.play_agent_allow_walkthrough, true),
    play_agent_monkey_mode: bool(data?.play_agent_monkey_mode, false),
    play_agent_personality: data?.play_agent_personality || 'casual',
    play_agent_custom_personality: data?.play_agent_custom_personality || '',
    custom_openai_url: data?.custom_openai_url || '',
    custom_openai_timeout: num(data?.custom_openai_timeout, 300),
    custom_openai_response_format: sharedFormat,
    small_custom_openai_url: data?.small_custom_openai_url || '',
    small_custom_openai_timeout: num(data?.small_custom_openai_timeout, sharedTimeout),
    small_custom_openai_response_format: data?.small_custom_openai_response_format || sharedFormat,
    complex_custom_openai_url: data?.complex_custom_openai_url || '',
    complex_custom_openai_timeout: num(data?.complex_custom_openai_timeout, sharedTimeout),
    generator_custom_openai_url: data?.generator_custom_openai_url || '',
    generator_custom_openai_timeout: num(data?.generator_custom_openai_timeout, sharedTimeout),
    generator_custom_openai_response_format: data?.generator_custom_openai_response_format || sharedFormat,
    play_agent_custom_openai_url: data?.play_agent_custom_openai_url || '',
    play_agent_custom_openai_timeout: num(data?.play_agent_custom_openai_timeout, sharedTimeout),
    compression_custom_openai_url: data?.compression_custom_openai_url || '',
    compression_custom_openai_timeout: num(data?.compression_custom_openai_timeout, sharedTimeout),
  }
}

const { draft: localForm, isDirty, changedCount, reset } = useDraft(() => normalizeLocalForm(props.llmForm))

type TabFilter = 'all' | 'core' | 'world' | 'aux' | 'endpoints'
const activeTab = ref<TabFilter>('all')
const FILTERS: { value: TabFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'core', label: 'Play' },
  { value: 'world', label: 'World-Builder' },
  { value: 'aux', label: 'Play-Agent & memory' },
  { value: 'endpoints', label: 'Local endpoints' },
]
const shows = (tab: TabFilter): boolean => activeTab.value === 'all' || activeTab.value === tab

const PASSES = ['small', 'complex', 'generator', 'play_agent', 'compression']

const PERSONALITIES = [
  { value: 'casual', label: 'Casual – relaxed, curious, plays for fun' },
  { value: 'bureaucrat', label: 'Bureaucrat – formal, protocol-obsessed' },
  { value: 'powerplayer', label: 'Powerplayer – min-maxer, optimal path' },
  { value: 'custom', label: 'Custom – your own directives' },
]

const missingProviders = computed(() => {
  const providers = new Set(PASSES.map((pass) => localForm.value[`${pass}_model_provider`]))
  return [...providers].filter((p) => p && !['ollama', 'custom_openai'].includes(p) && !props.configuredKeys?.[p])
})

const getProviderName = (id: string) => {
  return props.availableConstants?.llm_providers?.find((p: any) => p.id === id)?.name || id
}

const hasOllamaProviderSelected = computed(() => PASSES.some((pass) => localForm.value[`${pass}_model_provider`] === 'ollama'))

const ollamaModelCount = computed(() => {
  const models = props.availableConstants?.predefined_llm_models?.ollama
  return Array.isArray(models) ? models.length : 0
})

watch(hasOllamaProviderSelected, (enabled) => {
  if (enabled) {
    emit('refreshOllamaModels', localForm.value.ollama_url)
  }
}, { immediate: true })

const turnsBeforeCompacting = computed({
  get: () => localForm.value.turns_before_compacting,
  set: (value: number) => {
    if (!Number.isNaN(value)) localForm.value.turns_before_compacting = Math.min(100, Math.max(1, value))
  },
})

// Copy the provider, model and endpoint of pass 1 to all other passes.
const syncFromPass1 = () => {
  const p = localForm.value.small_model_provider
  const m = localForm.value.small_model
  const customUrl = localForm.value.small_custom_openai_url
  for (const pass of PASSES.slice(1)) {
    localForm.value[`${pass}_model_provider`] = p
    localForm.value[`${pass}_model`] = m
    localForm.value[`${pass}_custom_openai_url`] = customUrl
  }
}

function runTest(payload: Record<string, unknown>): void {
  emit('test', payload as unknown as TestPayload)
}
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Intelligence" description="Which AI model runs each part of the game: rules, narration, world creation, Play-Agent and memory.">
      <template #actions>
        <UiButton :icon="Copy" title="Use the provider and model of pass 1 for all other passes" @click="syncFromPass1">
          Copy pass 1 to all
        </UiButton>
      </template>
    </PageHeader>

    <UiNotice v-if="missingProviders.length > 0" tone="warn" title="API key missing">
      Some passes use providers without a key: {{ missingProviders.map(getProviderName).join(', ') }}.
      <template #action>
        <UiButton size="sm" @click="emit('switchSection', 'keys')">Open API keys</UiButton>
      </template>
    </UiNotice>

    <div class="overflow-x-auto">
      <UiSegmented v-model="activeTab" :options="FILTERS" label="Show passes" />
    </div>

    <LlmPassCard
      v-if="shows('core')"
      v-model:form="localForm"
      pass="small"
      title="Pass 1 · Mechanics"
      description="Evaluates the player's action, rolls dice, checks items and returns structured JSON."
      badge="Fast, JSON"
      :available-constants="availableConstants"
      :configured-keys="configuredKeys"
      :test-result="testResults.small"
      show-response-format
      :max-tokens="{ min: 512, max: 65536 }"
      thinking
      @test="runTest"
      @vault="emit('switchSection', 'keys')"
    />

    <LlmPassCard
      v-if="shows('core')"
      v-model:form="localForm"
      pass="complex"
      title="Pass 2 · Narration"
      description="Writes the scene descriptions and dialogue from the resolved mechanics."
      badge="Creative prose"
      :available-constants="availableConstants"
      :configured-keys="configuredKeys"
      :test-result="testResults.complex"
      :max-tokens="{ min: 512, max: 65536 }"
      thinking
      openrouter-placeholder="e.g. Anthropic, Together"
      @test="runTest"
      @vault="emit('switchSection', 'keys')"
    />

    <LlmPassCard
      v-if="shows('world')"
      v-model:form="localForm"
      pass="generator"
      title="Pass 3 · World-Builder"
      description="Generates whole adventures: places, quests, characters and secrets."
      badge="Long context"
      :available-constants="availableConstants"
      :configured-keys="configuredKeys"
      :test-result="testResults.generator"
      show-response-format
      :max-tokens="{ min: 1024, max: 131072 }"
      openrouter-placeholder="e.g. Google, Anthropic"
      @test="runTest"
      @vault="emit('switchSection', 'keys')"
    />

    <LlmPassCard
      v-if="shows('aux')"
      v-model:form="localForm"
      pass="play_agent"
      title="Pass 4 · Play-Agent"
      description="Plays the adventure for the player (Auto-Play) and for automated test runs."
      :available-constants="availableConstants"
      :configured-keys="configuredKeys"
      :test-result="testResults.play_agent"
      openrouter-placeholder="e.g. Together, Grok"
      @test="runTest"
      @vault="emit('switchSection', 'keys')"
    >
      <div class="space-y-4 border-t border-wb-line pt-4">
        <UiField label="Personality">
          <UiSelect v-model="localForm.play_agent_personality" :options="PERSONALITIES" />
        </UiField>
        <UiField
          v-if="localForm.play_agent_personality === 'custom'"
          label="Custom directives"
          hint="Roleplay guidelines and play habits for the Play-Agent."
        >
          <UiTextarea
            v-model="localForm.play_agent_custom_personality"
            :rows="3"
            placeholder="e.g. A paranoid rogue who never trusts chests, checks for traps everywhere and speaks in underworld slang."
          />
        </UiField>
        <UiToggle
          v-model="localForm.play_agent_allow_walkthrough"
          label="Walkthrough by default"
          description="The agent may read the walkthrough of chapters the player unlocked."
        />
        <UiToggle
          v-model="localForm.play_agent_monkey_mode"
          label="Monkey mode by default"
          description="Start in chaos-testing mode (debug only)."
        />
      </div>
    </LlmPassCard>

    <LlmPassCard
      v-if="shows('aux')"
      v-model:form="localForm"
      pass="compression"
      title="Pass 5 · Memory"
      description="Summarizes older story turns so long games keep their context."
      badge="Summaries"
      :available-constants="availableConstants"
      :configured-keys="configuredKeys"
      :test-result="testResults.compression"
      model-placeholder="Empty: uses the pass 1 model"
      @test="runTest"
      @vault="emit('switchSection', 'keys')"
    >
      <template #before>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <UiToggle
            v-model="localForm.enable_history_compression"
            label="Summarize history automatically"
            description="Older turns are replaced by a summary."
          />
          <UiField
            label="Summarize after"
            :hint="`${localForm.turns_before_compacting} ${localForm.turns_before_compacting === 1 ? 'turn' : 'turns'} (1–100, default 10)`"
          >
            <input v-model.number="turnsBeforeCompacting" type="range" min="1" max="100" class="mt-2 h-2 w-full cursor-pointer accent-wb-accent" />
          </UiField>
        </div>
      </template>
    </LlmPassCard>

    <UiCard v-if="shows('endpoints')" title="Ollama" description="Address of a self-hosted Ollama server.">
      <template #actions>
        <UiBadge :tone="ollamaModelCount > 0 ? 'accent' : 'neutral'">{{ ollamaModelCount }} models</UiBadge>
        <UiButton size="sm" :icon="RefreshCw" :loading="isLoadingOllamaModels" @click="emit('refreshOllamaModels', localForm.ollama_url)">
          Detect models
        </UiButton>
      </template>
      <UiField label="API host">
        <UiInput v-model="localForm.ollama_url" placeholder="http://localhost:11434" class="wb-mono" />
      </UiField>
    </UiCard>

    <UiSaveBar
      :dirty="isDirty"
      :count="changedCount"
      :saving="isSubmitting"
      @save="emit('save', cloneValue(localForm))"
      @discard="reset"
    />
  </div>
</template>
