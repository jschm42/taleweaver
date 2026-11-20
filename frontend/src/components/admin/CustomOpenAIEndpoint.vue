<script setup lang="ts">
import { KeyRound, RefreshCw } from 'lucide-vue-next'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

defineProps<{
  passTitle?: string
  url: string
  fallbackUrl?: string
  timeout?: number
  responseFormat?: string
  showResponseFormat?: boolean
  loading: boolean
  modelCount: number
  hasKey: boolean
}>()

const emit = defineEmits<{
  (e: 'update:url', value: string): void
  (e: 'update:timeout', value: number): void
  (e: 'update:responseFormat', value: string): void
  (e: 'detect'): void
  (e: 'vault'): void
}>()

const RESPONSE_FORMATS = [
  { value: 'prompt', label: 'Prompt only (widest compatibility)' },
  { value: 'json_object', label: 'JSON object (server must support it)' },
  { value: 'json_schema', label: 'JSON schema (server must support it)' },
]
</script>

<template>
  <section class="space-y-4 border-t border-wb-line pt-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h4 class="wb-subheading">OpenAI-compatible endpoint{{ passTitle ? ` (${passTitle})` : '' }}</h4>
      <div class="flex items-center gap-2">
        <UiBadge v-if="modelCount > 0">{{ modelCount }} models</UiBadge>
        <UiButton size="sm" :icon="RefreshCw" :loading="loading" :disabled="!(url || fallbackUrl)" @click="emit('detect')">
          Detect models
        </UiButton>
      </div>
    </div>

    <UiField label="Base URL" :hint="!url && fallbackUrl ? `Empty uses the shared URL: ${fallbackUrl}` : ''">
      <UiInput
        :model-value="url"
        type="url"
        :placeholder="fallbackUrl || 'https://your-provider.example/v1'"
        class="wb-mono"
        @update:model-value="(value) => emit('update:url', String(value ?? ''))"
      />
    </UiField>

    <div :class="['grid gap-4', showResponseFormat ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1 sm:max-w-xs']">
      <UiField v-if="showResponseFormat" label="Structured output support">
        <UiSelect
          :model-value="responseFormat || 'prompt'"
          :options="RESPONSE_FORMATS"
          @update:model-value="(value) => emit('update:responseFormat', String(value ?? 'prompt'))"
        />
      </UiField>
      <UiField label="Request timeout" hint="Seconds, 1–3600.">
        <UiInput
          :model-value="timeout ?? 300"
          type="number"
          min="1"
          max="3600"
          @update:model-value="(value) => emit('update:timeout', Number(value) || 300)"
        />
      </UiField>
    </div>

    <UiButton variant="ghost" size="sm" :icon="KeyRound" class="!px-0" @click="emit('vault')">
      {{ hasKey ? 'Manage the API key' : 'Add an optional API key' }}
    </UiButton>
  </section>
</template>
