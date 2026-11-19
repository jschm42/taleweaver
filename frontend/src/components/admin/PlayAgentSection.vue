<script setup lang="ts">
/**
 * PlayAgentSection — admin page of the Play-Agent (Auto-Play and automated test runs): its
 * model (pass 4) and its default behavior. The values belong to the LLM settings, so the page
 * edits a draft of the same form as the Intelligence page and saves it the same way.
 */
import { computed, watch } from 'vue'
import { cloneValue, useDraft } from '@/composables/useDraft'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'
import UiToggle from '@/components/ui/UiToggle.vue'
import LlmPassCard from './LlmPassCard.vue'
import type { LlmTestPayload } from './useAdminActions'

const props = defineProps<{
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  llmForm: any
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  availableConstants: any
  configuredKeys: Record<string, { masked: string; is_env: boolean }>
  isSubmitting: boolean
  testResults: Record<string, { status: string; message: string }>
}>()

const emit = defineEmits<{
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (e: 'save', payload: any): void
  (e: 'test', payload: LlmTestPayload): void
  (e: 'refreshOllamaModels', ollamaUrl?: string): void
  (e: 'switchSection', section: string): void
}>()

const PERSONALITIES = [
  { value: 'casual', label: 'Casual – relaxed, curious, plays for fun' },
  { value: 'bureaucrat', label: 'Bureaucrat – formal, protocol-obsessed' },
  { value: 'powerplayer', label: 'Powerplayer – min-maxer, optimal path' },
  { value: 'custom', label: 'Custom – your own directives' },
]

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalize(data: any): Record<string, any> {
  return {
    ...data,
    play_agent_allow_walkthrough: typeof data?.play_agent_allow_walkthrough === 'boolean' ? data.play_agent_allow_walkthrough : true,
    play_agent_monkey_mode: typeof data?.play_agent_monkey_mode === 'boolean' ? data.play_agent_monkey_mode : false,
    play_agent_personality: data?.play_agent_personality || 'casual',
    play_agent_custom_personality: data?.play_agent_custom_personality || '',
    play_agent_custom_openai_url: data?.play_agent_custom_openai_url || '',
    play_agent_custom_openai_timeout:
      typeof data?.play_agent_custom_openai_timeout === 'number'
        ? data.play_agent_custom_openai_timeout
        : data?.custom_openai_timeout || 300,
  }
}

const { draft: localForm, isDirty, changedCount, reset } = useDraft(() => normalize(props.llmForm))

const provider = computed<string>(() => localForm.value.play_agent_model_provider || '')
const missingKey = computed(
  () => Boolean(provider.value) && !['ollama', 'custom_openai'].includes(provider.value) && !props.configuredKeys?.[provider.value],
)
const providerName = computed(
  () => props.availableConstants?.llm_providers?.find((p: { id: string }) => p.id === provider.value)?.name || provider.value,
)

watch(
  () => provider.value === 'ollama',
  (isOllama) => {
    if (isOllama) emit('refreshOllamaModels', localForm.value.ollama_url)
  },
  { immediate: true },
)
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Play-Agent" description="The AI player behind Auto-Play and automated test runs: its model and how it plays by default." />

    <UiNotice v-if="missingKey" tone="warn" title="API key missing">
      The Play-Agent uses {{ providerName }}, but no key is stored for it.
      <template #action>
        <UiButton size="sm" @click="emit('switchSection', 'keys')">Open API keys</UiButton>
      </template>
    </UiNotice>

    <LlmPassCard
      v-model:form="localForm"
      pass="play_agent"
      title="Model"
      description="Decides the agent's next action from the story, its notes and the player's instruction."
      :available-constants="availableConstants"
      :configured-keys="configuredKeys"
      :test-result="testResults.play_agent"
      openrouter-placeholder="e.g. Together, Grok"
      @test="(payload) => emit('test', payload as unknown as LlmTestPayload)"
      @vault="emit('switchSection', 'keys')"
    />

    <UiCard title="Behavior" description="Defaults for new Auto-Play runs; players can change them in the Play-Agent panel.">
      <div class="space-y-4">
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
