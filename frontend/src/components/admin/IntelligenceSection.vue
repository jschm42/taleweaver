<script setup lang="ts">
import { ref, watch, computed } from 'vue'

const props = defineProps<{
  llmForm: any
  availableConstants: any
  configuredKeys: Record<string, { masked: string; is_env: boolean }>
  isSubmitting: boolean
  isLoadingOllamaModels: boolean
  isLoadingMinimaxModels: boolean
  isLoadingLlmModels?: Record<string, boolean>
  testResults: Record<string, { status: string; message: string }>
}>()

const emit = defineEmits<{
  (e: 'save', payload: any): void
  (e: 'test', payload: { key: string; model: string; provider: string; openrouterProvider?: string }): void
  (e: 'refreshOllamaModels', ollamaUrl?: string): void
  (e: 'refreshMinimaxModels', minimaxUrl?: string): void
  (e: 'refreshLlmModels', provider: string, apiBase?: string): void
  (e: 'switchSection', section: string): void
}>()

const normalizeLocalForm = (data: any) => ({
  ...data,
  turns_before_compacting: typeof data?.turns_before_compacting === 'number' ? data.turns_before_compacting : 10,
  enable_history_compression: typeof data?.enable_history_compression === 'boolean' ? data.enable_history_compression : true,
  small_max_tokens: typeof data?.small_max_tokens === 'number' ? data.small_max_tokens : 12288,
  complex_max_tokens: typeof data?.complex_max_tokens === 'number' ? data.complex_max_tokens : 24576,
  generator_max_tokens: typeof data?.generator_max_tokens === 'number' ? data.generator_max_tokens : 32768,
  compression_max_tokens: typeof data?.compression_max_tokens === 'number' ? data.compression_max_tokens : 4096,
  play_agent_allow_walkthrough: typeof data?.play_agent_allow_walkthrough === 'boolean' ? data.play_agent_allow_walkthrough : true,
  play_agent_monkey_mode: typeof data?.play_agent_monkey_mode === 'boolean' ? data.play_agent_monkey_mode : false,
  play_agent_personality: data?.play_agent_personality || 'casual',
  play_agent_custom_personality: data?.play_agent_custom_personality || '',
})

const localForm = ref(normalizeLocalForm(props.llmForm))

watch(() => props.llmForm, (newVal) => {
  localForm.value = normalizeLocalForm(newVal)
}, { deep: true })

// Active sub-tab filter
type TabFilter = 'all' | 'core' | 'world' | 'aux' | 'endpoints'
const activeTab = ref<TabFilter>('all')

// Accordion / expanded advanced settings state per pass
const expandedAdvanced = ref<Record<string, boolean>>({
  small: false,
  complex: false,
  generator: false,
  play_agent: false,
  compression: false,
})

const toggleAdvanced = (key: string) => {
  expandedAdvanced.value[key] = !expandedAdvanced.value[key]
}

// Check missing keys
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
    if (p && p !== 'ollama' && !props.configuredKeys?.[p]) {
      missing.push(p)
    }
  }
  return missing
})

const isModelCustom = (model: string, provider: string) => {
  if (!model) return false
  const predefined = props.availableConstants?.predefined_llm_models?.[provider]
  if (!predefined) return true
  return !predefined.includes(model)
}

const getModelOptionLabel = (_provider: string, model: string) => model

const getProviderName = (id: string) => {
  return props.availableConstants?.llm_providers?.find((p: any) => p.id === id)?.name || id
}

const isProviderConfigured = (providerId: string) => {
  if (providerId === 'ollama') return true
  return Boolean(props.configuredKeys?.[providerId])
}

const resolveModelOnProviderChange = (
  currentModel: string,
  newProvider: string,
  oldProvider: string | undefined
) => {
  const getPredefined = (provider: string | undefined) => {
    if (!provider) return [] as string[]
    return (props.availableConstants?.predefined_llm_models?.[provider] || [])
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

const isCompressionModelMissingWarning = computed(() => {
  return !!localForm.value.enable_history_compression && !localForm.value.compression_model?.trim()
})

const handleTurnsInput = (e: Event) => {
  const val = Number((e.target as HTMLInputElement).value)
  if (!isNaN(val)) {
    localForm.value.turns_before_compacting = Math.min(100, Math.max(1, val))
  }
}

// Quick Sync Action: Copy Pass 1 Provider and Model to other passes
const syncFromPass1 = () => {
  const p = localForm.value.small_model_provider
  const m = localForm.value.small_model
  localForm.value.complex_model_provider = p
  localForm.value.complex_model = m
  localForm.value.generator_model_provider = p
  localForm.value.generator_model = m
  localForm.value.play_agent_model_provider = p
  localForm.value.play_agent_model = m
  localForm.value.compression_model_provider = p
  localForm.value.compression_model = m
}

const handleSave = () => {
  emit('save', localForm.value)
}

// Trigger test with proper args
const triggerTest = (passKey: string, model: string, provider: string, openrouterProvider?: string) => {
  emit('test', {
    key: passKey,
    model,
    provider,
    openrouterProvider
  })
}
</script>

<template>
  <div class="space-y-6 animate-fade-in max-w-5xl">
    <!-- Header with Quick Sync & Save -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
          <i class="ra ra-brain text-purple-400"></i>
          Intelligence Routing
        </h1>
        <p class="text-slate-400 text-sm mt-1">
          Assign AI models to game loops: rules validation, storytelling, world creation, and memory.
        </p>
      </div>

      <div class="flex items-center gap-3 self-start sm:self-auto">
        <button
          type="button"
          @click="syncFromPass1"
          class="px-3.5 py-2 bg-slate-900 border border-purple-500/30 hover:border-purple-500/60 text-purple-300 text-xs font-bold rounded-xl transition-all flex items-center gap-2"
          title="Apply Pass 1 Provider & Model to all other passes"
        >
          <i class="ra ra-cycle"></i>
          <span>Sync from Pass 1</span>
        </button>

        <button
          type="button"
          @click="handleSave"
          :disabled="isSubmitting"
          class="px-5 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-purple-900/30 disabled:opacity-50 flex items-center gap-2 cursor-pointer"
        >
          <i v-if="isSubmitting" class="ra ra-recycle animate-spin"></i>
          <i v-else class="ra ra-save"></i>
          <span>{{ isSubmitting ? 'Saving...' : 'Save Routing' }}</span>
        </button>
      </div>
    </div>

    <!-- API KEY WARNING -->
    <div v-if="missingProviders.length > 0" class="p-4 bg-amber-500/10 border border-amber-500/30 rounded-2xl flex items-start gap-3">
      <div class="p-2.5 bg-amber-500/20 rounded-xl text-amber-400 shrink-0">
        <i class="ra ra-warning text-lg"></i>
      </div>
      <div class="min-w-0">
        <h4 class="text-xs font-bold text-amber-400 uppercase tracking-wider mb-1">Missing Provider API Keys</h4>
        <p class="text-xs text-amber-400/90 leading-relaxed">
          Some configured passes require missing keys for: 
          <strong v-for="(p, i) in missingProviders" :key="p" class="text-amber-200">
            {{ getProviderName(p) }}{{ i < missingProviders.length - 1 ? ', ' : '' }}
          </strong>.
          Add them in the 
          <button @click="emit('switchSection', 'keys')" class="text-amber-300 underline font-bold hover:text-white">
            Provider Vault
          </button>.
        </p>
      </div>
    </div>

    <!-- Filter Sub-Tabs -->
    <div class="flex items-center gap-1.5 p-1.5 bg-slate-900/70 border border-slate-800 rounded-2xl overflow-x-auto">
      <button
        @click="activeTab = 'all'"
        :class="[
          'px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0',
          activeTab === 'all'
            ? 'bg-purple-600/20 text-purple-300 border border-purple-500/40 shadow-sm'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
        ]"
      >
        All Passes (5)
      </button>
      <button
        @click="activeTab = 'core'"
        :class="[
          'px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5',
          activeTab === 'core'
            ? 'bg-purple-600/20 text-purple-300 border border-purple-500/40 shadow-sm'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
        ]"
      >
        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
        Core Pipeline (Mechanics & Story)
      </button>
      <button
        @click="activeTab = 'world'"
        :class="[
          'px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5',
          activeTab === 'world'
            ? 'bg-purple-600/20 text-purple-300 border border-purple-500/40 shadow-sm'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
        ]"
      >
        <span class="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
        Worldbuilder (Adventure Gen)
      </button>
      <button
        @click="activeTab = 'aux'"
        :class="[
          'px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5',
          activeTab === 'aux'
            ? 'bg-purple-600/20 text-purple-300 border border-purple-500/40 shadow-sm'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
        ]"
      >
        <span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
        Auxiliary (Agent & Chronicle)
      </button>
      <button
        @click="activeTab = 'endpoints'"
        :class="[
          'px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5',
          activeTab === 'endpoints'
            ? 'bg-purple-600/20 text-purple-300 border border-purple-500/40 shadow-sm'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
        ]"
      >
        <span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span>
        Local Endpoints & Memory
      </button>
    </div>

    <!-- PASS 1: MECHANICS (Simple Model) -->
    <div
      v-if="activeTab === 'all' || activeTab === 'core'"
      class="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-3xl p-6 shadow-xl transition-all space-y-4"
    >
      <!-- Card Header -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-slate-800/80">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center font-mono font-black text-sm">
            01
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 class="text-base font-bold text-white">Pass 1: Mechanics & Rule Engine</h3>
              <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
                FAST / JSON
              </span>
            </div>
            <p class="text-xs text-slate-400 mt-0.5">
              Evaluates player choices, executes dice checks, verifies item usage, and outputs structured JSON.
            </p>
          </div>
        </div>

        <div class="flex items-center gap-2 self-start sm:self-auto">
          <button
            type="button"
            @click="triggerTest('small', localForm.small_model, localForm.small_model_provider, localForm.small_openrouter_provider)"
            :disabled="testResults.small?.status === 'loading' || !localForm.small_model"
            class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-xl border border-slate-700 transition-all flex items-center gap-1.5 disabled:opacity-40"
          >
            <i v-if="testResults.small?.status === 'loading'" class="ra ra-cycle animate-spin text-emerald-400"></i>
            <i v-else class="ra ra-player text-emerald-400"></i>
            <span>Test Model</span>
          </button>
        </div>
      </div>
      <!-- Primary Selectors (2 columns) -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">
            AI Provider
          </label>
          <div class="relative">
            <select
              v-model="localForm.small_model_provider"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:ring-2 focus:ring-purple-500/50"
            >
              <option
                v-for="p in availableConstants.llm_providers"
                :key="p.id"
                :value="p.id"
              >
                {{ p.name }} {{ isProviderConfigured(p.id) ? '✓' : '(No Key)' }}
              </option>
            </select>
          </div>
        </div>

        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider">
              Selected Model
            </label>
            <button
              v-if="isLlmDiscoveryProvider(localForm.small_model_provider)"
              type="button"
              @click="refreshLlmProviderModels(localForm.small_model_provider)"
              :disabled="isLlmProviderLoading(localForm.small_model_provider)"
              class="text-[11px] text-purple-400 hover:text-purple-300 flex items-center gap-1"
              title="Refresh available models from provider API"
            >
              <i class="ra ra-recycle" :class="{'animate-spin': isLlmProviderLoading(localForm.small_model_provider)}"></i>
              <span>Refresh list</span>
            </button>
          </div>

          <select
            :value="isModelCustom(localForm.small_model, localForm.small_model_provider) ? 'custom' : localForm.small_model"
            @change="(e) => {
              const val = (e.target as HTMLSelectElement).value;
              if (val !== 'custom') localForm.small_model = val;
              else if (!isModelCustom(localForm.small_model, localForm.small_model_provider)) localForm.small_model = '';
            }"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white font-mono outline-none focus:ring-2 focus:ring-purple-500/50"
          >
            <option
              v-for="m in availableConstants.predefined_llm_models?.[localForm.small_model_provider]"
              :key="m"
              :value="m"
            >
              {{ getModelOptionLabel(localForm.small_model_provider, m) }}
            </option>
            <option value="custom">-- Custom Model ID --</option>
          </select>
        </div>
      </div>

      <!-- Custom Model Input if custom -->
      <div v-if="isModelCustom(localForm.small_model, localForm.small_model_provider)" class="pt-1">
        <label class="block text-xs font-bold text-slate-400 mb-1">Custom Model Identifier</label>
        <input
          v-model="localForm.small_model"
          type="text"
          placeholder="e.g. gpt-4o-mini or meta-llama/llama-3.2-3b"
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm text-white font-mono focus:ring-2 focus:ring-purple-500/50 outline-none"
        />
      </div>

      <!-- Test Result Alert -->
      <div
        v-if="testResults.small"
        class="p-3 rounded-xl text-xs font-mono flex items-center gap-2 border"
        :class="[
          testResults.small.status === 'loading'
            ? 'bg-slate-950 border-slate-800 text-slate-300'
            : testResults.small.status === 'success'
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
            : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
        ]"
      >
        <i :class="testResults.small.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
        <span>{{ testResults.small.message }}</span>
      </div>

      <!-- Advanced Settings Drawer -->
      <div class="pt-2 border-t border-slate-800/60">
        <button
          type="button"
          @click="toggleAdvanced('small')"
          class="text-xs font-bold text-slate-400 hover:text-white flex items-center gap-2 transition-colors"
        >
          <span>{{ expandedAdvanced.small ? '▲ Hide Advanced Parameters' : '▼ Advanced Parameters (Tokens, Thinking, Routing)' }}</span>
        </button>

        <div v-if="expandedAdvanced.small" class="mt-4 pt-3 border-t border-slate-800/40 space-y-4 animate-fade-in">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <!-- Max Tokens -->
            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1">Max Generation Tokens</label>
              <input
                v-model.number="localForm.small_max_tokens"
                type="number"
                min="512"
                max="65536"
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-purple-500/50 outline-none"
              />
            </div>

            <!-- OpenRouter Routing -->
            <div v-if="localForm.small_model_provider === 'openrouter'">
              <label class="block text-xs font-bold text-slate-400 mb-1">OpenRouter Provider Routing (optional)</label>
              <input
                v-model="localForm.small_openrouter_provider"
                type="text"
                placeholder="e.g. Together, Fireworks"
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-purple-500/50 outline-none"
              />
            </div>
          </div>

          <!-- Thinking Mode -->
          <div class="p-3.5 bg-slate-950/60 border border-slate-800 rounded-xl flex items-center justify-between gap-4">
            <div>
              <span class="text-xs font-bold text-slate-200">Reasoning / Thinking Mode</span>
              <p class="text-[11px] text-slate-400 mt-0.5">Enables extended internal reasoning tokens for models that support it.</p>
            </div>
            <div class="flex items-center gap-3">
              <div v-if="localForm.small_enable_thinking" class="flex items-center gap-1.5">
                <span class="text-[11px] text-slate-400">Budget:</span>
                <input
                  v-model.number="localForm.small_max_thinking_tokens"
                  type="number"
                  min="256"
                  max="32768"
                  class="w-20 bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs font-mono text-white text-center"
                />
              </div>
              <input
                v-model="localForm.small_enable_thinking"
                type="checkbox"
                class="w-4 h-4 rounded accent-purple-500 cursor-pointer"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- PASS 2: NARRATION (Complex Model) -->
    <div
      v-if="activeTab === 'all' || activeTab === 'core'"
      class="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-3xl p-6 shadow-xl transition-all space-y-4"
    >
      <!-- Card Header -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-slate-800/80">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center justify-center font-mono font-black text-sm">
            02
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 class="text-base font-bold text-white">Pass 2: Narrative & Dialogue Storyteller</h3>
              <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20 font-bold">
                CREATIVE PROSE
              </span>
            </div>
            <p class="text-xs text-slate-400 mt-0.5">
              Writes immersive scene descriptions, character dialogs, suspense, and sensory details based on mechanics.
            </p>
          </div>
        </div>

        <div class="flex items-center gap-2 self-start sm:self-auto">
          <button
            type="button"
            @click="triggerTest('complex', localForm.complex_model, localForm.complex_model_provider, localForm.complex_openrouter_provider)"
            :disabled="testResults.complex?.status === 'loading' || !localForm.complex_model"
            class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-xl border border-slate-700 transition-all flex items-center gap-1.5 disabled:opacity-40"
          >
            <i v-if="testResults.complex?.status === 'loading'" class="ra ra-cycle animate-spin text-purple-400"></i>
            <i v-else class="ra ra-player text-purple-400"></i>
            <span>Test Model</span>
          </button>
        </div>
      </div>

      <!-- Primary Selectors (2 columns) -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">
            AI Provider
          </label>
          <select
            v-model="localForm.complex_model_provider"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:ring-2 focus:ring-purple-500/50"
          >
            <option
              v-for="p in availableConstants.llm_providers"
              :key="p.id"
              :value="p.id"
            >
              {{ p.name }} {{ isProviderConfigured(p.id) ? '✓' : '(No Key)' }}
            </option>
          </select>
        </div>

        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider">
              Selected Model
            </label>
            <button
              v-if="isLlmDiscoveryProvider(localForm.complex_model_provider)"
              type="button"
              @click="refreshLlmProviderModels(localForm.complex_model_provider)"
              :disabled="isLlmProviderLoading(localForm.complex_model_provider)"
              class="text-[11px] text-purple-400 hover:text-purple-300 flex items-center gap-1"
            >
              <i class="ra ra-recycle" :class="{'animate-spin': isLlmProviderLoading(localForm.complex_model_provider)}"></i>
              <span>Refresh list</span>
            </button>
          </div>

          <select
            :value="isModelCustom(localForm.complex_model, localForm.complex_model_provider) ? 'custom' : localForm.complex_model"
            @change="(e) => {
              const val = (e.target as HTMLSelectElement).value;
              if (val !== 'custom') localForm.complex_model = val;
              else if (!isModelCustom(localForm.complex_model, localForm.complex_model_provider)) localForm.complex_model = '';
            }"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white font-mono outline-none focus:ring-2 focus:ring-purple-500/50"
          >
            <option
              v-for="m in availableConstants.predefined_llm_models?.[localForm.complex_model_provider]"
              :key="m"
              :value="m"
            >
              {{ getModelOptionLabel(localForm.complex_model_provider, m) }}
            </option>
            <option value="custom">-- Custom Model ID --</option>
          </select>
        </div>
      </div>

      <!-- Custom Model Input -->
      <div v-if="isModelCustom(localForm.complex_model, localForm.complex_model_provider)" class="pt-1">
        <label class="block text-xs font-bold text-slate-400 mb-1">Custom Model Identifier</label>
        <input
          v-model="localForm.complex_model"
          type="text"
          placeholder="e.g. claude-3-5-sonnet or gpt-4o"
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm text-white font-mono focus:ring-2 focus:ring-purple-500/50 outline-none"
        />
      </div>

      <!-- Test Result Alert -->
      <div
        v-if="testResults.complex"
        class="p-3 rounded-xl text-xs font-mono flex items-center gap-2 border"
        :class="[
          testResults.complex.status === 'loading'
            ? 'bg-slate-950 border-slate-800 text-slate-300'
            : testResults.complex.status === 'success'
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
            : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
        ]"
      >
        <i :class="testResults.complex.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
        <span>{{ testResults.complex.message }}</span>
      </div>

      <!-- Advanced Settings Drawer -->
      <div class="pt-2 border-t border-slate-800/60">
        <button
          type="button"
          @click="toggleAdvanced('complex')"
          class="text-xs font-bold text-slate-400 hover:text-white flex items-center gap-2 transition-colors"
        >
          <span>{{ expandedAdvanced.complex ? '▲ Hide Advanced Parameters' : '▼ Advanced Parameters (Tokens, Thinking, Routing)' }}</span>
        </button>

        <div v-if="expandedAdvanced.complex" class="mt-4 pt-3 border-t border-slate-800/40 space-y-4 animate-fade-in">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1">Max Generation Tokens</label>
              <input
                v-model.number="localForm.complex_max_tokens"
                type="number"
                min="512"
                max="65536"
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-purple-500/50 outline-none"
              />
            </div>
            <div v-if="localForm.complex_model_provider === 'openrouter'">
              <label class="block text-xs font-bold text-slate-400 mb-1">OpenRouter Provider Routing (optional)</label>
              <input
                v-model="localForm.complex_openrouter_provider"
                type="text"
                placeholder="e.g. Anthropic, Together"
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-purple-500/50 outline-none"
              />
            </div>
          </div>

          <div class="p-3.5 bg-slate-950/60 border border-slate-800 rounded-xl flex items-center justify-between gap-4">
            <div>
              <span class="text-xs font-bold text-slate-200">Reasoning / Thinking Mode</span>
              <p class="text-[11px] text-slate-400 mt-0.5">Allows deep narrative planning tokens before generating text.</p>
            </div>
            <div class="flex items-center gap-3">
              <div v-if="localForm.complex_enable_thinking" class="flex items-center gap-1.5">
                <span class="text-[11px] text-slate-400">Budget:</span>
                <input
                  v-model.number="localForm.complex_max_thinking_tokens"
                  type="number"
                  min="256"
                  max="32768"
                  class="w-20 bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs font-mono text-white text-center"
                />
              </div>
              <input
                v-model="localForm.complex_enable_thinking"
                type="checkbox"
                class="w-4 h-4 rounded accent-purple-500 cursor-pointer"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- PASS 3: WORLDBUILDER (Generator Model) -->
    <div
      v-if="activeTab === 'all' || activeTab === 'world'"
      class="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-3xl p-6 shadow-xl transition-all space-y-4"
    >
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-slate-800/80">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 flex items-center justify-center font-mono font-black text-sm">
            03
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 class="text-base font-bold text-white">Pass 3: Worldbuilder & Adventure Creator</h3>
              <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-bold">
                HIGH CONTEXT
              </span>
            </div>
            <p class="text-xs text-slate-400 mt-0.5">
              Generates complete worlds, locations, quests, NPCs, secrets, and branching nodes from scratch.
            </p>
          </div>
        </div>

        <div class="flex items-center gap-2 self-start sm:self-auto">
          <button
            type="button"
            @click="triggerTest('generator', localForm.generator_model, localForm.generator_model_provider, localForm.generator_openrouter_provider)"
            :disabled="testResults.generator?.status === 'loading' || !localForm.generator_model"
            class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-xl border border-slate-700 transition-all flex items-center gap-1.5 disabled:opacity-40"
          >
            <i v-if="testResults.generator?.status === 'loading'" class="ra ra-cycle animate-spin text-cyan-400"></i>
            <i v-else class="ra ra-player text-cyan-400"></i>
            <span>Test Model</span>
          </button>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">
            AI Provider
          </label>
          <select
            v-model="localForm.generator_model_provider"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:ring-2 focus:ring-purple-500/50"
          >
            <option
              v-for="p in availableConstants.llm_providers"
              :key="p.id"
              :value="p.id"
            >
              {{ p.name }} {{ isProviderConfigured(p.id) ? '✓' : '(No Key)' }}
            </option>
          </select>
        </div>

        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider">
              Selected Model
            </label>
            <button
              v-if="isLlmDiscoveryProvider(localForm.generator_model_provider)"
              type="button"
              @click="refreshLlmProviderModels(localForm.generator_model_provider)"
              :disabled="isLlmProviderLoading(localForm.generator_model_provider)"
              class="text-[11px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
            >
              <i class="ra ra-recycle" :class="{'animate-spin': isLlmProviderLoading(localForm.generator_model_provider)}"></i>
              <span>Refresh list</span>
            </button>
          </div>

          <select
            :value="isModelCustom(localForm.generator_model, localForm.generator_model_provider) ? 'custom' : localForm.generator_model"
            @change="(e) => {
              const val = (e.target as HTMLSelectElement).value;
              if (val !== 'custom') localForm.generator_model = val;
              else if (!isModelCustom(localForm.generator_model, localForm.generator_model_provider)) localForm.generator_model = '';
            }"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white font-mono outline-none focus:ring-2 focus:ring-purple-500/50"
          >
            <option
              v-for="m in availableConstants.predefined_llm_models?.[localForm.generator_model_provider]"
              :key="m"
              :value="m"
            >
              {{ getModelOptionLabel(localForm.generator_model_provider, m) }}
            </option>
            <option value="custom">-- Custom Model ID --</option>
          </select>
        </div>
      </div>

      <div v-if="isModelCustom(localForm.generator_model, localForm.generator_model_provider)" class="pt-1">
        <label class="block text-xs font-bold text-slate-400 mb-1">Custom Model Identifier</label>
        <input
          v-model="localForm.generator_model"
          type="text"
          placeholder="e.g. gpt-4o or gemini-2.5-pro"
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm text-white font-mono focus:ring-2 focus:ring-purple-500/50 outline-none"
        />
      </div>

      <div
        v-if="testResults.generator"
        class="p-3 rounded-xl text-xs font-mono flex items-center gap-2 border"
        :class="[
          testResults.generator.status === 'loading'
            ? 'bg-slate-950 border-slate-800 text-slate-300'
            : testResults.generator.status === 'success'
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
            : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
        ]"
      >
        <i :class="testResults.generator.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
        <span>{{ testResults.generator.message }}</span>
      </div>

      <!-- Advanced Settings Drawer -->
      <div class="pt-2 border-t border-slate-800/60">
        <button
          type="button"
          @click="toggleAdvanced('generator')"
          class="text-xs font-bold text-slate-400 hover:text-white flex items-center gap-2 transition-colors"
        >
          <span>{{ expandedAdvanced.generator ? '▲ Hide Advanced Parameters' : '▼ Advanced Parameters (Tokens, Thinking, Routing)' }}</span>
        </button>

        <div v-if="expandedAdvanced.generator" class="mt-4 pt-3 border-t border-slate-800/40 space-y-4 animate-fade-in">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1">Max Generation Tokens</label>
              <input
                v-model.number="localForm.generator_max_tokens"
                type="number"
                min="1024"
                max="131072"
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-purple-500/50 outline-none"
              />
            </div>
            <div v-if="localForm.generator_model_provider === 'openrouter'">
              <label class="block text-xs font-bold text-slate-400 mb-1">OpenRouter Provider Routing (optional)</label>
              <input
                v-model="localForm.generator_openrouter_provider"
                type="text"
                placeholder="e.g. Google, Anthropic"
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-white focus:ring-2 focus:ring-purple-500/50 outline-none"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- PASS 4 & 5: AUXILIARY (Play Agent & Chronicle Compacting) -->
    <div
      v-if="activeTab === 'all' || activeTab === 'aux'"
      class="space-y-6"
    >
      <!-- PASS 4: PLAY AGENT -->
      <div class="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-3xl p-6 shadow-xl transition-all space-y-4">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-slate-800/80">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center justify-center font-mono font-black text-sm">
              04
            </div>
            <div>
              <div class="flex items-center gap-2">
                <h3 class="text-base font-bold text-white">Pass 4: Autonomous Play Agent</h3>
                <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-bold">
                  AUTOPLAY / NPC
                </span>
              </div>
              <p class="text-xs text-slate-400 mt-0.5">
                Simulates player choices for automated test playthroughs and companion NPC roleplay.
              </p>
            </div>
          </div>

          <button
            type="button"
            @click="triggerTest('play_agent', localForm.play_agent_model, localForm.play_agent_model_provider, localForm.play_agent_openrouter_provider)"
            :disabled="testResults.play_agent?.status === 'loading' || !localForm.play_agent_model"
            class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-xl border border-slate-700 transition-all flex items-center gap-1.5 disabled:opacity-40 self-start sm:self-auto"
          >
            <i v-if="testResults.play_agent?.status === 'loading'" class="ra ra-cycle animate-spin text-amber-400"></i>
            <i v-else class="ra ra-player text-amber-400"></i>
            <span>Test Model</span>
          </button>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Provider</label>
            <select
              v-model="localForm.play_agent_model_provider"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:ring-2 focus:ring-purple-500/50"
            >
              <option v-for="p in availableConstants.llm_providers" :key="p.id" :value="p.id">
                {{ p.name }} {{ isProviderConfigured(p.id) ? '✓' : '(No Key)' }}
              </option>
            </select>
          </div>

          <div>
            <div class="flex items-center justify-between mb-1.5">
              <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider">
                Model
              </label>
              <button
                v-if="isLlmDiscoveryProvider(localForm.play_agent_model_provider)"
                type="button"
                @click="refreshLlmProviderModels(localForm.play_agent_model_provider)"
                :disabled="isLlmProviderLoading(localForm.play_agent_model_provider)"
                class="text-[11px] text-purple-400 hover:text-purple-300 flex items-center gap-1"
                title="Refresh available models from provider API"
              >
                <i class="ra ra-recycle" :class="{'animate-spin': isLlmProviderLoading(localForm.play_agent_model_provider)}"></i>
                <span>Refresh list</span>
              </button>
            </div>
            <select
              :value="isModelCustom(localForm.play_agent_model, localForm.play_agent_model_provider) ? 'custom' : localForm.play_agent_model"
              @change="(e) => {
                const val = (e.target as HTMLSelectElement).value;
                if (val !== 'custom') localForm.play_agent_model = val;
                else if (!isModelCustom(localForm.play_agent_model, localForm.play_agent_model_provider)) localForm.play_agent_model = '';
              }"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white font-mono outline-none focus:ring-2 focus:ring-purple-500/50"
            >
              <option v-for="m in availableConstants.predefined_llm_models?.[localForm.play_agent_model_provider]" :key="m" :value="m">
                {{ getModelOptionLabel(localForm.play_agent_model_provider, m) }}
              </option>
              <option value="custom">-- Custom Model ID --</option>
            </select>
          </div>
        </div>

        <!-- Custom Model Input if custom -->
        <div v-if="isModelCustom(localForm.play_agent_model, localForm.play_agent_model_provider)" class="pt-1">
          <label class="block text-xs font-bold text-slate-400 mb-1">Custom Model Identifier</label>
          <input
            v-model="localForm.play_agent_model"
            type="text"
            placeholder="e.g. gpt-4o-mini"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm text-white font-mono focus:ring-2 focus:ring-purple-500/50 outline-none"
          />
        </div>

        <!-- OpenRouter Provider Routing if openrouter -->
        <div v-if="localForm.play_agent_model_provider === 'openrouter'" class="pt-1">
          <label class="block text-xs font-bold text-slate-400 mb-1">OpenRouter Provider Routing (optional)</label>
          <input
            v-model="localForm.play_agent_openrouter_provider"
            type="text"
            placeholder="e.g. Together, Grok"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm text-white font-mono focus:ring-2 focus:ring-purple-500/50 outline-none"
          />
        </div>

        <!-- Play Agent Personality -->
        <div class="pt-2 border-t border-slate-800/80 space-y-3">
          <div>
            <div class="flex items-center justify-between mb-1.5">
              <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider">
                Play Agent Personality
              </label>
              <span class="text-[11px] font-mono text-purple-400 font-semibold">
                {{ localForm.play_agent_personality ? localForm.play_agent_personality.charAt(0).toUpperCase() + localForm.play_agent_personality.slice(1) : 'Casual' }}
              </span>
            </div>
            <select
              v-model="localForm.play_agent_personality"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:ring-2 focus:ring-purple-500/50"
            >
              <option value="casual">Casual (Relaxed, curious, informal, plays for fun)</option>
              <option value="bureaucrat">Bureaucrat (Strictly formal, protocol-obsessed, demands documentation)</option>
              <option value="powerplayer">Powerplayer (Aggressive min-maxer, optimal path & efficiency)</option>
              <option value="custom">Custom (User-defined directives)</option>
            </select>
          </div>

          <!-- Custom Personality Instructions Field -->
          <div v-if="localForm.play_agent_personality === 'custom'" class="space-y-1.5">
            <label class="block text-xs font-bold text-purple-300 uppercase tracking-wider">
              Custom Personality Directives
            </label>
            <textarea
              v-model="localForm.play_agent_custom_personality"
              rows="3"
              placeholder="e.g. You are a paranoid rogue who never trusts chests, checks for traps everywhere, and speaks in cryptic underworld slang."
              class="w-full bg-slate-950 border border-purple-500/30 focus:border-purple-500 rounded-xl p-3 text-xs text-white placeholder-slate-600 outline-none focus:ring-2 focus:ring-purple-500/40 resize-y"
            ></textarea>
            <p class="text-[11px] text-slate-400">
              Provide custom roleplay guidelines and gameplay habits for the autonomous Play-Agent.
            </p>
          </div>
        </div>

        <!-- Play Agent Behaviors / Defaults -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-slate-800/80">
          <div class="flex items-center justify-between gap-3 p-3 bg-slate-950/60 border border-slate-800 rounded-xl">
            <div>
              <div class="text-xs font-bold text-cyan-200 flex items-center gap-1.5">
                <i class="ra ra-compass text-cyan-400"></i> Sequence Walkthrough Default
              </div>
              <p class="text-[11px] text-slate-400 mt-0.5">Allow agent to read sequence walkthrough.</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer shrink-0">
              <input type="checkbox" v-model="localForm.play_agent_allow_walkthrough" class="sr-only peer">
              <div class="w-9 h-5 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-cyan-500 peer-checked:after:bg-white"></div>
            </label>
          </div>

          <div class="flex items-center justify-between gap-3 p-3 bg-slate-950/60 border border-slate-800 rounded-xl">
            <div>
              <div class="text-xs font-bold text-amber-200 flex items-center gap-1.5">
                <i class="ra ra-perspective-dice-random text-amber-400"></i> Monkey Mode Default
              </div>
              <p class="text-[11px] text-slate-400 mt-0.5">Start directly in chaos-testing mode.</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer shrink-0">
              <input type="checkbox" v-model="localForm.play_agent_monkey_mode" class="sr-only peer">
              <div class="w-9 h-5 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-amber-500 peer-checked:after:bg-white"></div>
            </label>
          </div>
        </div>

        <div v-if="testResults.play_agent" class="p-3 rounded-xl text-xs font-mono flex items-center gap-2 border bg-slate-950 border-slate-800">
          <i :class="testResults.play_agent.status === 'success' ? 'ra ra-check text-emerald-400' : 'ra ra-warning text-rose-400'"></i>
          <span>{{ testResults.play_agent.message }}</span>
        </div>
      </div>

      <!-- PASS 5: CHRONICLE COMPACTING -->
      <div class="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-3xl p-6 shadow-xl transition-all space-y-4">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-slate-800/80">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center justify-center font-mono font-black text-sm">
              05
            </div>
            <div>
              <div class="flex items-center gap-2">
                <h3 class="text-base font-bold text-white">Pass 5: Chronicle Compacting & Memory</h3>
                <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-bold">
                  SUMMARIZATION
                </span>
              </div>
              <p class="text-xs text-slate-400 mt-0.5">
                Compresses past adventures into persistent lore summaries to preserve context in long campaigns.
              </p>
            </div>
          </div>

          <button
            type="button"
            @click="triggerTest('compression', localForm.compression_model, localForm.compression_model_provider, localForm.compression_openrouter_provider)"
            :disabled="testResults.compression?.status === 'loading' || !localForm.compression_model"
            class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-xl border border-slate-700 transition-all flex items-center gap-1.5 disabled:opacity-40 self-start sm:self-auto"
          >
            <i v-if="testResults.compression?.status === 'loading'" class="ra ra-cycle animate-spin text-indigo-400"></i>
            <i v-else class="ra ra-player text-indigo-400"></i>
            <span>Test Model</span>
          </button>
        </div>

        <!-- Compacting Controls Bar -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-slate-950/70 rounded-2xl border border-slate-800">
          <!-- Toggle -->
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="flex items-center gap-2">
                <span class="text-xs font-bold text-white">Automatic History Compacting</span>
                <span :class="['text-[9px] font-bold px-1.5 py-0.5 rounded uppercase', localForm.enable_history_compression ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-800 text-slate-400']">
                  {{ localForm.enable_history_compression ? 'Active' : 'Off' }}
                </span>
              </div>
              <p class="text-[11px] text-slate-400 mt-0.5">Periodically summarizes old story turns.</p>
            </div>
            <input
              type="checkbox"
              v-model="localForm.enable_history_compression"
              class="w-5 h-5 rounded accent-indigo-500 cursor-pointer"
            />
          </div>

          <!-- Turns Slider -->
          <div class="space-y-1">
            <div class="flex items-center justify-between text-xs">
              <span class="text-slate-400 font-bold uppercase text-[10px]">Threshold</span>
              <span class="font-mono text-indigo-300 font-bold">{{ localForm.turns_before_compacting }} turns</span>
            </div>
            <input
              type="range"
              min="1"
              max="100"
              :value="localForm.turns_before_compacting"
              @input="handleTurnsInput"
              class="w-full accent-indigo-500 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
            />
            <div class="flex justify-between text-[9px] text-slate-500 font-mono">
              <span>1 turn</span>
              <span>10 (Default)</span>
              <span>100 turns</span>
            </div>
          </div>
        </div>

        <!-- Model Selection -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Provider</label>
            <select
              v-model="localForm.compression_model_provider"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:ring-2 focus:ring-purple-500/50"
            >
              <option v-for="p in availableConstants.llm_providers" :key="p.id" :value="p.id">
                {{ p.name }} {{ isProviderConfigured(p.id) ? '✓' : '(No Key)' }}
              </option>
            </select>
          </div>

          <div>
            <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Model</label>
            <select
              :value="isModelCustom(localForm.compression_model, localForm.compression_model_provider) ? 'custom' : localForm.compression_model"
              @change="(e) => {
                const val = (e.target as HTMLSelectElement).value;
                if (val !== 'custom') localForm.compression_model = val;
                else if (!isModelCustom(localForm.compression_model, localForm.compression_model_provider)) localForm.compression_model = '';
              }"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white font-mono outline-none focus:ring-2 focus:ring-purple-500/50"
            >
              <option value="">-- No Dedicated Model (Fall back to Pass 1) --</option>
              <option v-for="m in availableConstants.predefined_llm_models?.[localForm.compression_model_provider]" :key="m" :value="m">
                {{ getModelOptionLabel(localForm.compression_model_provider, m) }}
              </option>
              <option value="custom">-- Custom Model ID --</option>
            </select>
          </div>
        </div>

        <div v-if="testResults.compression" class="p-3 rounded-xl text-xs font-mono flex items-center gap-2 border bg-slate-950 border-slate-800">
          <i :class="testResults.compression.status === 'success' ? 'ra ra-check text-emerald-400' : 'ra ra-warning text-rose-400'"></i>
          <span>{{ testResults.compression.message }}</span>
        </div>
      </div>
    </div>

    <!-- LOCAL ENDPOINTS & INFRASTRUCTURE (Ollama / MiniMax) -->
    <div
      v-if="activeTab === 'all' || activeTab === 'endpoints'"
      class="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-6"
    >
      <div class="flex items-center gap-3 pb-3 border-b border-slate-800/80">
        <div class="w-10 h-10 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center justify-center text-lg">
          <i class="ra ra-reactor"></i>
        </div>
        <div>
          <h3 class="text-base font-bold text-white">Local & Custom API Endpoints</h3>
          <p class="text-xs text-slate-400 mt-0.5">Configure host addresses for self-hosted and on-premise model backends.</p>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Ollama Endpoint -->
        <div class="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-white flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-cyan-400"></span>
              Ollama API Host
            </span>
            <button
              type="button"
              @click="refreshOllamaModels"
              class="px-2.5 py-1 bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 text-[11px] font-bold rounded-lg border border-cyan-500/30 transition-all flex items-center gap-1"
            >
              <i class="ra ra-recycle" :class="{'animate-spin': isLoadingOllamaModels}"></i>
              <span>{{ isLoadingOllamaModels ? 'Detecting...' : 'Detect Models' }}</span>
            </button>
          </div>
          <input
            v-model="localForm.ollama_url"
            type="text"
            placeholder="http://localhost:11434"
            class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white font-mono outline-none focus:ring-2 focus:ring-cyan-500/50"
          />
          <div class="flex items-center justify-between text-[11px] text-slate-500 font-mono">
            <span>Detected: {{ ollamaModelCount }} local models</span>
            <span v-if="ollamaModelCount > 0" class="text-emerald-400">Ready</span>
            <span v-else class="text-amber-400">No models detected</span>
          </div>
        </div>

        <!-- MiniMax Endpoint -->
        <div class="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-white flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-purple-400"></span>
              MiniMax API Endpoint
            </span>
            <button
              type="button"
              @click="refreshMinimaxModels"
              class="px-2.5 py-1 bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 text-[11px] font-bold rounded-lg border border-purple-500/30 transition-all flex items-center gap-1"
            >
              <i class="ra ra-recycle" :class="{'animate-spin': isLoadingMinimaxModels}"></i>
              <span>{{ isLoadingMinimaxModels ? 'Detecting...' : 'Detect Models' }}</span>
            </button>
          </div>
          <input
            v-model="localForm.minimax_url"
            type="text"
            placeholder="https://api.minimax.chat/v1"
            class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white font-mono outline-none focus:ring-2 focus:ring-purple-500/50"
          />
          <div class="flex items-center justify-between text-[11px] text-slate-500 font-mono">
            <span>Detected: {{ minimaxModelCount }} models</span>
            <span v-if="minimaxModelCount > 0" class="text-emerald-400">Ready</span>
            <span v-else class="text-slate-500">Default endpoints</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Sticky Bottom Save Bar -->
    <div class="sticky bottom-6 z-30 p-4 bg-slate-900/90 backdrop-blur-md border border-slate-800 rounded-2xl shadow-2xl flex items-center justify-between gap-4">
      <div class="flex items-center gap-2 text-xs text-slate-400">
        <i class="ra ra-brain text-purple-400"></i>
        <span>Intelligence Pipeline Configured</span>
      </div>
      <button
        type="button"
        @click="handleSave"
        :disabled="isSubmitting"
        class="px-6 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-purple-900/30 disabled:opacity-50 flex items-center gap-2 cursor-pointer"
      >
        <i v-if="isSubmitting" class="ra ra-recycle animate-spin"></i>
        <i v-else class="ra ra-save"></i>
        <span>{{ isSubmitting ? 'Saving...' : 'Save Intelligence Settings' }}</span>
      </button>
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
