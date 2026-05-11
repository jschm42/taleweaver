<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  configuredKeys: Record<string, { masked: string, is_env: boolean }>
  isSubmitting: boolean
}>()

const emit = defineEmits<{
  (e: 'save', payload: { provider: string, api_key: string }): void
  (e: 'delete', provider: string): void
}>()

const keyForm = ref({
  provider: 'openai',
  api_key: ''
})

const handleSave = () => {
  emit('save', { provider: keyForm.value.provider, api_key: keyForm.value.api_key })
  keyForm.value.api_key = ''
}
</script>

<template>
  <div class="space-y-8 animate-fade-in">
    <div>
      <h1 class="text-4xl font-extrabold text-white mb-2">Secure API Management</h1>
      <p class="text-slate-400">Manage encryption keys for your AI providers. Keys are stored locally and never touch our servers.</p>
    </div>

    <div class="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div class="space-y-2">
          <label class="block text-sm font-semibold text-slate-300">Provider</label>
          <select v-model="keyForm.provider" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none">
            <option value="openai">OpenAI</option>
            <option value="google">Google Gemini</option>
            <option value="elevenlabs">ElevenLabs</option>
            <option value="openrouter">OpenRouter</option>
            <option value="deepseek">DeepSeek</option>
            <option value="black_forest_labs">Black Forest Labs</option>
            <option value="anthropic">Anthropic</option>
            <option value="ollama">Ollama (Local, EXPERIMENTAL)</option>
          </select>
        </div>
        <div class="space-y-2">
           <label class="block text-sm font-semibold text-slate-300">Set New API Key</label>
           <input v-if="keyForm.provider !== 'ollama' && !configuredKeys[keyForm.provider]?.is_env" v-model="keyForm.api_key" type="password" placeholder="sk-..." class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none" />
           <div v-else-if="configuredKeys[keyForm.provider]?.is_env" class="w-full bg-amber-500/5 border border-amber-500/20 rounded-xl px-4 py-3 text-amber-500/70 text-sm italic flex items-center gap-2">
             <i class="ra ra-locked"></i>
             This key is managed via environment variables.
           </div>
           <p v-else class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-slate-400 text-sm">No API key needed for local Ollama.</p>
        </div>
      </div>
      <button @click="handleSave" :disabled="isSubmitting || (keyForm.provider !== 'ollama' && !keyForm.api_key) || configuredKeys[keyForm.provider]?.is_env" class="w-full py-4 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition-all shadow-lg disabled:opacity-50">
        {{ isSubmitting ? 'Encrypting...' : configuredKeys[keyForm.provider]?.is_env ? 'Key Managed via ENV' : 'Lock API Key' }}
      </button>
    </div>

    <div class="bg-slate-900/50 border border-slate-800 rounded-2xl p-6">
      <h3 class="text-xs font-bold uppercase tracking-widest text-slate-500 mb-4">Configured Vaults</h3>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div v-if="Object.keys(configuredKeys).length === 0" class="col-span-2 text-slate-600 italic py-4 text-center border border-dashed border-slate-800 rounded-xl">No keys secured yet.</div>
        <div v-for="(info, provider) in configuredKeys" :key="provider" class="flex items-center justify-between p-4 bg-slate-950 border border-slate-800 rounded-xl">
           <div class="flex flex-col">
             <span class="capitalize font-bold text-slate-300">{{ provider }}</span>
             <span v-if="info.is_env" class="text-xxs text-amber-500/80 uppercase font-black tracking-tighter">Imported from ENV</span>
           </div>
           <div class="flex items-center gap-3">
             <span :class="[info.is_env ? 'text-amber-500 bg-amber-500/10' : 'text-emerald-500 bg-emerald-500/10', 'text-xxs font-mono font-black tracking-widest px-2 py-1 rounded']">
               {{ info.is_env ? 'READ-ONLY' : 'SECURED' }}
             </span>
             <button 
               v-if="!info.is_env" 
               @click="emit('delete', provider)" 
               class="p-2 text-slate-600 hover:text-red-500 transition-colors"
               title="Remove this key"
             >
               <i class="ra ra-cancel text-xs"></i>
             </button>
           </div>
        </div>
      </div>
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
