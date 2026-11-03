<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  configuredKeys: Record<string, { masked: string; is_env: boolean }>
  isSubmitting: boolean
}>()

const emit = defineEmits<{
  (e: 'save', payload: { provider: string; api_key: string }): void
  (e: 'delete', provider: string): void
}>()

interface ProviderMeta {
  id: string
  name: string
  category: 'major' | 'specialized' | 'local'
  capabilities: string[]
  description: string
  keyPrefix?: string
  docsUrl?: string
}

const PROVIDERS: ProviderMeta[] = [
  {
    id: 'custom_openai',
    name: 'OpenAI-Compatible API',
    category: 'specialized',
    capabilities: ['LLM'],
    description: 'API key for a hosted OpenAI-compatible gateway or self-hosted endpoint. Optional for unauthenticated servers.'
  },
  {
    id: 'openai',
    name: 'OpenAI',
    category: 'major',
    capabilities: ['LLM', 'T2I', 'TTS'],
    description: 'GPT-4o, GPT-4o-mini, image generation, and TTS voices.',
    keyPrefix: 'sk-...',
    docsUrl: 'https://platform.openai.com/api-keys'
  },
  {
    id: 'google',
    name: 'Google Gemini',
    category: 'major',
    capabilities: ['LLM', 'TTS (Gemini Voice)'],
    description: 'Gemini 2.5 Flash / Pro reasoning and high-fidelity Gemini TTS voices.',
    keyPrefix: 'AIza...',
    docsUrl: 'https://aistudio.google.com/app/apikey'
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    category: 'major',
    capabilities: ['LLM'],
    description: 'Claude 3.5 Sonnet and Haiku for deep narrative prose.',
    keyPrefix: 'sk-ant-...',
    docsUrl: 'https://console.anthropic.com/settings/keys'
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    category: 'major',
    capabilities: ['LLM', 'T2I'],
    description: 'Unified gateway for hundreds of open and proprietary AI models.',
    keyPrefix: 'sk-or-...',
    docsUrl: 'https://openrouter.ai/keys'
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    category: 'major',
    capabilities: ['LLM'],
    description: 'DeepSeek-V3 and DeepSeek-R1 reasoning models with high cost-efficiency.',
    keyPrefix: 'sk-...',
    docsUrl: 'https://platform.deepseek.com/api_keys'
  },
  {
    id: 'minimax',
    name: 'MiniMax',
    category: 'specialized',
    capabilities: ['LLM', 'TTS'],
    description: 'MiniMax-01 and high-capacity long-context reasoning models.',
    keyPrefix: 'eyJ...',
    docsUrl: 'https://api.minimax.chat'
  },
  {
    id: 'black_forest_labs',
    name: 'Black Forest Labs',
    category: 'specialized',
    capabilities: ['T2I (FLUX)'],
    description: 'State-of-the-art FLUX.1 & FLUX 3 visual generation models.',
    keyPrefix: 'bfl-...',
    docsUrl: 'https://docs.bfl.ml'
  },
  {
    id: 'elevenlabs',
    name: 'ElevenLabs',
    category: 'specialized',
    capabilities: ['TTS'],
    description: 'Ultra-realistic character narration with emotional voice control.',
    keyPrefix: 'sk_...',
    docsUrl: 'https://elevenlabs.io'
  },
  {
    id: 'kimi',
    name: 'Kimi (Moonshot)',
    category: 'specialized',
    capabilities: ['LLM'],
    description: 'Moonshot AI long-context models for intricate world lore.',
    keyPrefix: 'sk-...',
    docsUrl: 'https://platform.moonshot.cn'
  },
  {
    id: 'ollama',
    name: 'Ollama',
    category: 'local',
    capabilities: ['Local LLM', 'Local T2I'],
    description: 'Self-hosted open models running entirely on your local hardware.'
  }
]

// Filter state
const activeFilter = ref<'all' | 'configured' | 'missing'>('all')
const searchQuery = ref('')

// Active editing modal state
const activeProvider = ref<ProviderMeta | null>(null)
const keyInput = ref('')
const showKey = ref(false)

const filteredProviders = computed(() => {
  return PROVIDERS.filter((p) => {
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase()
      if (!p.name.toLowerCase().includes(q) && !p.description.toLowerCase().includes(q)) {
        return false
      }
    }
    const isConfigured = Boolean(props.configuredKeys[p.id]) || p.id === 'ollama'
    if (activeFilter.value === 'configured' && !isConfigured) return false
    if (activeFilter.value === 'missing' && isConfigured) return false
    return true
  })
})

const configuredCount = computed(() => {
  const configured = Object.keys(props.configuredKeys).length
  return configured + (props.configuredKeys['ollama'] ? 0 : 1) // Ollama is always local
})

const openConfig = (provider: ProviderMeta) => {
  activeProvider.value = provider
  keyInput.value = ''
  showKey.value = false
}

const closeConfig = () => {
  activeProvider.value = null
  keyInput.value = ''
  showKey.value = false
}

const handleSave = () => {
  if (!activeProvider.value) return
  emit('save', {
    provider: activeProvider.value.id,
    api_key: keyInput.value.trim()
  })
  closeConfig()
}

const handleDelete = (providerId: string) => {
  if (confirm(`Remove the API key for ${providerId}? Models requiring this key will stop functioning.`)) {
    emit('delete', providerId)
  }
}
</script>

<template>
  <div class="space-y-6 animate-fade-in max-w-5xl">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
          <i class="ra ra-locked text-emerald-400"></i>
          Provider Vault
        </h1>
        <p class="text-slate-400 text-sm mt-1">
          Manage API credentials for neural providers. Keys are stored encrypted at rest.
        </p>
      </div>

      <!-- Stats Pill -->
      <div class="flex items-center gap-3 self-start sm:self-auto">
        <div class="px-4 py-2 bg-slate-900 border border-slate-800 rounded-xl flex items-center gap-2 text-xs font-mono">
          <span class="w-2 h-2 rounded-full" :class="configuredCount > 0 ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'"></span>
          <span class="text-slate-300 font-bold">{{ configuredCount }}</span>
          <span class="text-slate-500">Providers Ready</span>
        </div>
      </div>
    </div>

    <!-- Filters & Search Toolbar -->
    <div class="flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-900/60 border border-slate-800/80 rounded-2xl p-3">
      <!-- Filter Chips -->
      <div class="flex items-center gap-1.5 w-full sm:w-auto">
        <button
          @click="activeFilter = 'all'"
          :class="[
            'px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer',
            activeFilter === 'all'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 shadow-sm'
              : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
          ]"
        >
          All ({{ PROVIDERS.length }})
        </button>
        <button
          @click="activeFilter = 'configured'"
          :class="[
            'px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer',
            activeFilter === 'configured'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 shadow-sm'
              : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
          ]"
        >
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          Configured ({{ configuredCount }})
        </button>
        <button
          @click="activeFilter = 'missing'"
          :class="[
            'px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer',
            activeFilter === 'missing'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 shadow-sm'
              : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
          ]"
        >
          <span class="w-1.5 h-1.5 rounded-full bg-slate-500"></span>
          Unset ({{ PROVIDERS.length - configuredCount }})
        </button>
      </div>

      <!-- Search Box -->
      <div class="relative w-full sm:w-64">
        <i class="ra ra-eye-shield absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-xs"></i>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Filter providers..."
          class="w-full bg-slate-950/80 border border-slate-800 rounded-xl pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/50"
        />
        <button
          v-if="searchQuery"
          @click="searchQuery = ''"
          class="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 text-xs cursor-pointer"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- Provider Table -->
    <div class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
      <div class="overflow-x-auto">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-950/60 text-xxs font-black text-slate-500 uppercase tracking-widest">
              <th class="px-5 py-3.5">Provider</th>
              <th class="px-5 py-3.5">Capabilities</th>
              <th class="px-5 py-3.5">Status</th>
              <th class="px-5 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/70 text-xs">
            <tr
              v-for="provider in filteredProviders"
              :key="provider.id"
              class="hover:bg-white/[0.02] transition-colors group"
            >
              <!-- Provider Name & Info -->
              <td class="px-5 py-3.5 align-middle">
                <div class="flex flex-col gap-0.5">
                  <div class="flex items-center gap-2">
                    <span class="font-bold text-white group-hover:text-emerald-300 transition-colors">
                      {{ provider.name }}
                    </span>
                    <a
                      v-if="provider.docsUrl"
                      :href="provider.docsUrl"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="text-[11px] text-slate-500 hover:text-slate-300 transition-colors inline-flex items-center gap-0.5"
                      title="Open provider API key portal"
                    >
                      <span class="text-[10px]">↗</span>
                    </a>
                  </div>
                  <p class="text-[11px] text-slate-400 max-w-xl line-clamp-1">
                    {{ provider.description }}
                  </p>
                </div>
              </td>

              <!-- Capabilities -->
              <td class="px-5 py-3.5 align-middle whitespace-nowrap">
                <div class="flex items-center gap-1.5 flex-wrap">
                  <span
                    v-for="cap in provider.capabilities"
                    :key="cap"
                    class="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700/50"
                  >
                    {{ cap }}
                  </span>
                </div>
              </td>

              <!-- Status -->
              <td class="px-5 py-3.5 align-middle whitespace-nowrap">
                <span
                  v-if="configuredKeys[provider.id]?.is_env"
                  class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20"
                  title="Configured through system environment variable"
                >
                  <span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                  ENV
                </span>
                <span
                  v-else-if="configuredKeys[provider.id]"
                  class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                >
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  CONFIGURED
                </span>
                <span
                  v-else-if="provider.id === 'ollama'"
                  class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"
                >
                  <span class="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
                  LOCAL
                </span>
                <span
                  v-else
                  class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono text-slate-500 bg-slate-950/60 border border-slate-800"
                >
                  <span class="w-1.5 h-1.5 rounded-full bg-slate-600"></span>
                  UNSET
                </span>
              </td>

              <!-- Actions -->
              <td class="px-5 py-3.5 align-middle text-right whitespace-nowrap">
                <div class="flex items-center justify-end gap-2">
                  <button
                    v-if="configuredKeys[provider.id] && !configuredKeys[provider.id].is_env"
                    @click="handleDelete(provider.id)"
                    class="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg text-xs transition-colors cursor-pointer"
                    title="Delete stored key"
                  >
                    <i class="ra ra-cancel"></i>
                  </button>
                  <button
                    v-if="provider.id !== 'ollama' && !configuredKeys[provider.id]?.is_env"
                    @click="openConfig(provider)"
                    class="px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer"
                    :class="[
                      configuredKeys[provider.id]
                        ? 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/60'
                        : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm'
                    ]"
                  >
                    <i class="ra ra-locked text-[11px]"></i>
                    <span>{{ configuredKeys[provider.id] ? 'Update Key' : 'Add Key' }}</span>
                  </button>
                  <span
                    v-else-if="configuredKeys[provider.id]?.is_env"
                    class="text-[11px] text-amber-500/80 font-mono italic px-2 py-1"
                  >
                    Read-only
                  </span>
                  <span
                    v-else-if="provider.id === 'ollama'"
                    class="text-[11px] text-cyan-400/80 font-mono px-2 py-1"
                  >
                    Ready locally
                  </span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-if="filteredProviders.length === 0"
      class="py-12 text-center border-2 border-dashed border-slate-800 rounded-3xl text-slate-500"
    >
      <i class="ra ra-eye-shield text-3xl mb-2 opacity-40"></i>
      <p class="font-bold text-sm text-slate-400">No providers match your search filter.</p>
      <button
        @click="searchQuery = ''; activeFilter = 'all'"
        class="mt-3 text-xs text-emerald-400 underline hover:text-emerald-300 cursor-pointer"
      >
        Reset filters
      </button>
    </div>

    <!-- Configure Key Modal -->
    <Teleport to="body">
      <div v-if="activeProvider" class="fixed inset-0 z-[100] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="closeConfig"></div>
        <div class="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl p-8 animate-fade-in">
          <!-- Modal Header -->
          <div class="flex items-start justify-between gap-4 mb-6">
            <div>
              <h2 class="text-xl font-bold text-white">Configure {{ activeProvider.name }}</h2>
              <p class="text-xs text-slate-400 mt-0.5">Enter your secret API key below.</p>
            </div>
            <button @click="closeConfig" class="text-slate-500 hover:text-white transition-colors p-1 cursor-pointer">
              <i class="ra ra-cancel text-sm"></i>
            </button>
          </div>

          <!-- Description Callout -->
          <div class="mb-6 p-4 bg-slate-950/60 border border-slate-800 rounded-2xl text-xs text-slate-400 leading-relaxed">
            <p>{{ activeProvider.description }}</p>
            <div class="mt-2 flex items-center gap-2">
              <span class="text-slate-500">Supports:</span>
              <span
                v-for="cap in activeProvider.capabilities"
                :key="cap"
                class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[10px]"
              >
                {{ cap }}
              </span>
            </div>
          </div>

          <!-- Existing Key Alert if Present -->
          <div
            v-if="configuredKeys[activeProvider.id]"
            class="mb-6 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-xs flex items-center justify-between text-emerald-400"
          >
            <div class="flex items-center gap-2">
              <i class="ra ra-check"></i>
              <span>A key is already configured and stored in the vault.</span>
            </div>
            <span class="text-[10px] text-emerald-400/70 uppercase font-mono">Overwriting</span>
          </div>

          <!-- Key Input -->
          <div class="space-y-2 mb-6">
            <div class="flex items-center justify-between">
              <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider">
                API Secret Key
              </label>
              <a
                v-if="activeProvider.docsUrl"
                :href="activeProvider.docsUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="text-[11px] text-emerald-400 hover:underline flex items-center gap-1"
              >
                <span>Get key from {{ activeProvider.name }}</span>
                <span>↗</span>
              </a>
            </div>
            <div class="relative">
              <input
                v-model="keyInput"
                :type="showKey ? 'text' : 'password'"
                :placeholder="activeProvider.keyPrefix || 'Enter secret key...'"
                autocomplete="off"
                spellcheck="false"
                class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-4 pr-11 py-3 text-white text-sm font-mono placeholder-slate-600 focus:ring-2 focus:ring-emerald-500/50 outline-none"
                @keydown.enter="keyInput.trim() && handleSave()"
              />
              <button
                type="button"
                @click="showKey = !showKey"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 text-xs px-1 py-1 cursor-pointer"
                :title="showKey ? 'Hide key' : 'Show key'"
              >
                <i :class="['ra', showKey ? 'ra-eye-shield' : 'ra-eye-slash']"></i>
              </button>
            </div>
            <p class="text-[11px] text-slate-500">
              Keys are encrypted at rest locally and only sent to the selected provider when making requests.
            </p>
          </div>

          <!-- Actions -->
          <div class="flex items-center justify-end gap-3 pt-2">
            <button
              @click="closeConfig"
              class="px-5 py-2.5 rounded-xl border border-slate-800 text-slate-400 hover:text-white hover:bg-slate-800/50 text-sm font-bold transition-all cursor-pointer"
            >
              Cancel
            </button>
            <button
              @click="handleSave"
              :disabled="!keyInput.trim() || isSubmitting"
              class="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-sm font-bold transition-all shadow-lg shadow-emerald-900/20 disabled:opacity-50 flex items-center gap-2 cursor-pointer"
            >
              <i v-if="isSubmitting" class="ra ra-cycle animate-spin"></i>
              <i v-else class="ra ra-locked"></i>
              <span>{{ isSubmitting ? 'Securing...' : 'Save to Vault' }}</span>
            </button>
          </div>
        </div>
      </div>
    </Teleport>
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
