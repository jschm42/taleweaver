<script setup lang="ts">
import { ref, watch, computed } from 'vue'

const props = defineProps<{
  t2iForm: any
  availableConstants: any
  configuredKeys: any
  isSubmitting: boolean
  isLoadingStableDiffusionModels?: boolean
  testResults: any
}>()

const missingProviders = computed(() => {
  const providers = new Set([
    localForm.value.simple_model_provider,
    localForm.value.advanced_model_provider,
  ])
  const missing: string[] = []
  for (const p of providers) {
    if (p && p !== 'ollama' && p !== 'stable_diffusion' && !props.configuredKeys[p]) {
      missing.push(p)
    }
  }
  return missing
})


const emit = defineEmits<{
  (e: 'save', payload: any): void
  (e: 'test', payload: { key: string, model: string, provider: string }): void
  (e: 'refresh-stable-diffusion-models', sdUrl?: string): void
  (e: 'switchSection', section: string): void
}>()

const localForm = ref({
  ...props.t2iForm,
  // Model usage quality defaults (simple | advanced)
  scene_model_quality: props.t2iForm?.scene_model_quality ?? 'advanced',
  profile_model_quality: props.t2iForm?.profile_model_quality ?? 'advanced',
  protagonist_model_quality: props.t2iForm?.protagonist_model_quality ?? 'advanced',
  asset_model_quality: props.t2iForm?.asset_model_quality ?? 'simple',
})

watch(() => props.t2iForm, (newVal) => {
  localForm.value = {
    ...newVal,
    scene_model_quality: newVal?.scene_model_quality ?? 'advanced',
    profile_model_quality: newVal?.profile_model_quality ?? 'advanced',
    protagonist_model_quality: newVal?.protagonist_model_quality ?? 'advanced',
    asset_model_quality: newVal?.asset_model_quality ?? 'simple',
  }
}, { deep: true })

const isModelCustom = (model: string, provider: string) => {
  if (!model) return false
  const predefined = props.availableConstants.predefined_image_models[provider]
  if (!predefined) return true
  return !predefined.includes(model)
}

const getModelOptionLabel = (_provider: string, model: string) => model

const getProviderName = (id: string) => {
  return props.availableConstants.image_providers?.find((p: any) => p.id === id)?.name || id
}

const resolveModelOnProviderChange = (
  currentModel: string,
  newProvider: string,
  oldProvider: string | undefined
) => {
  const getPredefined = (provider: string | undefined) => {
    if (!provider) return [] as string[]
    return (props.availableConstants.predefined_image_models[provider] || [])
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

// Explicit handler so we always capture the current URL value from localForm.value
const refreshSdModels = () => {
  emit('refresh-stable-diffusion-models', localForm.value.stable_diffusion_url)
}

const handleSave = () => {
  emit('save', localForm.value)
}
</script>

<template>
  <div class="space-y-8 animate-fade-in">
    <div>
      <h1 class="text-4xl font-extrabold text-white mb-2">Visual Generation</h1>
      <p class="text-slate-400">Set up AI artists for your world portraits and scene visualizations.</p>
    </div>

    <div class="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-8">
      <!-- API KEY WARNING -->
      <div v-if="missingProviders.length > 0" class="p-6 bg-amber-500/10 border border-amber-500/20 rounded-2xl flex items-start gap-4">
        <div class="p-3 bg-amber-500/20 rounded-xl text-amber-500">
          <i class="ra ra-warning text-xl"></i>
        </div>
        <div>
          <h4 class="text-sm font-bold text-amber-400 uppercase tracking-widest mb-1">API Keys Missing</h4>
          <p class="text-xs text-amber-500/70 leading-relaxed">
            Missing keys for: <strong v-for="(p, i) in missingProviders" :key="p">{{ getProviderName(p) }}{{ i < missingProviders.length - 1 ? ', ' : '' }}</strong>.
            Please add them in the <button @click="emit('switchSection', 'keys')" class="text-amber-400 underline font-bold hover:text-amber-300">Provider Keys</button> section.
          </p>
        </div>
      </div>

      <!-- MODEL USAGE QUALITY CONFIG -->
      <div class="space-y-4 p-6 bg-slate-950/70 rounded-2xl border border-violet-500/20">
        <div class="flex items-center gap-2 mb-1">
          <i class="ra ra-gear text-violet-400"></i>
          <h3 class="text-xs font-bold uppercase tracking-widest text-slate-400">Model Usage per Content Type</h3>
        </div>
        <p class="text-xxs text-slate-500">Choose which model quality is used for each type of generated image. "Advanced" produces higher-quality results but may be slower or more expensive.</p>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-400">Scenes</label>
            <select v-model="localForm.scene_model_quality" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white outline-none focus:ring-2 focus:ring-violet-500/50">
              <option value="advanced">Advanced</option>
              <option value="simple">Simple</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-400">NPC Profiles</label>
            <select v-model="localForm.profile_model_quality" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white outline-none focus:ring-2 focus:ring-violet-500/50">
              <option value="advanced">Advanced</option>
              <option value="simple">Simple</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-400">Protagonist</label>
            <select v-model="localForm.protagonist_model_quality" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white outline-none focus:ring-2 focus:ring-violet-500/50">
              <option value="advanced">Advanced</option>
              <option value="simple">Simple</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-400">Other Assets</label>
            <select v-model="localForm.asset_model_quality" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white outline-none focus:ring-2 focus:ring-violet-500/50">
              <option value="advanced">Advanced</option>
              <option value="simple">Simple</option>
            </select>
          </div>
        </div>
      </div>
      
      <!-- SIMPLE VISUALS -->
      <div class="space-y-4 p-6 bg-slate-950/50 rounded-2xl border border-cyan-500/10">
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-lg font-bold text-cyan-400 flex items-center gap-2">
            <i class="ra ra-camera"></i> Simple Visuals (NPCs & Items)
          </h3>
          <button 
            @click="emit('test', { 
              key: 'simple_v', 
              model: localForm.simple_model, 
              provider: localForm.simple_model_provider,
              ollama_url: localForm.ollama_url,
              stable_diffusion_url: localForm.stable_diffusion_url,
              steps: localForm.simple_steps,
              cfg_scale: localForm.simple_cfg_scale,
              sampler_name: localForm.simple_sampler_name,
              scheduler: localForm.simple_scheduler,
              min_long_edge: localForm.simple_min_long_edge
            })"
            class="px-3 py-1.5 bg-cyan-600/20 hover:bg-cyan-600/40 text-cyan-300 text-xs font-bold rounded-lg border border-cyan-600/30 transition-all flex items-center gap-2"
          >
            <i class="ra ra-eye-shield"></i> Test Connection
          </button>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Provider</label>
            <select v-model="localForm.simple_model_provider" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50">
              <option v-for="p in availableConstants.image_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Model Selection</label>
            <select 
              :value="isModelCustom(localForm.simple_model, localForm.simple_model_provider) ? 'custom' : localForm.simple_model"
              @change="(e) => { 
                const val = (e.target as HTMLSelectElement).value; 
                if(val !== 'custom') localForm.simple_model = val;
                else if(!isModelCustom(localForm.simple_model, localForm.simple_model_provider)) localForm.simple_model = '';
              }"
              class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono"
            >
              <option value="" disabled>-- Please Select --</option>
              <option v-for="m in availableConstants.predefined_image_models[localForm.simple_model_provider]" :key="m" :value="m">{{ getModelOptionLabel(localForm.simple_model_provider, m) }}</option>
              <option value="custom">-- Custom Model String --</option>
            </select>
          </div>
        </div>

        <div v-if="isModelCustom(localForm.simple_model, localForm.simple_model_provider) || localForm.simple_model === ''" class="space-y-2 animate-fade-in">
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Custom Model ID</label>
          <input v-model="localForm.simple_model" type="text" maxlength="100" placeholder="e.g. dall-e-2" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono" />
        </div>

        <div v-if="localForm.simple_model_provider === 'stable_diffusion' || localForm.simple_model_provider === 'ollama'" class="grid grid-cols-1 md:grid-cols-2 gap-4 animate-fade-in">
          <div class="space-y-2 font-mono">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Steps (optional)</label>
            <input v-model.number="localForm.simple_steps" type="number" min="1" max="150" step="1" placeholder="e.g. 20" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50" />
          </div>
          <div class="space-y-2 font-mono">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">CFG Scale (optional)</label>
            <input v-model.number="localForm.simple_cfg_scale" type="number" min="1" max="30" step="0.5" placeholder="e.g. 7.0" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50" />
          </div>
        </div>

        <div v-if="localForm.simple_model_provider === 'stable_diffusion'" class="grid grid-cols-1 md:grid-cols-2 gap-4 animate-fade-in">
          <div class="space-y-2 font-mono">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Sampler (optional)</label>
            <input v-model="localForm.simple_sampler_name" type="text" placeholder="e.g. Euler" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50" />
          </div>
          <div class="space-y-2 font-mono">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Scheduler (optional)</label>
            <input v-model="localForm.simple_scheduler" type="text" placeholder="e.g. Normal or Simple" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50" />
          </div>
        </div>

        <div v-if="localForm.simple_model_provider === 'stable_diffusion' || localForm.simple_model_provider === 'ollama'" class="space-y-2 animate-fade-in">
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Min. Long Edge (px)</label>
          <div class="flex items-center gap-3">
            <input v-model.number="localForm.simple_min_long_edge" type="number" min="256" max="4096" step="8" placeholder="e.g. 1024" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono" />
            <span class="text-xxs text-slate-500 whitespace-nowrap">NPC ≈ 4:5</span>
          </div>
          <p class="text-xxs text-slate-500">Aspect ratio is determined automatically per content type (portrait, scene, cover, etc.).</p>
        </div>

        <!-- Test Result Feedback -->
        <div v-if="testResults.simple_v" :class="['p-4 rounded-xl text-sm font-medium border animate-fade-in', testResults.simple_v.status === 'loading' ? 'bg-slate-800 border-slate-700 text-slate-300' : testResults.simple_v.status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400']">
           <div class="flex flex-col gap-3">
              <div class="flex items-center gap-2">
                <div v-if="testResults.simple_v.status === 'loading'" class="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div>
                <i v-else :class="testResults.simple_v.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
                {{ testResults.simple_v.message }}
              </div>
              <img v-if="testResults.simple_v.image_url" :src="testResults.simple_v.image_url" class="w-full max-w-xs rounded-lg border border-white/10 shadow-lg" />
           </div>
        </div>
      </div>

      <!-- ADVANCED VISUALS -->
      <div class="space-y-4 p-6 bg-slate-950/50 rounded-2xl border border-cyan-500/10">
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-lg font-bold text-cyan-400 flex items-center gap-2">
            <i class="ra ra-brandy-glass"></i> Advanced Visuals (Scenes)
          </h3>
          <button 
            @click="emit('test', { 
              key: 'advanced_v', 
              model: localForm.advanced_model, 
              provider: localForm.advanced_model_provider,
              ollama_url: localForm.ollama_url,
              stable_diffusion_url: localForm.stable_diffusion_url,
              steps: localForm.advanced_steps,
              cfg_scale: localForm.advanced_cfg_scale,
              sampler_name: localForm.advanced_sampler_name,
              scheduler: localForm.advanced_scheduler,
              min_long_edge: localForm.advanced_min_long_edge
            })"
            class="px-3 py-1.5 bg-cyan-600/20 hover:bg-cyan-600/40 text-cyan-300 text-xs font-bold rounded-lg border border-cyan-600/30 transition-all flex items-center gap-2"
          >
            <i class="ra ra-eye-shield"></i> Test Connection
          </button>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Provider</label>
            <select v-model="localForm.advanced_model_provider" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50">
              <option v-for="p in availableConstants.image_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Model Selection</label>
            <select 
              :value="isModelCustom(localForm.advanced_model, localForm.advanced_model_provider) ? 'custom' : localForm.advanced_model"
              @change="(e) => { 
                const val = (e.target as HTMLSelectElement).value; 
                if(val !== 'custom') localForm.advanced_model = val;
                else if(!isModelCustom(localForm.advanced_model, localForm.advanced_model_provider)) localForm.advanced_model = '';
              }"
              class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono"
            >
              <option value="" disabled>-- Please Select --</option>
              <option v-for="m in availableConstants.predefined_image_models[localForm.advanced_model_provider]" :key="m" :value="m">{{ getModelOptionLabel(localForm.advanced_model_provider, m) }}</option>
              <option value="custom">-- Custom Model String --</option>
            </select>
          </div>
        </div>

        <div v-if="isModelCustom(localForm.advanced_model, localForm.advanced_model_provider) || localForm.advanced_model === ''" class="space-y-2 animate-fade-in">
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Custom Model ID</label>
          <input v-model="localForm.advanced_model" type="text" maxlength="100" placeholder="e.g. dall-e-3" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono" />
        </div>

        <div v-if="localForm.advanced_model_provider === 'stable_diffusion' || localForm.advanced_model_provider === 'ollama'" class="grid grid-cols-1 md:grid-cols-2 gap-4 animate-fade-in">
          <div class="space-y-2 font-mono">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Steps (optional)</label>
            <input v-model.number="localForm.advanced_steps" type="number" min="1" max="150" step="1" placeholder="e.g. 25" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50" />
          </div>
          <div class="space-y-2 font-mono">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">CFG Scale (optional)</label>
            <input v-model.number="localForm.advanced_cfg_scale" type="number" min="1" max="30" step="0.5" placeholder="e.g. 3.5" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50" />
          </div>
        </div>

        <div v-if="localForm.advanced_model_provider === 'stable_diffusion'" class="grid grid-cols-1 md:grid-cols-2 gap-4 animate-fade-in">
          <div class="space-y-2 font-mono">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Sampler (optional)</label>
            <input v-model="localForm.advanced_sampler_name" type="text" placeholder="e.g. Euler" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50" />
          </div>
          <div class="space-y-2 font-mono">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Scheduler (optional)</label>
            <input v-model="localForm.advanced_scheduler" type="text" placeholder="e.g. Normal or Simple" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50" />
          </div>
        </div>

        <div v-if="localForm.advanced_model_provider === 'stable_diffusion' || localForm.advanced_model_provider === 'ollama'" class="space-y-2 animate-fade-in">
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Min. Long Edge (px)</label>
          <div class="flex items-center gap-3">
            <input v-model.number="localForm.advanced_min_long_edge" type="number" min="256" max="4096" step="8" placeholder="e.g. 1024" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono" />
            <span class="text-xxs text-slate-500 whitespace-nowrap">Scene ≈ 16:9</span>
          </div>
          <p class="text-xxs text-slate-500">Aspect ratio is determined automatically per content type (portrait, scene, cover, etc.).</p>
        </div>

        <!-- Test Result Feedback -->
        <div v-if="testResults.advanced_v" :class="['p-4 rounded-xl text-sm font-medium border animate-fade-in', testResults.advanced_v.status === 'loading' ? 'bg-slate-800 border-slate-700 text-slate-300' : testResults.advanced_v.status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400']">
           <div class="flex flex-col gap-3">
              <div class="flex items-center gap-2">
                <div v-if="testResults.advanced_v.status === 'loading'" class="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div>
                <i v-else :class="testResults.advanced_v.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
                {{ testResults.advanced_v.message }}
              </div>
              <img v-if="testResults.advanced_v.image_url" :src="testResults.advanced_v.image_url" class="w-full max-w-xs rounded-lg border border-white/10 shadow-lg" />
           </div>
        </div>
      </div>

      <!-- GLOBAL VISUAL SETTINGS -->
      <div class="pt-6 border-t border-slate-800 space-y-6">
        <div class="flex items-center gap-2 mb-2">
          <i class="ra ra-save text-cyan-400"></i>
          <h3 class="text-xs font-bold uppercase tracking-widest text-slate-500">Global Visual Parameters</h3>
        </div>
        
        <div class="space-y-4">
          <div v-if="localForm.simple_model_provider === 'ollama' || localForm.advanced_model_provider === 'ollama'" class="space-y-2 p-4 bg-cyan-500/5 rounded-xl border border-cyan-500/20">
            <label class="block text-sm font-semibold text-slate-300">Ollama API Base URL</label>
            <input v-model="localForm.ollama_url" type="text" placeholder="http://localhost:11434" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono" />
          </div>

          <div v-if="localForm.simple_model_provider === 'stable_diffusion' || localForm.advanced_model_provider === 'stable_diffusion'" class="space-y-2 p-4 bg-cyan-500/5 rounded-xl border border-cyan-500/20">
            <div class="flex items-center justify-between">
              <label class="block text-sm font-semibold text-slate-300">Stable Diffusion API URL</label>
              <button 
                type="button"
                @click="refreshSdModels()"
                :disabled="isLoadingStableDiffusionModels"
                class="px-2.5 py-1 bg-cyan-600/20 hover:bg-cyan-600/40 text-cyan-300 text-xxs font-bold rounded border border-cyan-600/30 transition-all flex items-center gap-1"
              >
                <div v-if="isLoadingStableDiffusionModels" class="w-3 h-3 border border-cyan-300 border-t-transparent rounded-full animate-spin"></div>
                <i v-else class="ra ra-gear"></i>
                Refresh Models
              </button>
            </div>
            <input v-model="localForm.stable_diffusion_url" type="text" placeholder="http://127.0.0.1:7860" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono" />
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="space-y-2">
              <label class="block text-sm font-semibold text-slate-300">File Format</label>
              <select v-model="localForm.image_format" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-cyan-500/50 outline-none">
                <option value="jpeg">JPEG (Recommended)</option>
                <option value="png">PNG (Lossless)</option>
              </select>
              <p class="text-xxs text-slate-500">JPEG significantly reduces file size for assets.</p>
            </div>
            
            <div v-if="localForm.image_format === 'jpeg'" class="space-y-2">
              <div class="flex justify-between items-center mb-1">
                <label class="block text-sm font-semibold text-slate-300">JPEG Quality</label>
                <span class="text-xs font-mono font-bold text-cyan-400 bg-cyan-400/10 px-2 py-0.5 rounded">{{ localForm.image_quality }}%</span>
              </div>
              <input v-model.number="localForm.image_quality" type="range" min="10" max="100" step="5" class="w-full h-2 bg-slate-950 border border-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-500" />
            </div>
          </div>

        </div>
      </div>

      <button type="button" @click="handleSave" :disabled="isSubmitting" class="w-full py-4 bg-cyan-600 hover:bg-cyan-500 text-white font-bold rounded-xl transition-all shadow-lg disabled:opacity-50">
         {{ isSubmitting ? 'Painting...' : 'Update Visual Artists' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.4s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
