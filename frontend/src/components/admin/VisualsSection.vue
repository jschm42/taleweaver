<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import ComfyUISettings from './ComfyUISettings.vue'
import ModelCombobox from '@/components/common/ModelCombobox.vue'

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

const localForm = ref({
  ...props.t2iForm,
  comfyui_url: props.t2iForm?.comfyui_url ?? 'http://127.0.0.1:8188',
  comfyui_timeout: props.t2iForm?.comfyui_timeout ?? 600,
  simple_comfyui_workflow: props.t2iForm?.simple_comfyui_workflow ?? 'sdxl',
  advanced_comfyui_workflow: props.t2iForm?.advanced_comfyui_workflow ?? 'sdxl',
  scene_model_quality: props.t2iForm?.scene_model_quality ?? 'advanced',
  profile_model_quality: props.t2iForm?.profile_model_quality ?? 'advanced',
  protagonist_model_quality: props.t2iForm?.protagonist_model_quality ?? 'advanced',
  asset_model_quality: props.t2iForm?.asset_model_quality ?? 'simple',
})

watch(() => props.t2iForm, (newVal) => {
  localForm.value = {
    ...newVal,
    comfyui_url: newVal?.comfyui_url ?? 'http://127.0.0.1:8188',
    comfyui_timeout: newVal?.comfyui_timeout ?? 600,
    simple_comfyui_workflow: newVal?.simple_comfyui_workflow ?? 'sdxl',
    advanced_comfyui_workflow: newVal?.advanced_comfyui_workflow ?? 'sdxl',
    scene_model_quality: newVal?.scene_model_quality ?? 'advanced',
    profile_model_quality: newVal?.profile_model_quality ?? 'advanced',
    protagonist_model_quality: newVal?.protagonist_model_quality ?? 'advanced',
    asset_model_quality: newVal?.asset_model_quality ?? 'simple',
  }
}, { deep: true })

// Advanced tuning accordion state
const showSimpleAdvanced = ref(false)
const showAdvancedTuning = ref(false)

const missingProviders = computed(() => {
  const providers = new Set([
    localForm.value.simple_model_provider,
    localForm.value.advanced_model_provider,
  ])
  const missing: string[] = []
  for (const p of providers) {
    if (p && p !== 'ollama' && p !== 'stable_diffusion' && p !== 'comfyui' && !props.configuredKeys?.[p]) {
      missing.push(p)
    }
  }
  return missing
})

const isProviderConfigured = (providerId: string) => {
  if (providerId === 'ollama' || providerId === 'stable_diffusion' || providerId === 'comfyui') return true
  return Boolean(props.configuredKeys?.[providerId])
}

/** Self-hosted endpoints whose discovered model list depends on the configured URL. */
const modelBaseUrl = (provider: string): string => {
  if (provider === 'comfyui') return localForm.value.comfyui_url || ''
  if (provider === 'ollama') return localForm.value.ollama_url || ''
  if (provider === 'stable_diffusion') return localForm.value.stable_diffusion_url || ''
  return ''
}

const getProviderName = (id: string) => {
  return props.availableConstants?.image_providers?.find((p: any) => p.id === id)?.name || id
}

const resolveModelOnProviderChange = (
  currentModel: string,
  newProvider: string,
  oldProvider: string | undefined
) => {
  const getPredefined = (provider: string | undefined) => {
    if (!provider) return [] as string[]
    return (props.availableConstants?.predefined_image_models?.[provider] || [])
  }

  const nextPredefined = getPredefined(newProvider)
  if (nextPredefined.length === 0) return currentModel
  if (!currentModel) return nextPredefined[0]
  if (nextPredefined.includes(currentModel)) return currentModel

  const prevPredefined = getPredefined(oldProvider)
  if (prevPredefined.includes(currentModel)) return nextPredefined[0]

  return currentModel
}

const SD_PRESET_STEPS = 4
const SD_PRESET_CFG = 1.0
const SD_PRESET_SAMPLER = 'Euler'
const SD_PRESET_SCHEDULER = 'Normal'

watch(() => localForm.value.simple_model_provider, (provider, oldProvider) => {
  localForm.value.simple_model = resolveModelOnProviderChange(localForm.value.simple_model, provider, oldProvider)
  if (provider === 'stable_diffusion') {
    if (!localForm.value.simple_steps) localForm.value.simple_steps = SD_PRESET_STEPS
    if (!localForm.value.simple_cfg_scale) localForm.value.simple_cfg_scale = SD_PRESET_CFG
    if (!localForm.value.simple_sampler_name) localForm.value.simple_sampler_name = SD_PRESET_SAMPLER
    if (!localForm.value.simple_scheduler) localForm.value.simple_scheduler = SD_PRESET_SCHEDULER
  }
})

watch(() => localForm.value.advanced_model_provider, (provider, oldProvider) => {
  localForm.value.advanced_model = resolveModelOnProviderChange(localForm.value.advanced_model, provider, oldProvider)
  if (provider === 'stable_diffusion') {
    if (!localForm.value.advanced_steps) localForm.value.advanced_steps = SD_PRESET_STEPS
    if (!localForm.value.advanced_cfg_scale) localForm.value.advanced_cfg_scale = SD_PRESET_CFG
    if (!localForm.value.advanced_sampler_name) localForm.value.advanced_sampler_name = SD_PRESET_SAMPLER
    if (!localForm.value.advanced_scheduler) localForm.value.advanced_scheduler = SD_PRESET_SCHEDULER
  }
})

const refreshSdModels = () => {
  emit('refresh-stable-diffusion-models', localForm.value.stable_diffusion_url)
}

const handleSave = () => {
  emit('save', localForm.value)
}

const testSimple = () => {
  emit('test', { 
    key: 'simple_v', 
    model: localForm.value.simple_model, 
    provider: localForm.value.simple_model_provider,
    ollama_url: localForm.value.ollama_url,
    stable_diffusion_url: localForm.value.stable_diffusion_url,
    steps: localForm.value.simple_steps,
    cfg_scale: localForm.value.simple_cfg_scale,
    sampler_name: localForm.value.simple_sampler_name,
    scheduler: localForm.value.simple_scheduler,
    comfyui_url: localForm.value.comfyui_url,
    comfyui_timeout: localForm.value.comfyui_timeout,
    comfyui_workflow: localForm.value.simple_comfyui_workflow,
    min_long_edge: localForm.value.simple_min_long_edge
  })
}

const testAdvanced = () => {
  emit('test', { 
    key: 'advanced_v', 
    model: localForm.value.advanced_model, 
    provider: localForm.value.advanced_model_provider,
    ollama_url: localForm.value.ollama_url,
    stable_diffusion_url: localForm.value.stable_diffusion_url,
    steps: localForm.value.advanced_steps,
    cfg_scale: localForm.value.advanced_cfg_scale,
    sampler_name: localForm.value.advanced_sampler_name,
    scheduler: localForm.value.advanced_scheduler,
    comfyui_url: localForm.value.comfyui_url,
    comfyui_timeout: localForm.value.comfyui_timeout,
    comfyui_workflow: localForm.value.advanced_comfyui_workflow,
    min_long_edge: localForm.value.advanced_min_long_edge
  })
}
</script>

<template>
  <div class="space-y-6 animate-fade-in max-w-5xl">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
          <i class="ra ra-camera text-cyan-400"></i>
          Visual Generation (T2I)
        </h1>
        <p class="text-slate-400 text-sm mt-1">
          Configure AI artists and quality routing for scenes, character portraits, and items.
        </p>
      </div>

      <button 
        type="button" 
        @click="handleSave" 
        :disabled="isSubmitting" 
        class="px-6 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-cyan-900/30 disabled:opacity-50 flex items-center gap-2 self-start sm:self-auto cursor-pointer"
      >
        <i v-if="isSubmitting" class="ra ra-recycle animate-spin"></i>
        <i v-else class="ra ra-save"></i>
        <span>{{ isSubmitting ? 'Painting...' : 'Save Visuals Settings' }}</span>
      </button>
    </div>

    <!-- API KEY WARNING -->
    <div v-if="missingProviders.length > 0" class="p-4 bg-amber-500/10 border border-amber-500/30 rounded-2xl flex items-start gap-3">
      <div class="p-2.5 bg-amber-500/20 rounded-xl text-amber-400 shrink-0">
        <i class="ra ra-warning text-lg"></i>
      </div>
      <div>
        <h4 class="text-xs font-bold text-amber-400 uppercase tracking-wider mb-1">Missing Provider API Keys</h4>
        <p class="text-xs text-amber-400/90 leading-relaxed">
          The selected visual artists require missing keys for: 
          <strong v-for="(p, i) in missingProviders" :key="p" class="text-amber-200">
            {{ getProviderName(p) }}{{ i < missingProviders.length - 1 ? ', ' : '' }}
          </strong>.
          Configure them in the 
          <button @click="emit('switchSection', 'keys')" class="text-amber-300 underline font-bold hover:text-white">
            Provider Vault
          </button>.
        </p>
      </div>
    </div>

    <ComfyUISettings
      v-if="localForm.simple_model_provider === 'comfyui' || localForm.advanced_model_provider === 'comfyui'"
      v-model:url="localForm.comfyui_url"
      v-model:timeout="localForm.comfyui_timeout"
      v-model:simple-workflow="localForm.simple_comfyui_workflow"
      v-model:advanced-workflow="localForm.advanced_comfyui_workflow"
      :simple="localForm.simple_model_provider === 'comfyui'"
      :advanced="localForm.advanced_model_provider === 'comfyui'"
    />

    <!-- QUALITY ROUTING PER CONTENT TYPE -->
    <div class="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
      <div class="flex items-center gap-2.5 pb-3 border-b border-slate-800/80">
        <div class="w-9 h-9 rounded-xl bg-violet-500/10 text-violet-400 border border-violet-500/20 flex items-center justify-center text-sm">
          <i class="ra ra-gear"></i>
        </div>
        <div>
          <h3 class="text-sm font-bold text-white">Quality Routing by Content Type</h3>
          <p class="text-xs text-slate-400">Route each asset type to Standard (Fast) or High-Fidelity (Advanced) rendering.</p>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <!-- Scenes -->
        <div class="p-3.5 bg-slate-950 border border-slate-800 rounded-2xl space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-white flex items-center gap-1.5">
              <i class="ra ra-mountain text-cyan-400 text-xs"></i>
              Scenes & World
            </span>
            <span class="text-[10px] font-mono text-slate-500">16:9</span>
          </div>
          <div class="grid grid-cols-2 gap-1 p-1 bg-slate-900 rounded-xl border border-slate-800">
            <button
              type="button"
              @click="localForm.scene_model_quality = 'simple'"
              :class="['py-1 text-xs font-bold rounded-lg transition-all', localForm.scene_model_quality === 'simple' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-white']"
            >
              Standard
            </button>
            <button
              type="button"
              @click="localForm.scene_model_quality = 'advanced'"
              :class="['py-1 text-xs font-bold rounded-lg transition-all', localForm.scene_model_quality === 'advanced' ? 'bg-violet-600 text-white shadow' : 'text-slate-400 hover:text-white']"
            >
              High-Fi
            </button>
          </div>
        </div>

        <!-- NPC Profiles -->
        <div class="p-3.5 bg-slate-950 border border-slate-800 rounded-2xl space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-white flex items-center gap-1.5">
              <i class="ra ra-hood text-cyan-400 text-xs"></i>
              NPC Portraits
            </span>
            <span class="text-[10px] font-mono text-slate-500">4:5</span>
          </div>
          <div class="grid grid-cols-2 gap-1 p-1 bg-slate-900 rounded-xl border border-slate-800">
            <button
              type="button"
              @click="localForm.profile_model_quality = 'simple'"
              :class="['py-1 text-xs font-bold rounded-lg transition-all', localForm.profile_model_quality === 'simple' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-white']"
            >
              Standard
            </button>
            <button
              type="button"
              @click="localForm.profile_model_quality = 'advanced'"
              :class="['py-1 text-xs font-bold rounded-lg transition-all', localForm.profile_model_quality === 'advanced' ? 'bg-violet-600 text-white shadow' : 'text-slate-400 hover:text-white']"
            >
              High-Fi
            </button>
          </div>
        </div>

        <!-- Protagonist -->
        <div class="p-3.5 bg-slate-950 border border-slate-800 rounded-2xl space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-white flex items-center gap-1.5">
              <i class="ra ra-player text-cyan-400 text-xs"></i>
              Protagonist
            </span>
            <span class="text-[10px] font-mono text-slate-500">4:5</span>
          </div>
          <div class="grid grid-cols-2 gap-1 p-1 bg-slate-900 rounded-xl border border-slate-800">
            <button
              type="button"
              @click="localForm.protagonist_model_quality = 'simple'"
              :class="['py-1 text-xs font-bold rounded-lg transition-all', localForm.protagonist_model_quality === 'simple' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-white']"
            >
              Standard
            </button>
            <button
              type="button"
              @click="localForm.protagonist_model_quality = 'advanced'"
              :class="['py-1 text-xs font-bold rounded-lg transition-all', localForm.protagonist_model_quality === 'advanced' ? 'bg-violet-600 text-white shadow' : 'text-slate-400 hover:text-white']"
            >
              High-Fi
            </button>
          </div>
        </div>

        <!-- Other Assets -->
        <div class="p-3.5 bg-slate-950 border border-slate-800 rounded-2xl space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-white flex items-center gap-1.5">
              <i class="ra ra-gem text-cyan-400 text-xs"></i>
              Items & Loot
            </span>
            <span class="text-[10px] font-mono text-slate-500">1:1</span>
          </div>
          <div class="grid grid-cols-2 gap-1 p-1 bg-slate-900 rounded-xl border border-slate-800">
            <button
              type="button"
              @click="localForm.asset_model_quality = 'simple'"
              :class="['py-1 text-xs font-bold rounded-lg transition-all', localForm.asset_model_quality === 'simple' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-white']"
            >
              Standard
            </button>
            <button
              type="button"
              @click="localForm.asset_model_quality = 'advanced'"
              :class="['py-1 text-xs font-bold rounded-lg transition-all', localForm.asset_model_quality === 'advanced' ? 'bg-violet-600 text-white shadow' : 'text-slate-400 hover:text-white']"
            >
              High-Fi
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- TIER 1: STANDARD VISUALS (NPCs & Items) -->
    <div class="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-3xl p-6 shadow-xl space-y-4 transition-all">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-slate-800/80">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 flex items-center justify-center text-lg">
            <i class="ra ra-camera"></i>
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 class="text-base font-bold text-white">Standard Quality Visuals</h3>
              <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-bold">
                FAST / LOW LATENCY
              </span>
            </div>
            <p class="text-xs text-slate-400 mt-0.5">Used for rapid asset rendering, icons, item cards, and catalog tiles.</p>
          </div>
        </div>

        <button 
          type="button"
          @click="testSimple"
          :disabled="testResults.simple_v?.status === 'loading' || !localForm.simple_model"
          class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-xl border border-slate-700 transition-all flex items-center gap-1.5 disabled:opacity-40 self-start sm:self-auto cursor-pointer"
        >
          <i v-if="testResults.simple_v?.status === 'loading'" class="ra ra-cycle animate-spin text-cyan-400"></i>
          <i v-else class="ra ra-player text-cyan-400"></i>
          <span>Test Generation</span>
        </button>
      </div>

      <!-- Provider & Model Selection -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Provider</label>
          <select 
            v-model="localForm.simple_model_provider" 
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:ring-2 focus:ring-cyan-500/50"
          >
            <option v-for="p in availableConstants.image_providers" :key="p.id" :value="p.id">
              {{ p.name }} {{ isProviderConfigured(p.id) ? '✓' : '(No Key)' }}
            </option>
          </select>
        </div>

        <div>
          <label for="t2i-simple-model" class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Model</label>
          <ModelCombobox
            v-model="localForm.simple_model"
            input-id="t2i-simple-model"
            kind="image"
            :provider="localForm.simple_model_provider"
            :base-url="modelBaseUrl(localForm.simple_model_provider)"
            input-class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-4 pr-10 py-2.5 text-sm text-white outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono"
          />
        </div>
      </div>

      <!-- Test Feedback -->
      <div 
        v-if="testResults.simple_v" 
        class="p-3.5 rounded-2xl border text-xs font-mono animate-fade-in flex flex-col gap-3"
        :class="[
          testResults.simple_v.status === 'loading'
            ? 'bg-slate-950 border-slate-800 text-slate-300'
            : testResults.simple_v.status === 'success'
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
            : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
        ]"
      >
        <div class="flex items-center gap-2">
          <i :class="testResults.simple_v.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
          <span>{{ testResults.simple_v.message }}</span>
        </div>
        <img 
          v-if="testResults.simple_v.image_url" 
          :src="testResults.simple_v.image_url" 
          class="w-48 h-48 object-cover rounded-xl border border-white/10 shadow-lg mt-1" 
        />
      </div>

      <!-- Advanced Tuning Toggle (Stable Diffusion / Ollama only) -->
      <div 
        v-if="localForm.simple_model_provider === 'stable_diffusion' || localForm.simple_model_provider === 'ollama' || localForm.simple_model_provider === 'comfyui'"
        class="pt-2 border-t border-slate-800/60"
      >
        <button
          type="button"
          @click="showSimpleAdvanced = !showSimpleAdvanced"
          class="text-xs font-bold text-slate-400 hover:text-white flex items-center gap-2 transition-colors"
        >
          <span>{{ showSimpleAdvanced ? '▲ Hide Diffusion Parameters' : '▼ Local Diffusion Parameters (Steps, CFG, Sampler, Edge)' }}</span>
        </button>

        <div v-if="showSimpleAdvanced" class="mt-4 pt-3 border-t border-slate-800/40 space-y-4 animate-fade-in">
          <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1">Steps</label>
              <input 
                v-model.number="localForm.simple_steps" 
                type="number" 
                min="1" 
                max="150" 
                placeholder="Default: 20" 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-cyan-500/50 outline-none" 
              />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1">CFG Scale</label>
              <input 
                v-model.number="localForm.simple_cfg_scale" 
                type="number" 
                min="1" 
                max="30" 
                step="0.5" 
                placeholder="Default: 7.0" 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-cyan-500/50 outline-none" 
              />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1">Sampler</label>
              <input 
                v-model="localForm.simple_sampler_name" 
                type="text" 
                placeholder="e.g. Euler" 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-cyan-500/50 outline-none" 
              />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1">Scheduler</label>
              <input 
                v-model="localForm.simple_scheduler" 
                type="text" 
                placeholder="e.g. Normal" 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-cyan-500/50 outline-none" 
              />
            </div>
          </div>

          <div>
            <label class="block text-xs font-bold text-slate-400 mb-1">Min. Long Edge (px)</label>
            <input 
              v-model.number="localForm.simple_min_long_edge" 
              type="number" 
              min="256" 
              max="4096" 
              step="8" 
              placeholder="e.g. 1024" 
              class="w-full sm:w-64 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-cyan-500/50 outline-none" 
            />
          </div>
        </div>
      </div>
    </div>

    <!-- TIER 2: HIGH-FIDELITY VISUALS (Scenes & Avatars) -->
    <div class="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-3xl p-6 shadow-xl space-y-4 transition-all">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-slate-800/80">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-violet-500/10 text-violet-400 border border-violet-500/20 flex items-center justify-center text-lg">
            <i class="ra ra-brandy-glass"></i>
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 class="text-base font-bold text-white">High-Fidelity Visuals (Scenes & Lore)</h3>
              <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 font-bold">
                MAX QUALITY
              </span>
            </div>
            <p class="text-xs text-slate-400 mt-0.5">Used for epic cinematic world scenes, primary character avatars, and climax moments.</p>
          </div>
        </div>

        <button 
          type="button"
          @click="testAdvanced"
          :disabled="testResults.advanced_v?.status === 'loading' || !localForm.advanced_model"
          class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-xl border border-slate-700 transition-all flex items-center gap-1.5 disabled:opacity-40 self-start sm:self-auto cursor-pointer"
        >
          <i v-if="testResults.advanced_v?.status === 'loading'" class="ra ra-cycle animate-spin text-violet-400"></i>
          <i v-else class="ra ra-player text-violet-400"></i>
          <span>Test Generation</span>
        </button>
      </div>

      <!-- Provider & Model Selection -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Provider</label>
          <select 
            v-model="localForm.advanced_model_provider" 
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:ring-2 focus:ring-violet-500/50"
          >
            <option v-for="p in availableConstants.image_providers" :key="p.id" :value="p.id">
              {{ p.name }} {{ isProviderConfigured(p.id) ? '✓' : '(No Key)' }}
            </option>
          </select>
        </div>

        <div>
          <label for="t2i-advanced-model" class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Model</label>
          <ModelCombobox
            v-model="localForm.advanced_model"
            input-id="t2i-advanced-model"
            kind="image"
            :provider="localForm.advanced_model_provider"
            :base-url="modelBaseUrl(localForm.advanced_model_provider)"
            input-class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-4 pr-10 py-2.5 text-sm text-white outline-none focus:ring-2 focus:ring-violet-500/50 font-mono"
          />
        </div>
      </div>

      <!-- Test Feedback -->
      <div 
        v-if="testResults.advanced_v" 
        class="p-3.5 rounded-2xl border text-xs font-mono animate-fade-in flex flex-col gap-3"
        :class="[
          testResults.advanced_v.status === 'loading'
            ? 'bg-slate-950 border-slate-800 text-slate-300'
            : testResults.advanced_v.status === 'success'
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
            : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
        ]"
      >
        <div class="flex items-center gap-2">
          <i :class="testResults.advanced_v.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
          <span>{{ testResults.advanced_v.message }}</span>
        </div>
        <img 
          v-if="testResults.advanced_v.image_url" 
          :src="testResults.advanced_v.image_url" 
          class="w-48 h-48 object-cover rounded-xl border border-white/10 shadow-lg mt-1" 
        />
      </div>

      <!-- Advanced Tuning Toggle (Stable Diffusion / Ollama only) -->
      <div 
        v-if="localForm.advanced_model_provider === 'stable_diffusion' || localForm.advanced_model_provider === 'ollama' || localForm.advanced_model_provider === 'comfyui'"
        class="pt-2 border-t border-slate-800/60"
      >
        <button
          type="button"
          @click="showAdvancedTuning = !showAdvancedTuning"
          class="text-xs font-bold text-slate-400 hover:text-white flex items-center gap-2 transition-colors"
        >
          <span>{{ showAdvancedTuning ? '▲ Hide Diffusion Parameters' : '▼ Local Diffusion Parameters (Steps, CFG, Sampler, Edge)' }}</span>
        </button>

        <div v-if="showAdvancedTuning" class="mt-4 pt-3 border-t border-slate-800/40 space-y-4 animate-fade-in">
          <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1">Steps</label>
              <input 
                v-model.number="localForm.advanced_steps" 
                type="number" 
                min="1" 
                max="150" 
                placeholder="Default: 25" 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-violet-500/50 outline-none" 
              />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1">CFG Scale</label>
              <input 
                v-model.number="localForm.advanced_cfg_scale" 
                type="number" 
                min="1" 
                max="30" 
                step="0.5" 
                placeholder="Default: 3.5" 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-violet-500/50 outline-none" 
              />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1">Sampler</label>
              <input 
                v-model="localForm.advanced_sampler_name" 
                type="text" 
                placeholder="e.g. Euler" 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-violet-500/50 outline-none" 
              />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1">Scheduler</label>
              <input 
                v-model="localForm.advanced_scheduler" 
                type="text" 
                placeholder="e.g. Normal" 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-violet-500/50 outline-none" 
              />
            </div>
          </div>

          <div>
            <label class="block text-xs font-bold text-slate-400 mb-1">Min. Long Edge (px)</label>
            <input 
              v-model.number="localForm.advanced_min_long_edge" 
              type="number" 
              min="256" 
              max="4096" 
              step="8" 
              placeholder="e.g. 1024" 
              class="w-full sm:w-64 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-violet-500/50 outline-none" 
            />
          </div>
        </div>
      </div>
    </div>

    <!-- GLOBAL VISUAL SETTINGS (Format, Quality, Endpoints) -->
    <div class="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-6">
      <div class="flex items-center gap-3 pb-3 border-b border-slate-800/80">
        <div class="w-10 h-10 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 flex items-center justify-center text-lg">
          <i class="ra ra-save"></i>
        </div>
        <div>
          <h3 class="text-base font-bold text-white">Global Rendering & Storage Options</h3>
          <p class="text-xs text-slate-400 mt-0.5">Control image encoding, compression, and local image server connections.</p>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- File Format -->
        <div class="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-2">
          <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider">Storage Format</label>
          <select 
            v-model="localForm.image_format" 
            class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:ring-2 focus:ring-cyan-500/50 outline-none"
          >
            <option value="jpeg">JPEG (Fast, Optimized Disk Usage)</option>
            <option value="png">PNG (Lossless, Larger Disk Usage)</option>
          </select>
          <p class="text-[11px] text-slate-500">JPEG saves up to 80% disk space per generated portrait/scene.</p>
        </div>

        <!-- JPEG Quality Slider -->
        <div v-if="localForm.image_format === 'jpeg'" class="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-2">
          <div class="flex items-center justify-between">
            <label class="text-xs font-bold text-slate-400 uppercase tracking-wider">JPEG Quality</label>
            <span class="text-xs font-mono font-bold text-cyan-400 bg-cyan-400/10 px-2 py-0.5 rounded">{{ localForm.image_quality }}%</span>
          </div>
          <input 
            v-model.number="localForm.image_quality" 
            type="range" 
            min="10" 
            max="100" 
            step="5" 
            class="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-500 mt-2" 
          />
          <div class="flex justify-between text-[10px] text-slate-500 font-mono">
            <span>Compact (50%)</span>
            <span>Balanced (85%)</span>
            <span>Max (100%)</span>
          </div>
        </div>
      </div>

      <!-- Stable Diffusion Endpoint -->
      <div 
        v-if="localForm.simple_model_provider === 'stable_diffusion' || localForm.advanced_model_provider === 'stable_diffusion'"
        class="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3"
      >
        <div class="flex items-center justify-between">
          <label class="text-xs font-bold text-white flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-cyan-400"></span>
            Stable Diffusion WebUI API URL
          </label>
          <button 
            type="button"
            @click="refreshSdModels"
            :disabled="isLoadingStableDiffusionModels"
            class="px-2.5 py-1 bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 text-[11px] font-bold rounded-lg border border-cyan-500/30 transition-all flex items-center gap-1 cursor-pointer"
          >
            <i class="ra ra-recycle" :class="{'animate-spin': isLoadingStableDiffusionModels}"></i>
            <span>{{ isLoadingStableDiffusionModels ? 'Connecting...' : 'Fetch Checkpoints' }}</span>
          </button>
        </div>
        <input 
          v-model="localForm.stable_diffusion_url" 
          type="text" 
          placeholder="http://127.0.0.1:7860" 
          class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white font-mono outline-none focus:ring-2 focus:ring-cyan-500/50" 
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.3s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
