<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const form = ref({
  provider: 'openai', // default
  api_key: ''
})

const isSubmitting = ref(false)
const statusMessage = ref<{ type: 'success' | 'error', text: string } | null>(null)

const goBack = () => {
  router.push({ name: 'portal' })
}

const saveApiKey = async () => {
  if (!form.value.api_key.trim()) {
    statusMessage.value = { type: 'error', text: 'API key cannot be empty' }
    return
  }

  isSubmitting.value = true
  statusMessage.value = null

  try {
    const res = await fetch('http://localhost:8000/api/v1/settings/keys', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        provider: form.value.provider,
        api_key: form.value.api_key
      })
    })

    if (res.ok) {
      const data = await res.json()
      statusMessage.value = { type: 'success', text: data.message || 'Key saved securely.' }
      form.value.api_key = '' // clear field after saving
    } else {
      statusMessage.value = { type: 'error', text: 'Failed to save key. Server returned an error.' }
    }
  } catch (error) {
    statusMessage.value = { type: 'error', text: 'Network error. Could not connect to API.' }
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 font-sans p-8 flex justify-center items-start pt-20">
    <div class="w-full max-w-xl">
      <!-- Header -->
      <div class="flex items-center gap-4 mb-8">
        <button 
          @click="goBack" 
          class="p-2 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
          </svg>
        </button>
        <div>
          <h1 class="text-3xl font-bold text-white">Engine Configuration</h1>
          <p class="text-slate-400 text-sm mt-1">Configure LLM providers and core settings</p>
        </div>
      </div>

      <!-- Settings Panel -->
      <div class="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-8 shadow-2xl">
        <h2 class="text-xl font-semibold text-white mb-6 flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
          API Keys
        </h2>

        <form @submit.prevent="saveApiKey" class="space-y-6">
          <div class="space-y-2">
            <label class="block text-sm font-medium text-slate-300">Provider</label>
            <div class="relative">
              <select 
                v-model="form.provider" 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white appearance-none focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google (Gemini)</option>
                <option value="ollama">Local (Ollama)</option>
              </select>
              <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-slate-400">
                <svg class="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
                </svg>
              </div>
            </div>
          </div>

          <div class="space-y-2">
            <label class="block text-sm font-medium text-slate-300">Secret Key</label>
            <input 
              v-model="form.api_key" 
              type="password" 
              placeholder="sk-..." 
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
            />
            <p class="text-xs text-slate-500 mt-2">Keys are encrypted before being stored in the database.</p>
          </div>

          <!-- Status Message -->
          <div 
            v-if="statusMessage" 
            :class="[
              'p-4 rounded-xl text-sm font-medium transition-all duration-300',
              statusMessage.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'
            ]"
          >
            {{ statusMessage.text }}
          </div>

          <button 
            type="submit" 
            :disabled="isSubmitting"
            class="w-full py-3 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white font-semibold rounded-xl shadow-lg hover:shadow-emerald-500/25 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ isSubmitting ? 'Saving...' : 'Save Configuration' }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>
