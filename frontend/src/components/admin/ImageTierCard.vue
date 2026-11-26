<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ImageIcon } from 'lucide-vue-next'
import ModelCombobox from '@/components/common/ModelCombobox.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiDisclosure from '@/components/ui/UiDisclosure.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiMultiCombobox from '@/components/ui/UiMultiCombobox.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import { CONTROL_INPUT_CLASS } from '@/components/ui/fieldContext'
import TestResultNote from './TestResultNote.vue'

/**
 * One image quality tier of the Images page ("simple" = standard, "advanced" = high fidelity):
 * provider, model, test run and the local diffusion parameters. Edits the page's draft form.
 */
const form = defineModel<Record<string, any>>('form', { required: true })

const props = defineProps<{
  tier: 'simple' | 'advanced'
  availableConstants: any
  configuredKeys: Record<string, { masked: string; is_env: boolean }>
  testResult?: { status: string; message: string; image_url?: string } | null
  lumigenProfiles?: Array<{ id: number | string; name: string }>
  lumigenCategories?: Array<{ id: number | string; name: string }>
}>()

const emit = defineEmits<{ test: [payload: Record<string, unknown>] }>()

const COPY = {
  simple: {
    title: 'Standard quality',
    description: 'Fast rendering for icons, item cards and catalog tiles.',
    stepsPlaceholder: 'Default: 20',
    cfgPlaceholder: 'Default: 7.0',
  },
  advanced: {
    title: 'High fidelity',
    description: 'Best quality for scenes, main character portraits and key moments.',
    stepsPlaceholder: 'Default: 25',
    cfgPlaceholder: 'Default: 3.5',
  },
}

const SD_PRESET = { steps: 4, cfg_scale: 1.0, sampler_name: 'Euler', scheduler: 'Normal' }
const LOCAL_PROVIDERS = ['ollama', 'stable_diffusion', 'comfyui']

const copy = computed(() => COPY[props.tier])
const key = (field: string): string => `${props.tier}_${field}`
const provider = computed(() => form.value[key('model_provider')] as string)
const showParameters = ref(false)

const isProviderConfigured = (providerId: string): boolean =>
  LOCAL_PROVIDERS.includes(providerId) || Boolean(props.configuredKeys?.[providerId])

const providerOptions = computed(() =>
  (props.availableConstants?.image_providers ?? []).map((p: { id: string; name: string }) => ({
    value: p.id,
    label: isProviderConfigured(p.id) ? p.name : `${p.name} (no key)`,
  })),
)

/** Self-hosted endpoints whose discovered model list depends on the configured URL. */
const modelBaseUrl = computed((): string => {
  if (provider.value === 'comfyui') return form.value.comfyui_url || ''
  if (provider.value === 'lumigen') return form.value.lumigen_url || ''
  if (provider.value === 'ollama') return form.value.ollama_url || ''
  if (provider.value === 'stable_diffusion') return form.value.stable_diffusion_url || ''
  return ''
})

function predefinedModels(providerId: string | undefined): string[] {
  if (!providerId) return []
  return props.availableConstants?.predefined_image_models?.[providerId] || []
}

function resolveModelOnProviderChange(currentModel: string, next: string, previous: string | undefined): string {
  const nextPredefined = predefinedModels(next)
  if (nextPredefined.length === 0) return currentModel
  if (!currentModel || predefinedModels(previous).includes(currentModel)) {
    return nextPredefined.includes(currentModel) ? currentModel : nextPredefined[0]
  }
  return currentModel
}

watch(provider, (next, previous) => {
  form.value[key('model')] = resolveModelOnProviderChange(form.value[key('model')], next, previous)
  if (next !== 'stable_diffusion') return
  for (const [field, value] of Object.entries(SD_PRESET)) {
    if (!form.value[key(field)]) form.value[key(field)] = value
  }
})

const lumigenProfileOptions = computed(() => {
  const seen = new Set<string>()
  const opts = [{ value: '', label: 'Default (server)' }]
  for (const p of props.lumigenProfiles || []) {
    if (!seen.has(p.name)) {
      seen.add(p.name)
      opts.push({ value: p.name, label: p.name })
    }
  }
  const current = String(form.value[key('lumigen_profile')] || '').trim()
  if (current && !seen.has(current)) opts.push({ value: current, label: current })
  return opts
})

const lumigenCategoryOptions = computed(() =>
  (props.lumigenCategories || []).map((c) => c.name).filter(Boolean),
)

function runTest(): void {
  emit('test', {
    key: `${props.tier}_v`,
    model: form.value[key('model')],
    provider: provider.value,
    ollama_url: form.value.ollama_url,
    stable_diffusion_url: form.value.stable_diffusion_url,
    steps: form.value[key('steps')],
    cfg_scale: form.value[key('cfg_scale')],
    sampler_name: form.value[key('sampler_name')],
    scheduler: form.value[key('scheduler')],
    comfyui_url: form.value.comfyui_url,
    comfyui_timeout: form.value.comfyui_timeout,
    comfyui_workflow: form.value[key('comfyui_workflow')],
    lumigen_url: form.value.lumigen_url,
    lumigen_timeout: form.value.lumigen_timeout,
    lumigen_profile: form.value[key('lumigen_profile')],
    lumigen_categories: form.value[key('lumigen_categories')],
    min_long_edge: form.value[key('min_long_edge')],
  })
}
</script>

<template>
  <UiCard :title="copy.title" :description="copy.description">
    <template #actions>
      <UiButton
        size="sm"
        :icon="ImageIcon"
        :loading="testResult?.status === 'loading'"
        :disabled="!form[key('model')]"
        @click="runTest"
      >
        Test image
      </UiButton>
    </template>
    <div class="space-y-4">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <UiField label="Provider">
          <UiSelect v-model="form[key('model_provider')]" :options="providerOptions" />
        </UiField>
        <UiField label="Model" :id="`t2i-${tier}-model`">
          <ModelCombobox
            v-model="form[key('model')]"
            :input-id="`t2i-${tier}-model`"
            kind="image"
            :provider="provider"
            :base-url="modelBaseUrl"
            :input-class="`${CONTROL_INPUT_CLASS} wb-mono pr-10`"
          />
        </UiField>
      </div>

      <div v-if="provider === 'lumigen'" class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <UiField label="Profile" hint="Optional Lumigen generation profile.">
          <UiSelect v-model="form[key('lumigen_profile')]" :options="lumigenProfileOptions" />
        </UiField>
        <UiField label="Categories" hint="Select or type categories for generated images.">
          <UiMultiCombobox
            v-model="form[key('lumigen_categories')]"
            :options="lumigenCategoryOptions"
            placeholder="Select categories..."
          />
        </UiField>
      </div>

      <div v-if="testResult" class="space-y-3">
        <TestResultNote :result="testResult" />
        <img
          v-if="testResult.image_url"
          :src="testResult.image_url"
          alt="Test image"
          class="h-48 w-48 rounded-xl border border-wb-line object-cover"
        />
      </div>

      <UiDisclosure v-if="LOCAL_PROVIDERS.includes(provider)" v-model:open="showParameters" label="Local diffusion parameters" hint="steps, CFG, sampler, edge">
        <div class="space-y-4">
          <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
            <UiField label="Steps">
              <UiInput v-model="form[key('steps')]" type="number" min="1" max="150" :placeholder="copy.stepsPlaceholder" />
            </UiField>
            <UiField label="CFG scale">
              <UiInput v-model="form[key('cfg_scale')]" type="number" min="1" max="30" step="0.5" :placeholder="copy.cfgPlaceholder" />
            </UiField>
            <UiField label="Sampler">
              <UiInput v-model="form[key('sampler_name')]" placeholder="e.g. Euler" class="wb-mono" />
            </UiField>
            <UiField label="Scheduler">
              <UiInput v-model="form[key('scheduler')]" placeholder="e.g. Normal" class="wb-mono" />
            </UiField>
          </div>
          <UiField label="Minimum long edge" hint="Pixels, 256–4096." class="sm:max-w-xs">
            <UiInput v-model="form[key('min_long_edge')]" type="number" min="256" max="4096" step="8" placeholder="e.g. 1024" />
          </UiField>
        </div>
      </UiDisclosure>
    </div>
  </UiCard>
</template>
