<script setup lang="ts">
import { ref, watch, computed } from 'vue'

const props = defineProps<{
  llmForm: any
  availableConstants: any
  configuredKeys: any
  isSubmitting: boolean
  isLoadingOllamaModels: boolean
  isLoadingMinimaxModels: boolean
  isLoadingLlmModels: Record<string, boolean>
  testResults: any
}>()

const missingProviders = computed(() => {
  const providers = new Set([
    localForm.value.small_model_provider,
    localForm.value.complex_model_provider,
    localForm.value.generator_model_provider,
    localForm.value.play_agent_model_provider,
    localForm.value.compression_model_provider,
  ])
  const missing: string[] = []
  for (const p of providers) {
    if (p && p !== 'ollama' && !props.configuredKeys[p]) {
      missing.push(p)
    }
  }
  return missing
})

const emit = defineEmits<{
  (e: 'save', payload: any): void
  (e: 'test', payload: { key: string, model: string, provider: string, openrouterProvider?: string }): void
  (e: 'refreshOllamaModels', ollamaUrl?: string): void
  (e: 'refreshMinimaxModels', minimaxUrl?: string): void
  (e: 'refreshLlmModels', provider: string, apiBase?: string): void
  (e: 'switchSection', section: string): void
}>()

const normalizeLocalForm = (data: any) => ({
  ...data,
  turns_before_compacting: typeof data?.turns_before_compacting === 'number' ? data.turns_before_compacting : 10,
  enable_history_compression: typeof data?.enable_history_compression === 'boolean' ? data.enable_history_compression : true,
})

const localForm = ref(normalizeLocalForm(props.llmForm))

watch(() => props.llmForm, (newVal) => {
  localForm.value = normalizeLocalForm(newVal)
}, { deep: true })

const isModelCustom = (model: string, provider: string) => {
  if (!model) return false
  const predefined = props.availableConstants.predefined_llm_models?.[provider]
  if (!predefined) return true
  return !predefined.includes(model)
}

const getModelOptionLabel = (_provider: string, model: string) => model

const getProviderName = (id: string) => {
  return props.availableConstants.llm_providers?.find((p: any) => p.id === id)?.name || id
}

const resolveModelOnProviderChange = (
  currentModel: string,
  newProvider: string,
  oldProvider: string | undefined
) => {
  const getPredefined = (provider: string | undefined) => {
    if (!provider) return [] as string[]
    return (props.availableConstants.predefined_llm_models?.[provider] || [])
  }

  const nextPredefined = getPredefined(newProvider)
  if (nextPredefined.length === 0) return currentModel
  if (!currentModel) return nextPredefined[0]
  if (nextPredefined.includes(currentModel)) return currentModel

  const prevPredefined = getPredefined(oldProvider)
  if (prevPredefined.includes(currentModel)) return nextPredefined[0]

  return currentModel
}

watch(() => localForm.value.small_model_provider, (provider, oldProvider) => {
  localForm.value.small_model = resolveModelOnProviderChange(localForm.value.small_model, provider, oldProvider)
})

watch(() => localForm.value.complex_model_provider, (provider, oldProvider) => {
  localForm.value.complex_model = resolveModelOnProviderChange(localForm.value.complex_model, provider, oldProvider)
})

watch(() => localForm.value.generator_model_provider, (provider, oldProvider) => {
  localForm.value.generator_model = resolveModelOnProviderChange(localForm.value.generator_model, provider, oldProvider)
})

watch(() => localForm.value.play_agent_model_provider, (provider, oldProvider) => {
  localForm.value.play_agent_model = resolveModelOnProviderChange(localForm.value.play_agent_model, provider, oldProvider)
})

watch(() => localForm.value.compression_model_provider, (provider, oldProvider) => {
  localForm.value.compression_model = resolveModelOnProviderChange(localForm.value.compression_model, provider, oldProvider)
})

const hasOllamaProviderSelected = computed(() => (
  localForm.value.small_model_provider === 'ollama'
  || localForm.value.complex_model_provider === 'ollama'
  || localForm.value.generator_model_provider === 'ollama'
  || localForm.value.play_agent_model_provider === 'ollama'
  || localForm.value.compression_model_provider === 'ollama'
))

const hasMinimaxProviderSelected = computed(() => (
  localForm.value.small_model_provider === 'minimax'
  || localForm.value.complex_model_provider === 'minimax'
  || localForm.value.generator_model_provider === 'minimax'
  || localForm.value.play_agent_model_provider === 'minimax'
  || localForm.value.compression_model_provider === 'minimax'
))

const ollamaModelCount = computed(() => {
  const models = props.availableConstants?.predefined_llm_models?.ollama
  return Array.isArray(models) ? models.length : 0
})

const minimaxModelCount = computed(() => {
  const models = props.availableConstants?.predefined_llm_models?.minimax
  return Array.isArray(models) ? models.length : 0
})

watch(hasOllamaProviderSelected, (enabled) => {
  if (enabled) {
    emit('refreshOllamaModels', localForm.value.ollama_url)
  }
}, { immediate: true })

const refreshOllamaModels = () => {
  emit('refreshOllamaModels', localForm.value.ollama_url)
}

const refreshMinimaxModels = () => {
  emit('refreshMinimaxModels', localForm.value.minimax_url)
}

const LLM_MODEL_DISCOVERY_PROVIDERS = ['openai', 'anthropic', 'google', 'openrouter', 'deepseek', 'kimi', 'minimax']

const isLlmDiscoveryProvider = (provider: string | undefined | null) => {
  return !!provider && LLM_MODEL_DISCOVERY_PROVIDERS.includes(provider)
}

const isLlmProviderLoading = (provider: string | undefined | null) => {
  if (!provider) return false
  if (provider === 'minimax') return props.isLoadingMinimaxModels
  return !!props.isLoadingLlmModels?.[provider]
}

const refreshLlmProviderModels = (provider: string) => {
  if (provider === 'minimax') {
    emit('refreshMinimaxModels', localForm.value.minimax_url)
  } else {
    emit('refreshLlmModels', provider, localForm.value.minimax_url)
  }
}

// Warning: Compacting is enabled but no compression model is chosen
const isCompressionModelMissingWarning = computed(() => {
  return !!localForm.value.enable_history_compression && !localForm.value.compression_model?.trim()
})

const handleTurnsInput = (e: Event) => {
  const val = Number((e.target as HTMLInputElement).value)
  if (!isNaN(val)) {
    localForm.value.turns_before_compacting = Math.min(100, Math.max(1, val))
  }
}

const handleSave = () => {
  emit('save', localForm.value)
}
</script>

<template>
  <div class="space-y-4 animate-fade-in max-w-5xl">
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
          <i class="ra ra-crystal-ball text-purple-400"></i>
          Intelligence Routing
        </h1>
        <p class="text-xs text-slate-400 mt-0.5">Configure model assignments for mechanics, storytelling, world generation & memory.</p>
      </div>
      <button
        type="button"
        @click="handleSave"
        :disabled="isSubmitting"
        class="px-5 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl transition-all shadow-md shadow-purple-900/30 disabled:opacity-50 flex items-center gap-2 shrink-0 cursor-pointer"
      >
        <i v-if="isSubmitting" class="ra ra-recycle animate-spin"></i>
        <i v-else class="ra ra-save"></i>
        {{ isSubmitting ? 'Saving...' : 'Save Settings' }}
      </button>
    </div>

    <!-- API KEY WARNING -->
    <div v-if="missingProviders.length > 0" class="p-3.5 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-3">
      <div class="p-2 bg-amber-500/20 rounded-lg text-amber-400 shrink-0">
        <i class="ra ra-warning text-lg"></i>
      </div>
      <div class="min-w-0">
        <h4 class="text-xs font-bold text-amber-400 uppercase tracking-wider mb-0.5">Missing Provider API Keys</h4>
        <p class="text-xs text-amber-500/80 leading-relaxed">
          Missing keys for: <strong v-for="(p, i) in missingProviders" :key="p" class="text-amber-300">{{ getProviderName(p) }}{{ i < missingProviders.length - 1 ? ', ' : '' }}</strong>.
          Please configure them in the <button @click="emit('switchSection', 'keys')" class="text-amber-400 underline font-bold hover:text-amber-300">Provider Keys</button> section.
        </p>
      </div>
    </div>

    <div class="space-y-3.5">
      <!-- 1. SIMPLE MODEL -->
      <div class="p-4 bg-slate-900/90 border border-purple-500/15 rounded-xl shadow-lg space-y-3">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <span class="w-7 h-7 rounded-lg bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-300 text-xs">
              <i class="ra ra-gear-hammer"></i>
            </span>
            <div>
              <h3 class="text-sm font-bold text-white flex items-center gap-1.5">
                Simple Model
                <span class="text-[10px] font-semibold text-purple-400 bg-purple-500/15 px-1.5 py-0.5 rounded border border-purple-500/30 uppercase tracking-wider">Pass 1: Mechanics</span>
              </h3>
              <p class="text-[11px] text-slate-400">Rule enforcement, inventory operations, and mechanics reasoning.</p>
            </div>
          </div>
          <button 
            type="button"
            @click="emit('test', { key: 'simple', model: localForm.small_model, provider: localForm.small_model_provider, openrouterProvider: localForm.small_openrouter_provider })"
            class="px-2.5 py-1 bg-purple-600/20 hover:bg-purple-600/40 text-purple-300 text-[11px] font-bold rounded-lg border border-purple-600/30 transition-all flex items-center gap-1.5 shrink-0 cursor-pointer"
          >
            <i class="ra ra-player"></i> Test
          </button>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          <div>
            <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Provider</label>
            <select v-model="localForm.small_model_provider" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-purple-500">
              <option v-for="p in availableConstants.llm_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="min-w-0">
            <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Model Selection</label>
            <div class="flex gap-1.5 min-w-0">
              <select
                :value="isModelCustom(localForm.small_model, localForm.small_model_provider) ? 'custom' : localForm.small_model"
                @change="(e) => {
                  const val = (e.target as HTMLSelectElement).value;
                  if(val !== 'custom') localForm.small_model = val;
                  else if(!isModelCustom(localForm.small_model, localForm.small_model_provider)) localForm.small_model = '';
                }"
                class="flex-1 min-w-0 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-purple-500 font-mono truncate"
              >
                <option value="" disabled>-- Please Select --</option>
                <option v-for="m in availableConstants.predefined_llm_models?.[localForm.small_model_provider]" :key="m" :value="m">{{ getModelOptionLabel(localForm.small_model_provider, m) }}</option>
                <option value="custom">-- Custom Model String --</option>
              </select>
              <button
                v-if="isLlmDiscoveryProvider(localForm.small_model_provider)"
                type="button"
                @click="refreshLlmProviderModels(localForm.small_model_provider)"
                :disabled="isLlmProviderLoading(localForm.small_model_provider)"
                class="shrink-0 px-2 py-1 bg-purple-600/20 hover:bg-purple-600/40 text-purple-300 text-xs rounded-lg border border-purple-600/30 transition-all disabled:opacity-50 cursor-pointer"
                title="Fetch models from API"
              >
                <i class="ra ra-recycle"></i>
              </button>
            </div>
          </div>
        </div>

        <div v-if="isModelCustom(localForm.small_model, localForm.small_model_provider) || localForm.small_model === ''">
          <input v-model="localForm.small_model" type="text" maxlength="100" placeholder="Model ID e.g. gpt-4o-mini" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-purple-500 font-mono" />
        </div>

        <div v-if="localForm.small_model_provider === 'openrouter'">
          <input v-model="localForm.small_openrouter_provider" type="text" maxlength="100" placeholder="OpenRouter Provider Routing (e.g. Together, Grok)" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-purple-500 font-mono" />
        </div>

        <div class="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-800/80 text-xs">
          <div class="flex items-center gap-2">
            <span class="text-[10px] font-bold text-slate-400 uppercase">Max Tokens:</span>
            <input v-model.number="localForm.small_max_tokens" type="number" step="1024" min="128" class="w-24 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white outline-none focus:ring-1 focus:ring-purple-500 font-mono" />
          </div>
          <div class="flex items-center gap-2">
            <label class="flex items-center gap-1.5 cursor-pointer text-slate-300 text-xs select-none">
              <input type="checkbox" v-model="localForm.small_enable_thinking" class="rounded bg-slate-950 border-slate-800 text-purple-600 focus:ring-0">
              <span class="text-[11px] font-medium">Thinking Mode</span>
            </label>
            <input v-if="localForm.small_enable_thinking" v-model.number="localForm.small_max_thinking_tokens" type="number" step="1024" min="0" placeholder="Tokens" class="w-20 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white font-mono" />
          </div>
        </div>

        <div v-if="testResults.simple" :class="['p-2.5 rounded-lg text-xs font-medium border animate-fade-in flex items-center gap-2', testResults.simple.status === 'loading' ? 'bg-slate-800 border-slate-700 text-slate-300' : testResults.simple.status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400']">
          <div v-if="testResults.simple.status === 'loading'" class="w-3.5 h-3.5 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div>
          <i v-else :class="testResults.simple.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
          <span>{{ testResults.simple.message }}</span>
        </div>
      </div>

      <!-- 2. COMPLEX MODEL -->
      <div class="p-4 bg-slate-900/90 border border-purple-500/15 rounded-xl shadow-lg space-y-3">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <span class="w-7 h-7 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-300 text-xs">
              <i class="ra ra-feather-wing"></i>
            </span>
            <div>
              <h3 class="text-sm font-bold text-white flex items-center gap-1.5">
                Complex Model
                <span class="text-[10px] font-semibold text-indigo-400 bg-indigo-500/15 px-1.5 py-0.5 rounded border border-indigo-500/30 uppercase tracking-wider">Pass 2: Narration</span>
              </h3>
              <p class="text-[11px] text-slate-400">Rich storytelling, complex world-building, and high-fidelity prose.</p>
            </div>
          </div>
          <button 
            type="button"
            @click="emit('test', { key: 'complex', model: localForm.complex_model, provider: localForm.complex_model_provider, openrouterProvider: localForm.complex_openrouter_provider })"
            class="px-2.5 py-1 bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 text-[11px] font-bold rounded-lg border border-indigo-600/30 transition-all flex items-center gap-1.5 shrink-0 cursor-pointer"
          >
            <i class="ra ra-player"></i> Test
          </button>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          <div>
            <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Provider</label>
            <select v-model="localForm.complex_model_provider" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-indigo-500">
              <option v-for="p in availableConstants.llm_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="min-w-0">
            <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Model Selection</label>
            <div class="flex gap-1.5 min-w-0">
              <select
                :value="isModelCustom(localForm.complex_model, localForm.complex_model_provider) ? 'custom' : localForm.complex_model"
                @change="(e) => {
                  const val = (e.target as HTMLSelectElement).value;
                  if(val !== 'custom') localForm.complex_model = val;
                  else if(!isModelCustom(localForm.complex_model, localForm.complex_model_provider)) localForm.complex_model = '';
                }"
                class="flex-1 min-w-0 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-indigo-500 font-mono truncate"
              >
                <option value="" disabled>-- Please Select --</option>
                <option v-for="m in availableConstants.predefined_llm_models?.[localForm.complex_model_provider]" :key="m" :value="m">{{ getModelOptionLabel(localForm.complex_model_provider, m) }}</option>
                <option value="custom">-- Custom Model String --</option>
              </select>
              <button
                v-if="isLlmDiscoveryProvider(localForm.complex_model_provider)"
                type="button"
                @click="refreshLlmProviderModels(localForm.complex_model_provider)"
                :disabled="isLlmProviderLoading(localForm.complex_model_provider)"
                class="shrink-0 px-2 py-1 bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 text-xs rounded-lg border border-indigo-600/30 transition-all disabled:opacity-50 cursor-pointer"
                title="Fetch models from API"
              >
                <i class="ra ra-recycle"></i>
              </button>
            </div>
          </div>
        </div>

        <div v-if="isModelCustom(localForm.complex_model, localForm.complex_model_provider) || localForm.complex_model === ''">
          <input v-model="localForm.complex_model" type="text" maxlength="100" placeholder="Model ID e.g. gpt-4o" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-indigo-500 font-mono" />
        </div>

        <div v-if="localForm.complex_model_provider === 'openrouter'">
          <input v-model="localForm.complex_openrouter_provider" type="text" maxlength="100" placeholder="OpenRouter Provider Routing (e.g. Together, Grok)" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-indigo-500 font-mono" />
        </div>

        <div class="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-800/80 text-xs">
          <div class="flex items-center gap-2">
            <span class="text-[10px] font-bold text-slate-400 uppercase">Max Tokens:</span>
            <input v-model.number="localForm.complex_max_tokens" type="number" step="1024" min="128" class="w-24 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white outline-none focus:ring-1 focus:ring-indigo-500 font-mono" />
          </div>
          <div class="flex items-center gap-2">
            <label class="flex items-center gap-1.5 cursor-pointer text-slate-300 text-xs select-none">
              <input type="checkbox" v-model="localForm.complex_enable_thinking" class="rounded bg-slate-950 border-slate-800 text-indigo-600 focus:ring-0">
              <span class="text-[11px] font-medium">Thinking Mode</span>
            </label>
            <input v-if="localForm.complex_enable_thinking" v-model.number="localForm.complex_max_thinking_tokens" type="number" step="1024" min="0" placeholder="Tokens" class="w-20 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white font-mono" />
          </div>
        </div>

        <div v-if="testResults.complex" :class="['p-2.5 rounded-lg text-xs font-medium border animate-fade-in flex items-center gap-2', testResults.complex.status === 'loading' ? 'bg-slate-800 border-slate-700 text-slate-300' : testResults.complex.status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400']">
          <div v-if="testResults.complex.status === 'loading'" class="w-3.5 h-3.5 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div>
          <i v-else :class="testResults.complex.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
          <span>{{ testResults.complex.message }}</span>
        </div>
      </div>

      <!-- 3. ADVENTURE GENERATOR MODEL -->
      <div class="p-4 bg-slate-900/90 border border-purple-500/15 rounded-xl shadow-lg space-y-3">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <span class="w-7 h-7 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-300 text-xs">
              <i class="ra ra-world"></i>
            </span>
            <div>
              <h3 class="text-sm font-bold text-white flex items-center gap-1.5">
                Adventure Generator Model
                <span class="text-[10px] font-semibold text-emerald-400 bg-emerald-500/15 px-1.5 py-0.5 rounded border border-emerald-500/30 uppercase tracking-wider">World Creation</span>
              </h3>
              <p class="text-[11px] text-slate-400">Generates complete adventures, blueprints, scenes, and complex manifests.</p>
            </div>
          </div>
          <button 
            type="button"
            @click="emit('test', { key: 'generator', model: localForm.generator_model, provider: localForm.generator_model_provider, openrouterProvider: localForm.generator_openrouter_provider })"
            class="px-2.5 py-1 bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-300 text-[11px] font-bold rounded-lg border border-emerald-600/30 transition-all flex items-center gap-1.5 shrink-0 cursor-pointer"
          >
            <i class="ra ra-player"></i> Test
          </button>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          <div>
            <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Provider</label>
            <select v-model="localForm.generator_model_provider" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-emerald-500">
              <option v-for="p in availableConstants.llm_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="min-w-0">
            <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Model Selection</label>
            <div class="flex gap-1.5 min-w-0">
              <select
                :value="isModelCustom(localForm.generator_model, localForm.generator_model_provider) ? 'custom' : localForm.generator_model"
                @change="(e) => {
                  const val = (e.target as HTMLSelectElement).value;
                  if(val !== 'custom') localForm.generator_model = val;
                  else if(!isModelCustom(localForm.generator_model, localForm.generator_model_provider)) localForm.generator_model = '';
                }"
                class="flex-1 min-w-0 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-emerald-500 font-mono truncate"
              >
                <option value="" disabled>-- Please Select --</option>
                <option v-for="m in availableConstants.predefined_llm_models?.[localForm.generator_model_provider]" :key="m" :value="m">{{ getModelOptionLabel(localForm.generator_model_provider, m) }}</option>
                <option value="custom">-- Custom Model String --</option>
              </select>
              <button
                v-if="isLlmDiscoveryProvider(localForm.generator_model_provider)"
                type="button"
                @click="refreshLlmProviderModels(localForm.generator_model_provider)"
                :disabled="isLlmProviderLoading(localForm.generator_model_provider)"
                class="shrink-0 px-2 py-1 bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-300 text-xs rounded-lg border border-emerald-600/30 transition-all disabled:opacity-50 cursor-pointer"
                title="Fetch models from API"
              >
                <i class="ra ra-recycle"></i>
              </button>
            </div>
          </div>
        </div>

        <div v-if="isModelCustom(localForm.generator_model, localForm.generator_model_provider) || localForm.generator_model === ''">
          <input v-model="localForm.generator_model" type="text" maxlength="100" placeholder="Model ID e.g. gpt-4o" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-emerald-500 font-mono" />
        </div>

        <div v-if="localForm.generator_model_provider === 'openrouter'">
          <input v-model="localForm.generator_openrouter_provider" type="text" maxlength="100" placeholder="OpenRouter Provider Routing (e.g. Together, Grok)" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-emerald-500 font-mono" />
        </div>

        <div class="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-800/80 text-xs">
          <div class="flex items-center gap-2">
            <span class="text-[10px] font-bold text-slate-400 uppercase">Max Tokens:</span>
            <input v-model.number="localForm.generator_max_tokens" type="number" step="1024" min="128" class="w-24 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white outline-none focus:ring-1 focus:ring-emerald-500 font-mono" />
          </div>
          <div class="flex items-center gap-2">
            <label class="flex items-center gap-1.5 cursor-pointer text-slate-300 text-xs select-none">
              <input type="checkbox" v-model="localForm.generator_enable_thinking" class="rounded bg-slate-950 border-slate-800 text-emerald-600 focus:ring-0">
              <span class="text-[11px] font-medium">Thinking Mode</span>
            </label>
            <input v-if="localForm.generator_enable_thinking" v-model.number="localForm.generator_max_thinking_tokens" type="number" step="1024" min="0" placeholder="Tokens" class="w-20 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white font-mono" />
          </div>
        </div>

        <div v-if="testResults.generator" :class="['p-2.5 rounded-lg text-xs font-medium border animate-fade-in flex items-center gap-2', testResults.generator.status === 'loading' ? 'bg-slate-800 border-slate-700 text-slate-300' : testResults.generator.status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400']">
          <div v-if="testResults.generator.status === 'loading'" class="w-3.5 h-3.5 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div>
          <i v-else :class="testResults.generator.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
          <span>{{ testResults.generator.message }}</span>
        </div>
      </div>

      <!-- 4. PLAY AGENT MODEL -->
      <div class="p-4 bg-slate-900/90 border border-purple-500/15 rounded-xl shadow-lg space-y-3">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <span class="w-7 h-7 rounded-lg bg-sky-500/20 border border-sky-500/30 flex items-center justify-center text-sky-300 text-xs">
              <i class="ra ra-player"></i>
            </span>
            <div>
              <h3 class="text-sm font-bold text-white flex items-center gap-1.5">
                Play Agent Model
                <span class="text-[10px] font-semibold text-sky-400 bg-sky-500/15 px-1.5 py-0.5 rounded border border-sky-500/30 uppercase tracking-wider">Autonomous Mode</span>
              </h3>
              <p class="text-[11px] text-slate-400">Autonomous gameplay testing and engine stress-testing agent.</p>
            </div>
          </div>
          <button 
            type="button"
            @click="emit('test', { key: 'play_agent', model: localForm.play_agent_model, provider: localForm.play_agent_model_provider, openrouterProvider: localForm.play_agent_openrouter_provider })"
            class="px-2.5 py-1 bg-sky-600/20 hover:bg-sky-600/40 text-sky-300 text-[11px] font-bold rounded-lg border border-sky-600/30 transition-all flex items-center gap-1.5 shrink-0 cursor-pointer"
          >
            <i class="ra ra-player"></i> Test
          </button>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          <div>
            <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Provider</label>
            <select v-model="localForm.play_agent_model_provider" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-sky-500">
              <option v-for="p in availableConstants.llm_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="min-w-0">
            <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Model Selection</label>
            <div class="flex gap-1.5 min-w-0">
              <select
                :value="isModelCustom(localForm.play_agent_model, localForm.play_agent_model_provider) ? 'custom' : localForm.play_agent_model"
                @change="(e) => {
                  const val = (e.target as HTMLSelectElement).value;
                  if(val !== 'custom') localForm.play_agent_model = val;
                  else if(!isModelCustom(localForm.play_agent_model, localForm.play_agent_model_provider)) localForm.play_agent_model = '';
                }"
                class="flex-1 min-w-0 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-sky-500 font-mono truncate"
              >
                <option value="" disabled>-- Please Select --</option>
                <option v-for="m in availableConstants.predefined_llm_models?.[localForm.play_agent_model_provider]" :key="m" :value="m">{{ getModelOptionLabel(localForm.play_agent_model_provider, m) }}</option>
                <option value="custom">-- Custom Model String --</option>
              </select>
              <button
                v-if="isLlmDiscoveryProvider(localForm.play_agent_model_provider)"
                type="button"
                @click="refreshLlmProviderModels(localForm.play_agent_model_provider)"
                :disabled="isLlmProviderLoading(localForm.play_agent_model_provider)"
                class="shrink-0 px-2 py-1 bg-sky-600/20 hover:bg-sky-600/40 text-sky-300 text-xs rounded-lg border border-sky-600/30 transition-all disabled:opacity-50 cursor-pointer"
                title="Fetch models from API"
              >
                <i class="ra ra-recycle"></i>
              </button>
            </div>
          </div>
        </div>

        <div v-if="isModelCustom(localForm.play_agent_model, localForm.play_agent_model_provider) || localForm.play_agent_model === ''">
          <input v-model="localForm.play_agent_model" type="text" maxlength="100" placeholder="Model ID e.g. gpt-4o-mini" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-sky-500 font-mono" />
        </div>

        <div v-if="localForm.play_agent_model_provider === 'openrouter'">
          <input v-model="localForm.play_agent_openrouter_provider" type="text" maxlength="100" placeholder="OpenRouter Provider Routing (e.g. Together, Grok)" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-sky-500 font-mono" />
        </div>

        <div class="flex items-center justify-between gap-3 p-2.5 bg-amber-500/10 rounded-lg border border-amber-500/25">
          <div>
            <div class="text-xs font-bold text-amber-200 flex items-center gap-1.5">
              <i class="ra ra-perspective-dice-random text-amber-400"></i> Monkey Mode Default
            </div>
            <p class="text-[11px] text-amber-300/70">If enabled, /agent on starts directly in chaos-testing mode to stress-test engine robustness.</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer shrink-0">
            <input type="checkbox" v-model="localForm.play_agent_monkey_mode" class="sr-only peer">
            <div class="w-9 h-5 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-amber-500 peer-checked:after:bg-white"></div>
          </label>
        </div>

        <div v-if="testResults.play_agent" :class="['p-2.5 rounded-lg text-xs font-medium border animate-fade-in flex items-center gap-2', testResults.play_agent.status === 'loading' ? 'bg-slate-800 border-slate-700 text-slate-300' : testResults.play_agent.status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400']">
          <div v-if="testResults.play_agent.status === 'loading'" class="w-3.5 h-3.5 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div>
          <i v-else :class="testResults.play_agent.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
          <span>{{ testResults.play_agent.message }}</span>
        </div>
      </div>

      <!-- 5. HISTORY COMPRESSION & COMPACTING CONFIGURATION -->
      <div class="p-4 bg-slate-900/90 border border-purple-500/20 rounded-xl shadow-lg space-y-3.5">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <span class="w-7 h-7 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-300 text-xs">
              <i class="ra ra-quill-ink"></i>
            </span>
            <div>
              <h3 class="text-sm font-bold text-white flex items-center gap-1.5">
                History Compression & Memory
                <span class="text-[10px] font-semibold text-amber-400 bg-amber-500/15 px-1.5 py-0.5 rounded border border-amber-500/30 uppercase tracking-wider">Chronicle & Compacting</span>
              </h3>
              <p class="text-[11px] text-slate-400">Compresses older gameplay turns into an ongoing English chronicle summary.</p>
            </div>
          </div>
          <button 
            type="button"
            @click="emit('test', { key: 'compression', model: localForm.compression_model, provider: localForm.compression_model_provider, openrouterProvider: localForm.compression_openrouter_provider })"
            :disabled="!localForm.compression_model"
            class="px-2.5 py-1 bg-amber-600/20 hover:bg-amber-600/40 text-amber-300 text-[11px] font-bold rounded-lg border border-amber-600/30 transition-all flex items-center gap-1.5 shrink-0 disabled:opacity-40 cursor-pointer"
          >
            <i class="ra ra-player"></i> Test
          </button>
        </div>

        <!-- COMPACTING CONFIGURATION BAR (Toggle & Slider) -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 p-3 bg-slate-950/60 rounded-xl border border-white/5">
          <!-- Toggle Compacting -->
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="flex items-center gap-1.5">
                <label class="text-xs font-bold text-slate-200 cursor-pointer" @click="localForm.enable_history_compression = !localForm.enable_history_compression">
                  Automatic Compacting
                </label>
                <span :class="['text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider', localForm.enable_history_compression ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-slate-800 text-slate-400 border border-slate-700']">
                  {{ localForm.enable_history_compression ? 'Active' : 'Inactive' }}
                </span>
              </div>
              <p class="text-[11px] text-slate-400 mt-0.5">Automatically compresses older turns for narrator continuity.</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer shrink-0">
              <input type="checkbox" v-model="localForm.enable_history_compression" class="sr-only peer">
              <div class="w-9 h-5 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-amber-500 peer-checked:after:bg-white"></div>
            </label>
          </div>

          <!-- Turns before Compacting Slider & Number Input -->
          <div class="space-y-1.5">
            <div class="flex items-center justify-between">
              <label class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Turns before Compacting</label>
              <div class="flex items-center gap-1 bg-black/50 border border-white/10 px-2 py-0.5 rounded-md">
                <input
                  type="number"
                  min="1"
                  max="100"
                  :value="localForm.turns_before_compacting"
                  @input="handleTurnsInput"
                  class="w-8 bg-transparent text-center text-white font-mono font-bold text-xs focus:outline-none"
                />
                <span class="text-[10px] font-bold text-amber-400">Turns</span>
              </div>
            </div>
            <input
              type="range"
              min="1"
              max="100"
              :value="localForm.turns_before_compacting"
              @input="handleTurnsInput"
              class="w-full accent-amber-500 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
            />
            <div class="flex justify-between text-[9px] text-slate-500 uppercase tracking-wider font-mono">
              <span>1</span>
              <span class="text-amber-400 font-bold">10 Default</span>
              <span>100</span>
            </div>
          </div>
        </div>

        <!-- WARNING: Compacting enabled, but no model chosen -->
        <div v-if="isCompressionModelMissingWarning" class="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-2.5 text-amber-300 animate-fade-in">
          <i class="ra ra-warning text-base shrink-0 mt-0.5 text-amber-400"></i>
          <div class="text-xs leading-relaxed">
            <strong class="font-bold text-amber-200">No Compression Model Selected:</strong>
            Compacting is enabled, but no dedicated model is chosen. TaleWeaver will fall back to the Simple Model. A dedicated model is recommended for optimal chronicle summaries.
          </div>
        </div>

        <!-- MODEL SELECTION -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          <div>
            <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Provider</label>
            <select v-model="localForm.compression_model_provider" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-amber-500">
              <option v-for="p in availableConstants.llm_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="min-w-0">
            <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Model Selection</label>
            <div class="flex gap-1.5 min-w-0">
              <select
                :value="isModelCustom(localForm.compression_model, localForm.compression_model_provider) ? 'custom' : localForm.compression_model"
                @change="(e) => {
                  const val = (e.target as HTMLSelectElement).value;
                  if(val !== 'custom') localForm.compression_model = val;
                  else if(!isModelCustom(localForm.compression_model, localForm.compression_model_provider)) localForm.compression_model = '';
                }"
                class="flex-1 min-w-0 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-amber-500 font-mono truncate"
              >
                <option value="">-- No Dedicated Model (Fallback) --</option>
                <option v-for="m in availableConstants.predefined_llm_models?.[localForm.compression_model_provider]" :key="m" :value="m">{{ getModelOptionLabel(localForm.compression_model_provider, m) }}</option>
                <option value="custom">-- Custom Model String --</option>
              </select>
              <button
                v-if="isLlmDiscoveryProvider(localForm.compression_model_provider)"
                type="button"
                @click="refreshLlmProviderModels(localForm.compression_model_provider)"
                :disabled="isLlmProviderLoading(localForm.compression_model_provider)"
                class="shrink-0 px-2 py-1 bg-amber-600/20 hover:bg-amber-600/40 text-amber-300 text-xs rounded-lg border border-amber-600/30 transition-all disabled:opacity-50 cursor-pointer"
                title="Fetch models from API"
              >
                <i class="ra ra-recycle"></i>
              </button>
            </div>
          </div>
        </div>

        <div v-if="isModelCustom(localForm.compression_model, localForm.compression_model_provider)">
          <input v-model="localForm.compression_model" type="text" maxlength="100" placeholder="Model ID e.g. gpt-4o-mini" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-amber-500 font-mono" />
        </div>

        <div v-if="localForm.compression_model_provider === 'openrouter'">
          <input v-model="localForm.compression_openrouter_provider" type="text" maxlength="100" placeholder="OpenRouter Provider Routing (e.g. Together, Grok)" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-amber-500 font-mono" />
        </div>

        <div class="flex items-center gap-2 pt-2 border-t border-slate-800/80 text-xs">
          <span class="text-[10px] font-bold text-slate-400 uppercase">Max Tokens (Summary):</span>
          <input v-model.number="localForm.compression_max_tokens" type="number" min="256" max="32768" class="w-24 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white outline-none focus:ring-1 focus:ring-amber-500 font-mono" />
        </div>

        <div v-if="testResults.compression" :class="['p-2.5 rounded-lg text-xs font-medium border animate-fade-in flex items-center gap-2', testResults.compression.status === 'loading' ? 'bg-slate-800 border-slate-700 text-slate-300' : testResults.compression.status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400']">
          <div v-if="testResults.compression.status === 'loading'" class="w-3.5 h-3.5 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div>
          <i v-else :class="testResults.compression.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
          <span>{{ testResults.compression.message }}</span>
        </div>
      </div>

      <!-- PROVIDER ENDPOINTS (OLLAMA / MINIMAX - NO "Global Infrastructure" label) -->
      <div v-if="hasOllamaProviderSelected || hasMinimaxProviderSelected" class="space-y-2.5 pt-2 border-t border-slate-800">
        <!-- Ollama Endpoint -->
        <div v-if="hasOllamaProviderSelected" class="p-3 bg-slate-900/70 border border-purple-500/20 rounded-xl space-y-2">
          <div class="flex items-center justify-between gap-3">
            <label class="text-xs font-bold text-slate-300 flex items-center gap-1.5">
              <i class="ra ra-reactor text-purple-400"></i> Ollama API Base URL
            </label>
            <button
              type="button"
              @click="refreshOllamaModels"
              class="px-2.5 py-1 bg-purple-600/20 hover:bg-purple-600/40 text-purple-300 text-[11px] font-bold rounded-lg border border-purple-600/30 transition-all flex items-center gap-1 cursor-pointer"
            >
              <i class="ra ra-recycle"></i>
              {{ isLoadingOllamaModels ? 'Loading...' : 'Fetch Models' }}
            </button>
          </div>
          <input v-model="localForm.ollama_url" type="text" placeholder="http://localhost:11434" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-purple-500 font-mono" />
          <div v-if="!isLoadingOllamaModels && ollamaModelCount === 0" class="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px] leading-relaxed">
            No local Ollama models found. Please download a model first via terminal (e.g. <code class="bg-black/40 px-1 py-0.5 rounded text-amber-200">ollama pull llama3.2</code>) and click Fetch Models.
          </div>
        </div>

        <!-- MiniMax Endpoint -->
        <div v-if="hasMinimaxProviderSelected" class="p-3 bg-slate-900/70 border border-purple-500/20 rounded-xl space-y-2">
          <div class="flex items-center justify-between gap-3">
            <label class="text-xs font-bold text-slate-300 flex items-center gap-1.5">
              <i class="ra ra-reactor text-purple-400"></i> MiniMax API Base URL
            </label>
            <button
              type="button"
              @click="refreshMinimaxModels"
              class="px-2.5 py-1 bg-purple-600/20 hover:bg-purple-600/40 text-purple-300 text-[11px] font-bold rounded-lg border border-purple-600/30 transition-all flex items-center gap-1 cursor-pointer"
            >
              <i class="ra ra-recycle"></i>
              {{ isLoadingMinimaxModels ? 'Loading...' : 'Fetch Models' }}
            </button>
          </div>
          <input v-model="localForm.minimax_url" type="text" placeholder="https://api.minimax.chat/v1" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:ring-1 focus:ring-purple-500 font-mono" />
          <div v-if="!isLoadingMinimaxModels && minimaxModelCount === 0" class="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px] leading-relaxed">
            No MiniMax models found. Please verify your API key in Provider Keys and check the configured URL.
          </div>
        </div>
      </div>

      <!-- Save Button -->
      <div class="pt-2">
        <button 
          type="button" 
          @click="handleSave" 
          :disabled="isSubmitting" 
          class="w-full py-3 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-purple-900/30 disabled:opacity-50 flex items-center justify-center gap-2 cursor-pointer"
        >
          <i v-if="isSubmitting" class="ra ra-recycle animate-spin"></i>
          <i v-else class="ra ra-save"></i>
          {{ isSubmitting ? 'Saving...' : 'Save Intelligence Settings' }}
        </button>
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
