<script setup lang="ts">
import { computed, watch } from 'vue'
import type { ModelKind } from '@/composables/useApi'
import ModelCombobox from '@/components/common/ModelCombobox.vue'
import WizardTestResult from './WizardTestResult.vue'
import { needsKey, wizardStyles } from './wizardPresets'

/** One model role: provider + discovered model (manual entry allowed) + optional connection test. */
const provider = defineModel<string>('provider', { required: true })
const model = defineModel<string>('model', { required: true })

const props = defineProps<{
  id: string
  label: string
  hint?: string
  kind: ModelKind
  providers: { id: string; name: string }[]
  configuredKeys: Record<string, unknown>
  presetFor: (provider: string) => string
  baseUrlFor?: (provider: string) => string
  testKey: string
  testLabel: string
  /** Shows a second button that runs the capability probes of the model's pass. */
  capabilityLabel?: string
}>()

const emit = defineEmits<{ (e: 'test'): void; (e: 'testCapabilities'): void }>()

const providerNeedsKey = computed((): boolean => needsKey(provider.value, props.configuredKeys))
const baseUrl = computed((): string => props.baseUrlFor?.(provider.value) ?? '')

// A user-picked provider gets its recommended model; hydration sets both at once and is not affected.
watch(provider, (next) => {
  model.value = props.presetFor(next)
})
</script>

<template>
  <div class="p-4 rounded-2xl bg-white/[0.02] border border-white/5 space-y-3">
    <div>
      <p class="text-sm font-black text-white">{{ props.label }}</p>
      <p v-if="props.hint" :class="wizardStyles.hint">{{ props.hint }}</p>
    </div>
    <div class="grid sm:grid-cols-2 gap-3">
      <div>
        <label :class="wizardStyles.label" :for="`${props.id}-provider`">Provider</label>
        <select :id="`${props.id}-provider`" v-model="provider" :class="wizardStyles.input">
          <option v-for="entry in props.providers" :key="entry.id" :value="entry.id" class="bg-slate-900">
            {{ entry.name }}{{ needsKey(entry.id, props.configuredKeys) ? ' — no API key' : '' }}
          </option>
        </select>
      </div>
      <div>
        <label :class="wizardStyles.label" :for="`${props.id}-model`">Model</label>
        <ModelCombobox
          v-model="model"
          :input-id="`${props.id}-model`"
          :provider="provider"
          :kind="props.kind"
          :base-url="baseUrl"
          :input-class="`${wizardStyles.input} pr-10 font-mono`"
        />
      </div>
    </div>
    <p v-if="providerNeedsKey" class="text-xs text-amber-400">
      No API key for this provider yet. Go back to the API keys page to add it.
    </p>
    <div class="flex flex-wrap items-center gap-4">
      <button
        type="button"
        :class="wizardStyles.secondaryButton"
        :disabled="!model || providerNeedsKey"
        @click="emit('test')"
      >
        {{ props.testLabel }}
      </button>
      <button
        v-if="props.capabilityLabel"
        type="button"
        :class="wizardStyles.secondaryButton"
        :disabled="!model || providerNeedsKey"
        @click="emit('testCapabilities')"
      >
        {{ props.capabilityLabel }}
      </button>
      <WizardTestResult :test-key="props.testKey" />
    </div>
  </div>
</template>
