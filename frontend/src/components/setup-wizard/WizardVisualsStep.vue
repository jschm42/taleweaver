<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { settingsService } from '@/services/settingsService'
import { testService } from '@/services/testService'
import { configState } from '@/store/config'
import { setVisualsOptOut, setupWizardState } from '@/store/setupWizard'
import ComfyUISettings from '@/components/admin/ComfyUISettings.vue'
import WizardModelPicker from './WizardModelPicker.vue'
import { IMAGE_PRESETS, needsKey, resolvePreset, wizardStyles, type SetupMode } from './wizardPresets'

const props = defineProps<{ mode: SetupMode }>()

const t2iForm = settingsService.t2iForm
const constants = settingsService.availableConstants
const configuredKeys = computed(() => settingsService.configuredKeys.value)
const providers = computed(() => constants.value.image_providers)
const models = computed(() => constants.value.predefined_image_models)

const noImages = ref(!configState.hasT2iConfig && setupWizardState.visualsOptOut)
const scene = reactive({ provider: '', model: '' })
const asset = reactive({ provider: '', model: '' })
const ollamaUrl = ref(t2iForm.value.ollama_url || 'http://localhost:11434')
const stableDiffusionUrl = ref(t2iForm.value.stable_diffusion_url || 'http://127.0.0.1:7860')
const comfyuiUrl = ref(t2iForm.value.comfyui_url || 'http://127.0.0.1:8188')
const comfyuiTimeout = ref(t2iForm.value.comfyui_timeout || 600)
const simpleWorkflow = ref<'sd15' | 'sdxl'>(t2iForm.value.simple_comfyui_workflow === 'sd15' ? 'sd15' : 'sdxl')
const advancedWorkflow = ref<'sd15' | 'sdxl'>(t2iForm.value.advanced_comfyui_workflow === 'sd15' ? 'sd15' : 'sdxl')
const errorMessage = ref('')

const usesProvider = (id: string): boolean => scene.provider === id || asset.provider === id

function defaultProvider(): string {
  if (props.mode === 'local') {
    return 'stable_diffusion'
  }
  const withKey = providers.value.find((entry) => !needsKey(entry.id, configuredKeys.value))
  return withKey?.id ?? 'openai'
}

function scenePreset(provider: string): string {
  return resolvePreset(IMAGE_PRESETS, provider, models.value[provider] ?? []).story
}

function assetPreset(provider: string): string {
  return resolvePreset(IMAGE_PRESETS, provider, models.value[provider] ?? []).fast
}

function hydrate(): void {
  if (configState.hasT2iConfig) {
    Object.assign(scene, { provider: t2iForm.value.advanced_model_provider, model: t2iForm.value.advanced_model })
    Object.assign(asset, { provider: t2iForm.value.simple_model_provider, model: t2iForm.value.simple_model })
    return
  }
  const provider = defaultProvider()
  Object.assign(scene, { provider, model: scenePreset(provider) })
  Object.assign(asset, { provider, model: assetPreset(provider) })
}

/** Self-hosted endpoints whose model list depends on the configured URL. */
function baseUrlFor(provider: string): string {
  if (provider === 'comfyui') return comfyuiUrl.value
  if (provider === 'ollama') {
    return ollamaUrl.value
  }
  return provider === 'stable_diffusion' ? stableDiffusionUrl.value : ''
}

function runTest(key: string, role: { provider: string; model: string }): void {
  const profile = role === asset ? 'simple' : 'advanced'
  testService.testVision(
    key, role.model, role.provider, ollamaUrl.value, stableDiffusionUrl.value,
    t2iForm.value[`${profile}_steps`], t2iForm.value[`${profile}_cfg_scale`],
    undefined, undefined, t2iForm.value[`${profile}_sampler_name`],
    t2iForm.value[`${profile}_scheduler`], t2iForm.value[`${profile}_min_long_edge`],
    comfyuiUrl.value, comfyuiTimeout.value,
    profile === 'simple' ? simpleWorkflow.value : advancedWorkflow.value,
  )
}

async function save(): Promise<boolean> {
  errorMessage.value = ''
  if (noImages.value) {
    await setVisualsOptOut(true)
    return true
  }
  if (!scene.model.trim() || !asset.model.trim()) {
    errorMessage.value = 'Choose both models, turn images off, or skip this page.'
    return false
  }
  await settingsService.saveT2iSettings({
    ...t2iForm.value,
    simple_model: asset.model.trim(),
    simple_model_provider: asset.provider,
    advanced_model: scene.model.trim(),
    advanced_model_provider: scene.provider,
    provider: scene.provider,
    ollama_url: ollamaUrl.value,
    stable_diffusion_url: stableDiffusionUrl.value,
    comfyui_url: comfyuiUrl.value,
    comfyui_timeout: comfyuiTimeout.value,
    simple_comfyui_workflow: simpleWorkflow.value,
    advanced_comfyui_workflow: advancedWorkflow.value,
  })
  if (settingsService.statusMessage.value?.type === 'error') {
    errorMessage.value = settingsService.statusMessage.value.text
    return false
  }
  await setVisualsOptOut(false)
  return true
}

watch(noImages, () => {
  errorMessage.value = ''
})
hydrate()

defineExpose({ save })
</script>

<template>
  <div class="space-y-5">
    <div>
      <h3 class="text-lg font-black text-white mb-2">Visuals</h3>
      <p :class="wizardStyles.hint">
        Images bring covers, scenes and characters to life. Scenes and quick assets can use different
        providers. TaleWeaver also works text-only.
      </p>
    </div>

    <label class="flex items-center gap-3 cursor-pointer select-none">
      <input v-model="noImages" type="checkbox" class="w-4 h-4 accent-emerald-400" />
      <span class="text-sm font-bold text-white">No images — play text-only</span>
    </label>

    <p v-if="noImages" :class="wizardStyles.hint">
      Adventures will be text-only. You can enable images later in the admin settings.
    </p>

    <template v-else>
      <WizardModelPicker
        id="wizard-scene"
        v-model:provider="scene.provider"
        v-model:model="scene.model"
        label="Scene model (detailed)"
        hint="Covers, scenes, characters and protagonists."
        kind="image"
        :providers="providers"
        :configured-keys="configuredKeys"
        :preset-for="scenePreset"
        :base-url-for="baseUrlFor"
        test-key="wizard-t2i-scene"
        test-label="Generate test image"
        @test="runTest('wizard-t2i-scene', scene)"
      />

      <WizardModelPicker
        id="wizard-asset"
        v-model:provider="asset.provider"
        v-model:model="asset.model"
        label="Asset model (quick)"
        hint="Items and small assets."
        kind="image"
        :providers="providers"
        :configured-keys="configuredKeys"
        :preset-for="assetPreset"
        :base-url-for="baseUrlFor"
        test-key="wizard-t2i-asset"
        test-label="Generate test image"
        @test="runTest('wizard-t2i-asset', asset)"
      />

      <ComfyUISettings
        v-if="usesProvider('comfyui')"
        v-model:url="comfyuiUrl"
        v-model:timeout="comfyuiTimeout"
        v-model:simple-workflow="simpleWorkflow"
        v-model:advanced-workflow="advancedWorkflow"
        :simple="asset.provider === 'comfyui'"
        :advanced="scene.provider === 'comfyui'"
      />

      <div v-if="usesProvider('ollama')">
        <label :class="wizardStyles.label" for="wizard-t2i-ollama">Ollama URL</label>
        <input id="wizard-t2i-ollama" v-model="ollamaUrl" :class="wizardStyles.input" />
      </div>
      <div v-if="usesProvider('stable_diffusion')">
        <label :class="wizardStyles.label" for="wizard-sd-url">Stable Diffusion URL</label>
        <input id="wizard-sd-url" v-model="stableDiffusionUrl" :class="wizardStyles.input" />
      </div>
    </template>

    <p v-if="errorMessage" :class="wizardStyles.error">{{ errorMessage }}</p>
  </div>
</template>
