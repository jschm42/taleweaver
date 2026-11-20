<script setup lang="ts">
import { computed } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import { cloneValue, useDraft } from '@/composables/useDraft'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import ComfyUISettings from './ComfyUISettings.vue'
import ImageTierCard from './ImageTierCard.vue'

const props = defineProps<{
  t2iForm: any
  availableConstants: any
  configuredKeys: Record<string, { masked: string; is_env: boolean }>
  isSubmitting: boolean
  isLoadingStableDiffusionModels?: boolean
  testResults: Record<string, { status: string; message: string; image_url?: string }>
}>()

const emit = defineEmits<{
  (e: 'save', payload: any): void
  (e: 'test', payload: any): void
  (e: 'refresh-stable-diffusion-models', sdUrl?: string): void
  (e: 'switchSection', section: string): void
}>()

function withDefaults(form: any): any {
  return {
    ...form,
    comfyui_url: form?.comfyui_url ?? 'http://127.0.0.1:8188',
    comfyui_timeout: form?.comfyui_timeout ?? 600,
    simple_comfyui_workflow: form?.simple_comfyui_workflow ?? 'sdxl',
    advanced_comfyui_workflow: form?.advanced_comfyui_workflow ?? 'sdxl',
    scene_model_quality: form?.scene_model_quality ?? 'advanced',
    profile_model_quality: form?.profile_model_quality ?? 'advanced',
    protagonist_model_quality: form?.protagonist_model_quality ?? 'advanced',
    asset_model_quality: form?.asset_model_quality ?? 'simple',
  }
}

const { draft: localForm, isDirty, changedCount, reset } = useDraft(() => withDefaults(props.t2iForm))

const QUALITY_OPTIONS = [
  { value: 'simple', label: 'Standard' },
  { value: 'advanced', label: 'High fidelity' },
]

const CONTENT_TYPES = [
  { field: 'scene_model_quality', label: 'Scenes and world', ratio: '16:9' },
  { field: 'profile_model_quality', label: 'NPC portraits', ratio: '4:5' },
  { field: 'protagonist_model_quality', label: 'Protagonist', ratio: '4:5' },
  { field: 'asset_model_quality', label: 'Items and loot', ratio: '1:1' },
]

const IMAGE_FORMATS = [
  { value: 'webp', label: 'WEBP (default, smallest files)' },
  { value: 'jpeg', label: 'JPEG (widely compatible)' },
  { value: 'png', label: 'PNG (lossless, larger files)' },
]

const LOCAL_PROVIDERS = ['ollama', 'stable_diffusion', 'comfyui']

const missingProviders = computed(() => {
  const providers = new Set([localForm.value.simple_model_provider, localForm.value.advanced_model_provider])
  return [...providers].filter((p) => p && !LOCAL_PROVIDERS.includes(p) && !props.configuredKeys?.[p])
})

const getProviderName = (id: string) => {
  return props.availableConstants?.image_providers?.find((p: any) => p.id === id)?.name || id
}

const usesProvider = (id: string): boolean =>
  localForm.value.simple_model_provider === id || localForm.value.advanced_model_provider === id
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Images" description="Image models and the quality used for scenes, portraits and items." />

    <UiNotice v-if="missingProviders.length > 0" tone="warn" title="API key missing">
      The chosen image providers need a key: {{ missingProviders.map(getProviderName).join(', ') }}.
      <template #action>
        <UiButton size="sm" @click="emit('switchSection', 'keys')">Open API keys</UiButton>
      </template>
    </UiNotice>

    <UiCard title="Quality per content type" description="Which of the two models below renders each kind of image.">
      <ul class="divide-y divide-wb-line">
        <li v-for="type in CONTENT_TYPES" :key="type.field" class="flex flex-wrap items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
          <div>
            <span class="wb-label !text-wb-strong">{{ type.label }}</span>
            <span class="wb-hint ml-2">{{ type.ratio }}</span>
          </div>
          <UiSegmented v-model="localForm[type.field]" :options="QUALITY_OPTIONS" :label="`Quality for ${type.label}`" />
        </li>
      </ul>
    </UiCard>

    <ImageTierCard
      v-model:form="localForm"
      tier="simple"
      :available-constants="availableConstants"
      :configured-keys="configuredKeys"
      :test-result="testResults.simple_v"
      @test="(payload) => emit('test', payload)"
    />

    <ImageTierCard
      v-model:form="localForm"
      tier="advanced"
      :available-constants="availableConstants"
      :configured-keys="configuredKeys"
      :test-result="testResults.advanced_v"
      @test="(payload) => emit('test', payload)"
    />

    <ComfyUISettings
      v-if="usesProvider('comfyui')"
      v-model:url="localForm.comfyui_url"
      v-model:timeout="localForm.comfyui_timeout"
      v-model:simple-workflow="localForm.simple_comfyui_workflow"
      v-model:advanced-workflow="localForm.advanced_comfyui_workflow"
      :simple="localForm.simple_model_provider === 'comfyui'"
      :advanced="localForm.advanced_model_provider === 'comfyui'"
    />

    <UiCard v-if="usesProvider('stable_diffusion')" title="Stable Diffusion WebUI">
      <template #actions>
        <UiButton
          size="sm"
          :icon="RefreshCw"
          :loading="isLoadingStableDiffusionModels"
          @click="emit('refresh-stable-diffusion-models', localForm.stable_diffusion_url)"
        >
          Fetch checkpoints
        </UiButton>
      </template>
      <UiField label="API URL">
        <UiInput v-model="localForm.stable_diffusion_url" placeholder="http://127.0.0.1:7860" class="wb-mono" />
      </UiField>
    </UiCard>

    <UiCard title="Storage" description="How generated images are encoded on disk.">
      <div class="grid grid-cols-1 gap-6 md:grid-cols-2">
        <UiField label="File format" hint="WEBP gives the smallest files at the same visual quality.">
          <UiSelect v-model="localForm.image_format" :options="IMAGE_FORMATS" />
        </UiField>
        <UiField
          v-if="localForm.image_format !== 'png'"
          label="Image quality"
          :hint="`${localForm.image_quality}% · 50 compact, 85 balanced, 100 maximum`"
        >
          <input
            v-model.number="localForm.image_quality"
            type="range"
            min="10"
            max="100"
            step="5"
            class="mt-2 h-2 w-full cursor-pointer accent-wb-accent"
          />
        </UiField>
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
