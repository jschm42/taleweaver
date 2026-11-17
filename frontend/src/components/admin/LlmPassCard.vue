<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { MessageSquare } from 'lucide-vue-next'
import ModelCombobox from '@/components/common/ModelCombobox.vue'
import { getProviderModelsEntry, loadProviderModels, providerModelsKey } from '@/store/providerModels'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiDisclosure from '@/components/ui/UiDisclosure.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiToggle from '@/components/ui/UiToggle.vue'
import { CONTROL_INPUT_CLASS } from '@/components/ui/fieldContext'
import CustomOpenAIEndpoint from './CustomOpenAIEndpoint.vue'
import TestResultNote from './TestResultNote.vue'

export type PassKey = 'small' | 'complex' | 'generator' | 'play_agent' | 'compression'

/**
 * One LLM pass of the Intelligence page: provider, model, OpenAI-compatible endpoint, test and
 * the optional advanced parameters. Edits the page's draft form; extra fields go into the slot.
 */
const form = defineModel<Record<string, any>>('form', { required: true })

const props = withDefaults(
  defineProps<{
    pass: PassKey
    title: string
    description: string
    badge?: string
    availableConstants: any
    configuredKeys: Record<string, { masked: string; is_env: boolean }>
    testResult?: { status: string; message: string } | null
    showResponseFormat?: boolean
    /** Max-token bounds; omit to hide the field. */
    maxTokens?: { min: number; max: number } | null
    thinking?: boolean
    openrouterPlaceholder?: string
    modelPlaceholder?: string
  }>(),
  {
    badge: '',
    testResult: null,
    showResponseFormat: false,
    maxTokens: null,
    thinking: false,
    openrouterPlaceholder: 'e.g. Together, Fireworks',
    modelPlaceholder: undefined,
  },
)

const emit = defineEmits<{
  test: [payload: Record<string, unknown>]
  vault: []
}>()

const LIKELY_THINKING_MODEL_RE =
  /(?:^|\/)(?:o1|o3|o4-mini|qwq|qwen3|deepseek-r1|deepseek-reasoner|glm-(?:4\.[5-9]|5)|minimax-m2|kimi-k2-thinking|claude-(?:haiku|sonnet|opus)-(?:[5-9]|\d{2})|claude-(?:fable|mythos))|[-/](?:thinking|reasoner)(?:$|:|-)/i

const key = (field: string): string => `${props.pass}_${field}`
const provider = computed(() => form.value[key('model_provider')] as string)
const model = computed(() => form.value[key('model')] as string)
const showAdvanced = ref(false)
const hasAdvanced = computed(() => Boolean(props.maxTokens) || props.thinking)

const isProviderConfigured = (providerId: string): boolean =>
  ['ollama', 'custom_openai'].includes(providerId) || Boolean(props.configuredKeys?.[providerId])

const providerOptions = computed(() =>
  (props.availableConstants?.llm_providers ?? []).map((p: { id: string; name: string }) => ({
    value: p.id,
    label: isProviderConfigured(p.id) ? p.name : `${p.name} (no key)`,
  })),
)

/** Base URL for this pass (per-pass override or the shared URL). */
const baseUrl = computed((): string => {
  if (provider.value === 'ollama') return form.value.ollama_url || ''
  if (provider.value === 'custom_openai') return form.value[key('custom_openai_url')] || form.value.custom_openai_url || ''
  return ''
})

const customModelsKey = computed(() => providerModelsKey('custom_openai', 'llm', baseUrl.value))
const isDetecting = computed(() => getProviderModelsEntry(customModelsKey.value)?.status === 'loading')
const detectedCount = computed(
  () =>
    getProviderModelsEntry(customModelsKey.value)?.list?.models?.length ||
    props.availableConstants?.predefined_llm_models?.custom_openai?.length ||
    0,
)

function detectModels(): void {
  if (baseUrl.value) loadProviderModels('custom_openai', 'llm', { baseUrl: baseUrl.value, refresh: true })
}

const likelyThinking = computed(
  () => props.thinking && typeof model.value === 'string' && LIKELY_THINKING_MODEL_RE.test(model.value.trim()),
)

function predefinedModels(providerId: string | undefined): string[] {
  if (!providerId) return []
  return props.availableConstants?.predefined_llm_models?.[providerId] || []
}

watch(provider, (next, previous) => {
  const nextPredefined = predefinedModels(next)
  const current = form.value[key('model')]
  if (nextPredefined.length === 0) return
  if (!current || predefinedModels(previous).includes(current)) {
    form.value[key('model')] = nextPredefined.includes(current) ? current : nextPredefined[0]
  }
})

function runTest(): void {
  emit('test', {
    key: props.pass,
    model: model.value,
    provider: provider.value,
    openrouterProvider: form.value[key('openrouter_provider')],
    customOpenaiUrl: baseUrl.value,
    customOpenaiResponseFormat: form.value[key('custom_openai_response_format')] || form.value.custom_openai_response_format,
    customOpenaiTimeout: form.value[key('custom_openai_timeout')] || form.value.custom_openai_timeout,
  })
}
</script>

<template>
  <UiCard :title="title" :description="description">
    <template #actions>
      <UiBadge v-if="badge">{{ badge }}</UiBadge>
      <UiButton size="sm" :icon="MessageSquare" :loading="testResult?.status === 'loading'" :disabled="!model" @click="runTest">
        Test model
      </UiButton>
    </template>

    <div class="space-y-4">
      <slot name="before" />

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <UiField label="Provider">
          <UiSelect v-model="form[key('model_provider')]" :options="providerOptions" />
        </UiField>
        <UiField label="Model" :id="`llm-${pass}-model`">
          <ModelCombobox
            v-model="form[key('model')]"
            :input-id="`llm-${pass}-model`"
            kind="llm"
            :placeholder="modelPlaceholder"
            :provider="provider"
            :base-url="baseUrl"
            :input-class="`${CONTROL_INPUT_CLASS} wb-mono pr-10`"
          />
        </UiField>
      </div>

      <CustomOpenAIEndpoint
        v-if="provider === 'custom_openai'"
        v-model:url="form[key('custom_openai_url')]"
        v-model:timeout="form[key('custom_openai_timeout')]"
        v-model:response-format="form[key('custom_openai_response_format')]"
        :fallback-url="form.custom_openai_url"
        :show-response-format="showResponseFormat"
        :loading="isDetecting"
        :model-count="detectedCount"
        :has-key="!!configuredKeys?.custom_openai"
        @detect="detectModels"
        @vault="emit('vault')"
      />

      <UiField v-if="provider === 'openrouter' && !hasAdvanced" label="OpenRouter provider routing" hint="Optional.">
        <UiInput v-model="form[key('openrouter_provider')]" :placeholder="openrouterPlaceholder" class="wb-mono" />
      </UiField>

      <TestResultNote :result="testResult" />

      <slot />

      <UiDisclosure v-if="hasAdvanced" v-model:open="showAdvanced" label="Advanced parameters" hint="tokens, thinking, routing">
        <div class="space-y-4">
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <UiField v-if="maxTokens" label="Max generation tokens" :hint="`${maxTokens.min}–${maxTokens.max}.`">
              <UiInput v-model="form[key('max_tokens')]" type="number" :min="maxTokens.min" :max="maxTokens.max" />
            </UiField>
            <UiField v-if="provider === 'openrouter'" label="OpenRouter provider routing" hint="Optional.">
              <UiInput v-model="form[key('openrouter_provider')]" :placeholder="openrouterPlaceholder" class="wb-mono" />
            </UiField>
          </div>
          <template v-if="thinking">
            <UiToggle
              v-model="form[key('enable_thinking')]"
              label="Thinking mode"
              description="Extended internal reasoning for models that support it."
            />
            <UiField v-if="form[key('enable_thinking')]" label="Thinking budget" hint="Tokens, 256–32768." class="sm:max-w-xs">
              <UiInput v-model="form[key('max_thinking_tokens')]" type="number" min="256" max="32768" />
            </UiField>
          </template>
        </div>
      </UiDisclosure>

      <UiNotice v-if="likelyThinking && !form[key('enable_thinking')]" tone="warn">
        <span class="wb-mono">{{ model }}</span> probably thinks before it answers. Turn on thinking mode if responses come back empty.
        <template #action>
          <UiButton size="sm" @click="form[key('enable_thinking')] = true">Turn on</UiButton>
        </template>
      </UiNotice>
    </div>
  </UiCard>
</template>
