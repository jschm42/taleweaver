<script setup lang="ts">
import { ref, watch, computed } from 'vue'

const props = defineProps<{
  llmForm: any
  availableConstants: any
  configuredKeys: any
  isSubmitting: boolean
  isLoadingOllamaModels: boolean
  testResults: any
}>()

const missingProviders = computed(() => {
  const providers = new Set([
    localForm.value.small_model_provider,
    localForm.value.complex_model_provider,
    localForm.value.generator_model_provider,
    localForm.value.play_agent_model_provider,
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
  (e: 'test', payload: { key: string, model: string, provider: string }): void
  (e: 'refreshOllamaModels', ollamaUrl?: string): void
  (e: 'switchSection', section: string): void
}>()

const localForm = ref({ ...props.llmForm })

watch(() => props.llmForm, (newVal) => {
  localForm.value = { ...newVal }
}, { deep: true })

const isModelCustom = (model: string, provider: string) => {
  if (!model) return false
  const predefined = props.availableConstants.predefined_llm_models[provider]
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
    return (props.availableConstants.predefined_llm_models[provider] || [])
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

const hasOllamaProviderSelected = computed(() => (
  localForm.value.small_model_provider === 'ollama'
  || localForm.value.complex_model_provider === 'ollama'
  || localForm.value.generator_model_provider === 'ollama'
  || localForm.value.play_agent_model_provider === 'ollama'
))

const ollamaModelCount = computed(() => {
  const models = props.availableConstants?.predefined_llm_models?.ollama
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

watch(localForm, () => {
  // Sync back to parent if needed, but since we have a save button, maybe we just emit the whole form on save.
}, { deep: true })

const handleSave = () => {
  emit('save', localForm.value)
}
</script>

<template>
  <div class="space-y-8 animate-fade-in">
    <div>
      <h1 class="text-4xl font-extrabold text-white mb-2">Intelligence Routing</h1>
      <p class="text-slate-400">Configure how the game handles simple narrative vs complex mechanics.</p>
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
      
      <!-- SIMPLE MODEL -->
      <div class="space-y-4 p-6 bg-slate-950/50 rounded-2xl border border-purple-500/10">
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-lg font-bold text-purple-400 flex items-center gap-2">
            <i class="ra ra-gear-hammer"></i> Simple Model (Mechanics)
          </h3>
          <button 
            @click="emit('test', { key: 'simple', model: localForm.small_model, provider: localForm.small_model_provider })"
            class="px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/40 text-purple-300 text-xs font-bold rounded-lg border border-purple-600/30 transition-all flex items-center gap-2"
          >
            <i class="ra ra-gear-hammer"></i> Test Connection
          </button>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Provider</label>
            <select v-model="localForm.small_model_provider" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50">
              <option v-for="p in availableConstants.llm_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Model Selection</label>
            <select 
              :value="isModelCustom(localForm.small_model, localForm.small_model_provider) ? 'custom' : localForm.small_model"
              @change="(e) => { 
                const val = (e.target as HTMLSelectElement).value; 
                if(val !== 'custom') localForm.small_model = val;
                else if(!isModelCustom(localForm.small_model, localForm.small_model_provider)) localForm.small_model = '';
              }"
              class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50 font-mono"
            >
              <option value="" disabled>-- Please Select --</option>
              <option v-for="m in availableConstants.predefined_llm_models[localForm.small_model_provider]" :key="m" :value="m">{{ getModelOptionLabel(localForm.small_model_provider, m) }}</option>
              <option value="custom">-- Custom Model String --</option>
            </select>
          </div>
        </div>

        <div v-if="isModelCustom(localForm.small_model, localForm.small_model_provider) || localForm.small_model === ''" class="space-y-2 animate-fade-in">
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Custom Model ID</label>
          <input v-model="localForm.small_model" type="text" maxlength="100" placeholder="e.g. gpt-4o-mini" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50 font-mono" />
        </div>
        <p class="text-xxs text-slate-500">Efficient logic for rule enforcement and mechanical reasoning (Pass 1).</p>

        <div v-if="testResults.simple" :class="['p-4 rounded-xl text-sm font-medium border animate-fade-in', testResults.simple.status === 'loading' ? 'bg-slate-800 border-slate-700 text-slate-300' : testResults.simple.status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400']">
           <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <div v-if="testResults.simple.status === 'loading'" class="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div>
                <i v-else :class="testResults.simple.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
                {{ testResults.simple.message }}
              </div>
           </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-slate-900">
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Max Tokens</label>
            <input v-model.number="localForm.small_max_tokens" type="number" step="1024" min="128" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50" />
          </div>
          <div class="space-y-2">
            <div class="flex items-center justify-between mb-2">
              <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Thinking Mode</label>
              <label class="relative inline-flex items-center cursor-pointer scale-75 origin-right">
                <input type="checkbox" v-model="localForm.small_enable_thinking" class="sr-only peer">
                <div class="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600 peer-checked:after:bg-white"></div>
              </label>
            </div>
            <input v-if="localForm.small_enable_thinking" v-model.number="localForm.small_max_thinking_tokens" type="number" step="1024" min="0" placeholder="Thinking tokens" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50" />
          </div>
        </div>
      </div>

      <!-- COMPLEX MODEL -->
      <div class="space-y-4 p-6 bg-slate-950/50 rounded-2xl border border-purple-500/10">
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-lg font-bold text-purple-400 flex items-center gap-2">
            <i class="ra ra-feather-wing"></i> Complex Model (Narratives & World Gen)
          </h3>
          <button 
            @click="emit('test', { key: 'complex', model: localForm.complex_model, provider: localForm.complex_model_provider })"
            class="px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/40 text-purple-300 text-xs font-bold rounded-lg border border-purple-600/30 transition-all flex items-center gap-2"
          >
            <i class="ra ra-gear-hammer"></i> Test Connection
          </button>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Provider</label>
            <select v-model="localForm.complex_model_provider" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50">
              <option v-for="p in availableConstants.llm_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Model Selection</label>
            <select 
              :value="isModelCustom(localForm.complex_model, localForm.complex_model_provider) ? 'custom' : localForm.complex_model"
              @change="(e) => { 
                const val = (e.target as HTMLSelectElement).value; 
                if(val !== 'custom') localForm.complex_model = val;
                else if(!isModelCustom(localForm.complex_model, localForm.complex_model_provider)) localForm.complex_model = '';
              }"
              class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50 font-mono"
            >
              <option value="" disabled>-- Please Select --</option>
              <option v-for="m in availableConstants.predefined_llm_models[localForm.complex_model_provider]" :key="m" :value="m">{{ getModelOptionLabel(localForm.complex_model_provider, m) }}</option>
              <option value="custom">-- Custom Model String --</option>
            </select>
          </div>
        </div>

        <div v-if="isModelCustom(localForm.complex_model, localForm.complex_model_provider) || localForm.complex_model === ''" class="space-y-2 animate-fade-in">
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Custom Model ID</label>
          <input v-model="localForm.complex_model" type="text" maxlength="100" placeholder="e.g. gpt-4o" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50 font-mono" />
        </div>
        <p class="text-xxs text-slate-500">Rich storytelling, complex world-building, and high-fidelity prose (Pass 2).</p>

        <div v-if="testResults.complex" :class="['p-4 rounded-xl text-sm font-medium border animate-fade-in', testResults.complex.status === 'loading' ? 'bg-slate-800 border-slate-700 text-slate-300' : testResults.complex.status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400']">
           <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <div v-if="testResults.complex.status === 'loading'" class="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div>
                <i v-else :class="testResults.complex.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
                {{ testResults.complex.message }}
              </div>
           </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-slate-900">
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Max Tokens</label>
            <input v-model.number="localForm.complex_max_tokens" type="number" step="1024" min="128" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50" />
          </div>
          <div class="space-y-2">
            <div class="flex items-center justify-between mb-2">
              <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Thinking Mode</label>
              <label class="relative inline-flex items-center cursor-pointer scale-75 origin-right">
                <input type="checkbox" v-model="localForm.complex_enable_thinking" class="sr-only peer">
                <div class="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600 peer-checked:after:bg-white"></div>
              </label>
            </div>
            <input v-if="localForm.complex_enable_thinking" v-model.number="localForm.complex_max_thinking_tokens" type="number" step="1024" min="0" placeholder="Thinking tokens" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50" />
          </div>
        </div>
      </div>

      <!-- GENERATOR MODEL -->
      <div class="space-y-4 p-6 bg-slate-950/50 rounded-2xl border border-purple-500/10 shadow-inner">
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-lg font-bold text-purple-400 flex items-center gap-2">
            <i class="ra ra-world"></i> Adventure Generator Model
          </h3>
          <button 
            @click="emit('test', { key: 'generator', model: localForm.generator_model, provider: localForm.generator_model_provider })"
            class="px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/40 text-purple-300 text-xs font-bold rounded-lg border border-purple-600/30 transition-all flex items-center gap-2"
          >
            <i class="ra ra-gear-hammer"></i> Test Connection
          </button>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Provider</label>
            <select v-model="localForm.generator_model_provider" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50">
              <option v-for="p in availableConstants.llm_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Model Selection</label>
            <select 
              :value="isModelCustom(localForm.generator_model, localForm.generator_model_provider) ? 'custom' : localForm.generator_model"
              @change="(e) => { 
                const val = (e.target as HTMLSelectElement).value; 
                if(val !== 'custom') localForm.generator_model = val;
                else if(!isModelCustom(localForm.generator_model, localForm.generator_model_provider)) localForm.generator_model = '';
              }"
              class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50 font-mono"
            >
              <option value="" disabled>-- Please Select --</option>
              <option v-for="m in availableConstants.predefined_llm_models[localForm.generator_model_provider]" :key="m" :value="m">{{ getModelOptionLabel(localForm.generator_model_provider, m) }}</option>
              <option value="custom">-- Custom Model String --</option>
            </select>
          </div>
        </div>

        <div v-if="isModelCustom(localForm.generator_model, localForm.generator_model_provider) || localForm.generator_model === ''" class="space-y-2 animate-fade-in">
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Custom Model ID</label>
          <input v-model="localForm.generator_model" type="text" maxlength="100" placeholder="e.g. gpt-4o" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50 font-mono" />
        </div>
        <p class="text-xxs text-slate-500">Highest reasoning models for creating complete adventures, logic blueprints and complex manifests (World Generation).</p>

        <div v-if="testResults.generator" :class="['p-4 rounded-xl text-sm font-medium border animate-fade-in', testResults.generator.status === 'loading' ? 'bg-slate-800 border-slate-700 text-slate-300' : testResults.generator.status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400']">
           <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <div v-if="testResults.generator.status === 'loading'" class="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div>
                <i v-else :class="testResults.generator.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
                {{ testResults.generator.message }}
              </div>
           </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-slate-900">
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Max Tokens</label>
            <input v-model.number="localForm.generator_max_tokens" type="number" step="1024" min="128" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50" />
          </div>
          <div class="space-y-2">
            <div class="flex items-center justify-between mb-2">
              <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Thinking Mode</label>
              <label class="relative inline-flex items-center cursor-pointer scale-75 origin-right">
                <input type="checkbox" v-model="localForm.generator_enable_thinking" class="sr-only peer">
                <div class="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600 peer-checked:after:bg-white"></div>
              </label>
            </div>
            <input v-if="localForm.generator_enable_thinking" v-model.number="localForm.generator_max_thinking_tokens" type="number" step="1024" min="0" placeholder="Thinking tokens" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50" />
          </div>
        </div>
      </div>

      <!-- GLOBAL LLM SETTINGS -->
      <div class="space-y-4 p-6 bg-slate-950/50 rounded-2xl border border-purple-500/10 shadow-inner">
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-lg font-bold text-purple-400 flex items-center gap-2">
            <i class="ra ra-player"></i> Play Agent Model (Autonomous Gameplay)
          </h3>
          <button
            @click="emit('test', { key: 'play_agent', model: localForm.play_agent_model, provider: localForm.play_agent_model_provider })"
            class="px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/40 text-purple-300 text-xs font-bold rounded-lg border border-purple-600/30 transition-all flex items-center gap-2"
          >
            <i class="ra ra-gear-hammer"></i> Test Connection
          </button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Provider</label>
            <select v-model="localForm.play_agent_model_provider" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50">
              <option v-for="p in availableConstants.llm_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Model Selection</label>
            <select
              :value="isModelCustom(localForm.play_agent_model, localForm.play_agent_model_provider) ? 'custom' : localForm.play_agent_model"
              @change="(e) => {
                const val = (e.target as HTMLSelectElement).value;
                if (val !== 'custom') localForm.play_agent_model = val;
                else if (!isModelCustom(localForm.play_agent_model, localForm.play_agent_model_provider)) localForm.play_agent_model = '';
              }"
              class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50 font-mono"
            >
              <option value="" disabled>-- Please Select --</option>
              <option v-for="m in availableConstants.predefined_llm_models[localForm.play_agent_model_provider]" :key="m" :value="m">{{ getModelOptionLabel(localForm.play_agent_model_provider, m) }}</option>
              <option value="custom">-- Custom Model String --</option>
            </select>
          </div>
        </div>

        <div v-if="isModelCustom(localForm.play_agent_model, localForm.play_agent_model_provider) || localForm.play_agent_model === ''" class="space-y-2 animate-fade-in">
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Custom Model ID</label>
          <input v-model="localForm.play_agent_model" type="text" maxlength="100" placeholder="e.g. gpt-4o-mini" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50 font-mono" />
        </div>

        <p class="text-xxs text-slate-500">Used when Autonomous Agent Mode is active. Falls back to the Simple Model if left empty.</p>

        <div class="pt-4 border-t border-slate-900">
          <div class="flex items-start justify-between gap-4 p-4 bg-amber-500/10 rounded-xl border border-amber-500/30">
            <div>
              <label class="block text-sm font-semibold text-amber-200">Monkey Mode Default</label>
              <p class="text-xxs text-amber-300/80 mt-1">
                If enabled, /agent on starts directly in chaos-testing mode. The play-agent will intentionally try invalid,
                nonsensical, or rule-breaking actions to stress-test engine robustness.
              </p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" v-model="localForm.play_agent_monkey_mode" class="sr-only peer">
              <div class="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-500 peer-checked:after:bg-white"></div>
            </label>
          </div>
        </div>

        <div v-if="testResults.play_agent" :class="['p-4 rounded-xl text-sm font-medium border animate-fade-in', testResults.play_agent.status === 'loading' ? 'bg-slate-800 border-slate-700 text-slate-300' : testResults.play_agent.status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400']">
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <div v-if="testResults.play_agent.status === 'loading'" class="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div>
              <i v-else :class="testResults.play_agent.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
              {{ testResults.play_agent.message }}
            </div>
          </div>
        </div>
      </div>

      <div class="pt-6 border-t border-slate-800 space-y-6">
        <h4 class="text-xs font-black uppercase tracking-[0.2em] text-purple-400">Global Infrastructure</h4>
        
        <div class="space-y-4">
          <div v-if="localForm.small_model_provider === 'ollama' || localForm.complex_model_provider === 'ollama' || localForm.generator_model_provider === 'ollama' || localForm.play_agent_model_provider === 'ollama'" class="space-y-2 p-4 bg-purple-500/5 rounded-xl border border-purple-500/20">
            <div class="flex items-center justify-between gap-3">
              <label class="block text-sm font-semibold text-slate-300">Ollama API Base URL</label>
              <button
                type="button"
                @click="refreshOllamaModels"
                class="px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/40 text-purple-300 text-xs font-bold rounded-lg border border-purple-600/30 transition-all"
              >
                {{ isLoadingOllamaModels ? 'Loading models...' : 'Refresh Models' }}
              </button>
            </div>
            <input v-model="localForm.ollama_url" type="text" placeholder="http://localhost:11434" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50 font-mono" />
            <p class="text-xxs text-slate-500">Local endpoint used for local model execution. The model lists above show installed Ollama models.</p>
            <div v-if="!isLoadingOllamaModels && ollamaModelCount === 0" class="mt-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs leading-relaxed">
              No local Ollama models were found for this URL. Download one first (for example: ollama pull llama3.2), then click Refresh Models.
            </div>
          </div>
        </div>
      </div>

      <button type="button" @click="handleSave" :disabled="isSubmitting" class="w-full py-4 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-xl transition-all shadow-lg disabled:opacity-50">
         {{ isSubmitting ? 'Optimizing...' : 'Update Intelligence Paths' }}
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
