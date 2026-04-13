<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const keyForm = ref({
  provider: 'openai',
  api_key: ''
})

const llmForm = ref({
  small_model: 'openai/gpt-4o-mini',
  complex_model: 'openai/gpt-4o-mini',
  preferred_provider: 'openai'
})

const configuredKeys = ref<Record<string, string>>({})
const isSubmittingKey = ref(false)
const isSubmittingLlm = ref(false)
const statusMessage = ref<{ type: 'success' | 'error', text: string } | null>(null)

const goBack = () => {
  router.push({ name: 'portal' })
}

const fetchSettings = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/settings')
    if (res.ok) {
      const data = await res.json()
      configuredKeys.value = data.keys || {}
      if (data.llm_settings) {
        llmForm.value = { ...data.llm_settings }
      }
    }
  } catch (error) {
    console.error('Failed to fetch settings', error)
  }
}

const saveApiKey = async () => {
  if (!keyForm.value.api_key.trim()) {
    statusMessage.value = { type: 'error', text: 'API key cannot be empty' }
    return
  }

  isSubmittingKey.value = true
  statusMessage.value = null

  try {
    const res = await fetch('http://localhost:8000/api/settings/keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: keyForm.value.provider,
        api_key: keyForm.value.api_key
      })
    })

    if (res.ok) {
      statusMessage.value = { type: 'success', text: `${keyForm.value.provider} key saved securely.` }
      keyForm.value.api_key = ''
      fetchSettings()
    } else {
      statusMessage.value = { type: 'error', text: 'Failed to save key.' }
    }
  } catch (error) {
    statusMessage.value = { type: 'error', text: 'Network error.' }
  } finally {
    isSubmittingKey.value = false
  }
}

const saveLlmSettings = async () => {
  isSubmittingLlm.value = true
  statusMessage.value = null

  try {
    const res = await fetch('http://localhost:8000/api/settings/llm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(llmForm.value)
    })

    if (res.ok) {
      statusMessage.value = { type: 'success', text: 'Model preferences updated successfully.' }
    } else {
      statusMessage.value = { type: 'error', text: 'Failed to update model settings.' }
    }
  } catch (error) {
    statusMessage.value = { type: 'error', text: 'Network error.' }
  } finally {
    isSubmittingLlm.value = false
  }
}

onMounted(() => {
  fetchSettings()
})
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 font-sans p-8 flex justify-center items-start pt-16 overflow-y-auto">
    <div class="w-full max-w-4xl pb-20">
      <!-- Header -->
      <div class="flex items-center gap-4 mb-10">
        <button 
          @click="goBack" 
          class="p-2 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
          </svg>
        </button>
        <div>
          <h1 class="text-4xl font-extrabold text-white">Engine Configuration</h1>
          <p class="text-slate-400 mt-2">Manage your AI intelligence and providers</p>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- API Keys Section -->
        <div class="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-8 shadow-2xl flex flex-col h-fit">
          <h2 class="text-2xl font-bold text-white mb-6 flex items-center gap-3">
             <i class="ra ra-locked text-emerald-500"></i>
             API Management
          </h2>

          <div class="space-y-6">
            <div class="space-y-2">
              <label class="block text-sm font-semibold text-slate-300">Provider</label>
              <select 
                v-model="keyForm.provider" 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all font-medium"
              >
                <option value="openai">OpenAI</option>
                <option value="openrouter">OpenRouter</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google Gemini</option>
                <option value="ollama">Ollama (Local)</option>
              </select>
            </div>

            <div class="space-y-2">
              <label class="block text-sm font-semibold text-slate-300">Set New API Key</label>
              <input 
                v-model="keyForm.api_key" 
                type="password" 
                placeholder="Paste key here..." 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white placeholder-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all"
              />
            </div>

            <button 
              @click="saveApiKey" 
              :disabled="isSubmittingKey || !keyForm.api_key"
              class="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl shadow-lg transition-all disabled:opacity-50"
            >
              {{ isSubmittingKey ? 'Encrypting...' : 'Save API Key' }}
            </button>

            <!-- Configured Providers List -->
            <div class="mt-8">
              <h3 class="text-xs font-bold uppercase tracking-widest text-slate-500 mb-4">Secured Providers</h3>
              <div class="space-y-2">
                <div v-if="Object.keys(configuredKeys).length === 0" class="text-slate-600 italic text-sm">No keys stored yet.</div>
                <div 
                  v-for="(val, provider) in configuredKeys" 
                  :key="provider"
                  class="flex items-center justify-between p-3 bg-slate-950/50 border border-slate-800 rounded-xl"
                >
                   <span class="capitalize text-slate-300 font-medium">{{ provider }}</span>
                   <span class="text-emerald-500 text-xs font-mono">ENCRYPTED</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Model Preferences Section -->
        <div class="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-8 shadow-2xl flex flex-col h-fit">
          <h2 class="text-2xl font-bold text-white mb-6 flex items-center gap-3">
             <i class="ra ra-brain text-purple-500"></i>
             Intelligence Routing
          </h2>

          <div class="space-y-6">
            <div class="space-y-2">
              <label class="block text-sm font-semibold text-slate-300">Primary Provider (Routing)</label>
              <select 
                v-model="llmForm.preferred_provider" 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all font-medium"
              >
                <option value="openai">OpenAI</option>
                <option value="openrouter">OpenRouter</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google Gemini</option>
                <option value="ollama">Ollama (Local)</option>
              </select>
            </div>

            <div class="space-y-2">
              <label class="block text-sm font-semibold text-slate-300">Small Task Model (Narrative/Chat)</label>
              <input 
                v-model="llmForm.small_model" 
                type="text" 
                placeholder="e.g. gpt-4o-mini or google/gemini-flash-1.5" 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white placeholder-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all"
              />
              <p class="text-xs text-slate-500">Used for initial scene generation and simple user interactions.</p>
            </div>

            <div class="space-y-2">
              <label class="block text-sm font-semibold text-slate-300">Complex Task Model (Strict Mechanics)</label>
              <input 
                v-model="llmForm.complex_model" 
                type="text" 
                placeholder="e.g. gpt-4o or anthropic/claude-3-5-sonnet" 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white placeholder-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all"
              />
              <p class="text-xs text-slate-500">Used for resolving mechanics, structured data, and complex rules.</p>
            </div>

            <button 
              @click="saveLlmSettings" 
              :disabled="isSubmittingLlm"
              class="w-full py-3 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold rounded-xl shadow-lg transition-all disabled:opacity-50"
            >
              {{ isSubmittingLlm ? 'Applying...' : 'Update Model Preferences' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Footer Message -->
      <div 
        v-if="statusMessage" 
        :class="[
          'mt-8 p-5 rounded-2xl text-base font-semibold transition-all duration-500 text-center border',
          statusMessage.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'
        ]"
      >
        {{ statusMessage.text }}
      </div>
    </div>
  </div>
</template>
