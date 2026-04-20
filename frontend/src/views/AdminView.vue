<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { CatalogTile } from '@/types'

const router = useRouter()

// NAVIGATION
type Section = 'keys' | 'llm' | 't2i' | 'styles' | 'tones'
const activeSection = ref<Section>('keys')

// FORMS
const keyForm = ref({
  provider: 'openai',
  api_key: ''
})

const llmForm = ref({
  small_model: 'openai/gpt-4o-mini',
  complex_model: 'openai/gpt-4o-mini',
  preferred_provider: 'openai',
  ollama_url: 'http://localhost:11434',
})

const t2iForm = ref({
  simple_model: 'openai/dall-e-2',
  advanced_model: 'openai/dall-e-3',
  provider: 'openai',
  ollama_url: 'http://localhost:11434',
  width: null as number | null,
  height: null as number | null,
  steps: null as number | null,
  seed: null as number | null,
  image_format: 'jpeg',
  image_quality: 85,
  negative_prompt: '',
})

// STATE
const configuredKeys = ref<Record<string, string>>({})
const isSubmitting = ref(false)
const statusMessage = ref<{ type: 'success' | 'error', text: string } | null>(null)
const imageStylesCatalog = ref<CatalogTile[]>([])
const toneCatalog = ref<CatalogTile[]>([])
const newStyle = ref<CatalogTile>({ id: '', name: '', description: '', instruction: '', image_url: '' })
const newTone = ref<CatalogTile>({ id: '', name: '', description: '', instruction: '', image_url: '' })

const goBack = () => {
  router.push({ name: 'portal' })
}

const fetchSettings = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/settings')
    if (res.ok) {
      const data = await res.json()
      configuredKeys.value = data.keys || {}
      if (data.llm_settings) llmForm.value = { ...data.llm_settings }
      if (data.t2i_settings) t2iForm.value = { ...data.t2i_settings }
      imageStylesCatalog.value = data.image_styles_catalog || []
      toneCatalog.value = data.tone_catalog || []
    }
  } catch (error) {
    console.error('Failed to fetch settings', error)
  }
}

const slugify = (value: string): string =>
  value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') || 'item'

const addStyleTile = () => {
  if (!newStyle.value.name?.trim()) {
    statusMessage.value = { type: 'error', text: 'Style name is required.' }
    return
  }
  imageStylesCatalog.value = [
    ...imageStylesCatalog.value,
    {
      id: newStyle.value.id?.trim() || slugify(newStyle.value.name),
      name: newStyle.value.name.trim(),
      description: (newStyle.value.description || '').trim(),
      instruction: (newStyle.value.instruction || '').trim(),
      image_url: (newStyle.value.image_url || '').trim() || null,
    },
  ]
  newStyle.value = { id: '', name: '', description: '', instruction: '', image_url: '' }
}

const addToneTile = () => {
  if (!newTone.value.name?.trim()) {
    statusMessage.value = { type: 'error', text: 'Tone name is required.' }
    return
  }
  toneCatalog.value = [
    ...toneCatalog.value,
    {
      id: newTone.value.id?.trim() || slugify(newTone.value.name),
      name: newTone.value.name.trim(),
      description: (newTone.value.description || '').trim(),
      instruction: (newTone.value.instruction || '').trim(),
      image_url: (newTone.value.image_url || '').trim() || null,
    },
  ]
  newTone.value = { id: '', name: '', description: '', instruction: '', image_url: '' }
}

const removeStyleTile = (index: number) => {
  imageStylesCatalog.value = imageStylesCatalog.value.filter((_, i) => i !== index)
}

const removeToneTile = (index: number) => {
  toneCatalog.value = toneCatalog.value.filter((_, i) => i !== index)
}

const saveStylesCatalog = async () => {
  isSubmitting.value = true
  statusMessage.value = null
  try {
    const res = await fetch('http://localhost:8000/api/settings/image-styles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: imageStylesCatalog.value }),
    })
    if (res.ok) {
      statusMessage.value = { type: 'success', text: 'Image styles updated.' }
      await fetchSettings()
    } else {
      statusMessage.value = { type: 'error', text: 'Failed to save image styles.' }
    }
  } catch {
    statusMessage.value = { type: 'error', text: 'Network error while saving image styles.' }
  } finally {
    isSubmitting.value = false
  }
}

const saveToneCatalog = async () => {
  isSubmitting.value = true
  statusMessage.value = null
  try {
    const res = await fetch('http://localhost:8000/api/settings/tones', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: toneCatalog.value }),
    })
    if (res.ok) {
      statusMessage.value = { type: 'success', text: 'Tones updated.' }
      await fetchSettings()
    } else {
      statusMessage.value = { type: 'error', text: 'Failed to save tones.' }
    }
  } catch {
    statusMessage.value = { type: 'error', text: 'Network error while saving tones.' }
  } finally {
    isSubmitting.value = false
  }
}

const saveApiKey = async () => {
  if (keyForm.value.provider === 'ollama') {
    statusMessage.value = { type: 'success', text: 'Ollama nutzt lokal keinen API Key.' }
    return
  }
  if (!keyForm.value.api_key.trim()) return
  isSubmitting.value = true
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
    isSubmitting.value = false
  }
}

const saveLlmSettings = async () => {
  isSubmitting.value = true
  statusMessage.value = null
  try {
    const res = await fetch('http://localhost:8000/api/settings/llm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(llmForm.value)
    })
    if (res.ok) statusMessage.value = { type: 'success', text: 'Intelligence preferences updated.' }
  } catch (error) {
    statusMessage.value = { type: 'error', text: 'Network error.' }
  } finally {
    isSubmitting.value = false
  }
}

const saveT2iSettings = async () => {
  isSubmitting.value = true
  statusMessage.value = null
  try {
    const res = await fetch('http://localhost:8000/api/settings/t2i', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(t2iForm.value)
    })
    if (res.ok) statusMessage.value = { type: 'success', text: 'Visual preferences updated.' }
  } catch (error) {
    statusMessage.value = { type: 'error', text: 'Network error.' }
  } finally {
    isSubmitting.value = false
  }
}

onMounted(() => {
  fetchSettings()
})

watch(
  () => t2iForm.value.provider,
  (provider) => {
    if (provider === 'black_forest_labs') {
      const looksLikeCloudModel = (value: string) => value.startsWith('openai/') || value.startsWith('dall-e') || value.startsWith('openrouter/') || value.startsWith('midjourney/')
      if (!t2iForm.value.simple_model || looksLikeCloudModel(t2iForm.value.simple_model)) {
        t2iForm.value.simple_model = 'flux-dev'
      }
      if (!t2iForm.value.advanced_model || looksLikeCloudModel(t2iForm.value.advanced_model)) {
        t2iForm.value.advanced_model = 'flux-pro-1.1'
      }
      return
    }

    if (provider !== 'ollama') {
      return
    }

    const looksLikeCloudModel = (value: string) => value.startsWith('openai/') || value.startsWith('dall-e')
    if (!t2iForm.value.simple_model || looksLikeCloudModel(t2iForm.value.simple_model)) {
      t2iForm.value.simple_model = 'x/flux2-klein'
    }
    if (!t2iForm.value.advanced_model || looksLikeCloudModel(t2iForm.value.advanced_model)) {
      t2iForm.value.advanced_model = 'x/flux2-klein'
    }
    if (!t2iForm.value.ollama_url) {
      t2iForm.value.ollama_url = 'http://localhost:11434'
    }
  },
)
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 font-sans flex overflow-hidden">
    
    <!-- SIDEBAR -->
    <aside class="w-72 bg-slate-900 border-r border-slate-800 flex flex-col p-6 h-screen sticky top-0">
      <div class="flex items-center gap-4 mb-10">
        <button @click="goBack" class="p-2 rounded-lg bg-slate-950 border border-slate-800 hover:bg-slate-800 transition-colors">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" />
          </svg>
        </button>
        <h2 class="text-xl font-bold tracking-tight">Configuration</h2>
      </div>

      <nav class="flex-grow space-y-2">
        <button 
          @click="activeSection = 'keys'"
          :class="['w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300', activeSection === 'keys' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300']"
        >
          <i class="ra ra-locked"></i>
          <span class="font-semibold text-sm">Provider Keys</span>
        </button>
        <button 
          @click="activeSection = 'llm'"
          :class="['w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 uppercase tracking-tight', activeSection === 'llm' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300']"
        >
          <i class="ra ra-brain"></i>
          <span class="font-bold text-xs font-mono">Intelligence</span>
        </button>
        <button 
          @click="activeSection = 't2i'"
          :class="['w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 uppercase tracking-tight', activeSection === 't2i' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300']"
        >
          <i class="ra ra-camera"></i>
          <span class="font-bold text-xs font-mono">Visuals</span>
        </button>
        <button
          @click="activeSection = 'styles'"
          :class="['w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300', activeSection === 'styles' ? 'bg-amber-500/10 text-amber-300 border border-amber-500/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300']"
        >
          <i class="ra ra-paint-brush"></i>
          <span class="font-semibold text-sm">Image Styles</span>
        </button>
        <button
          @click="activeSection = 'tones'"
          :class="['w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300', activeSection === 'tones' ? 'bg-pink-500/10 text-pink-300 border border-pink-500/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300']"
        >
          <i class="ra ra-scroll-unfurled"></i>
          <span class="font-semibold text-sm">World Tones</span>
        </button>
      </nav>

      <div class="mt-auto pt-6 border-t border-slate-800 opacity-50">
        <div class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">TaleWeaver Engine v0.1.0</div>
      </div>
    </aside>

    <!-- CONTENT AREA -->
    <main class="flex-grow p-12 overflow-y-auto max-h-screen custom-scrollbar">
      <div class="max-w-3xl mx-auto">
        
        <!-- SECTION: KEYS -->
        <div v-if="activeSection === 'keys'" class="space-y-8 animate-fade-in">
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
                  <option value="openrouter">OpenRouter</option>
                  <option value="midjourney">Midjourney / Proxy</option>
                  <option value="black_forest_labs">Black Forest Labs</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="ollama">Ollama (Local)</option>
                </select>
              </div>
              <div class="space-y-2">
                 <label class="block text-sm font-semibold text-slate-300">Set New API Key</label>
                 <input v-if="keyForm.provider !== 'ollama'" v-model="keyForm.api_key" type="password" placeholder="sk-..." class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none" />
                 <p v-else class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-slate-400 text-sm">No API key needed for local Ollama.</p>
              </div>
            </div>
            <button @click="saveApiKey" :disabled="isSubmitting || (keyForm.provider !== 'ollama' && !keyForm.api_key)" class="w-full py-4 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition-all shadow-lg disabled:opacity-50">
              {{ isSubmitting ? 'Encrypting...' : 'Lock API Key' }}
            </button>
          </div>

          <div class="bg-slate-900/50 border border-slate-800 rounded-2xl p-6">
            <h3 class="text-xs font-bold uppercase tracking-widest text-slate-500 mb-4">Configured Vaults</h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div v-if="Object.keys(configuredKeys).length === 0" class="col-span-2 text-slate-600 italic py-4 text-center border border-dashed border-slate-800 rounded-xl">No keys secured yet.</div>
              <div v-for="(_, provider) in configuredKeys" :key="provider" class="flex items-center justify-between p-4 bg-slate-950 border border-slate-800 rounded-xl">
                 <span class="capitalize font-bold text-slate-300">{{ provider }}</span>
                 <span class="text-emerald-500 text-[10px] font-mono font-black tracking-widest bg-emerald-500/10 px-2 py-1 rounded">SECURED</span>
              </div>
            </div>
          </div>
        </div>

        <!-- SECTION: LLM -->
        <div v-if="activeSection === 'llm'" class="space-y-8 animate-fade-in">
          <div>
            <h1 class="text-4xl font-extrabold text-white mb-2">Intelligence Routing</h1>
            <p class="text-slate-400">Configure how the game handles simple narrative vs complex mechanics.</p>
          </div>

          <div class="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
            <div class="space-y-2">
              <label class="block text-sm font-semibold text-slate-300">Preferred Provider (Routing)</label>
              <select v-model="llmForm.preferred_provider" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-purple-500/50 outline-none font-bold">
                <option value="openai">OpenAI</option>
                <option value="openrouter">OpenRouter</option>
                <option value="anthropic">Anthropic</option>
                <option value="ollama">Ollama (Local)</option>
              </select>
            </div>

            <div v-if="llmForm.preferred_provider === 'ollama'" class="space-y-2">
              <label class="block text-sm font-semibold text-slate-300">Ollama URL</label>
              <input v-model="llmForm.ollama_url" type="text" placeholder="http://localhost:11434" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50" />
              <p class="text-[10px] text-slate-500">Local endpoint used for chat completions.</p>
            </div>

            <div class="space-y-2">
              <label class="block text-sm font-semibold text-slate-300">Simple Model (Narratives)</label>
              <input v-model="llmForm.small_model" type="text" placeholder="e.g. gpt-4o-mini" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50" />
              <p class="text-[10px] text-slate-500">Efficient logic and low-latency chatter.</p>
            </div>

            <div class="space-y-2">
              <label class="block text-sm font-semibold text-slate-300">Complex Model (Mechanics)</label>
              <input v-model="llmForm.complex_model" type="text" placeholder="e.g. gpt-4o" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50" />
              <p class="text-[10px] text-slate-500">Heavy reasoning, complex math, and structured data state.</p>
            </div>

            <button @click="saveLlmSettings" :disabled="isSubmitting" class="w-full py-4 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-xl transition-all shadow-lg disabled:opacity-50">
               {{ isSubmitting ? 'Optimizing...' : 'Update Intelligence Paths' }}
            </button>
          </div>
        </div>

        <!-- SECTION: T2I -->
        <div v-if="activeSection === 't2i'" class="space-y-8 animate-fade-in">
          <div>
            <h1 class="text-4xl font-extrabold text-white mb-2">Visual Generation</h1>
            <p class="text-slate-400">Set up AI artists for your world portraits and scene visualizations.</p>
          </div>

          <div class="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
            <div class="space-y-2">
              <label class="block text-sm font-semibold text-slate-300">Image Provider</label>
              <select v-model="t2iForm.provider" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-cyan-500/50 outline-none font-bold">
                <option value="openai">OpenAI (DALL-E)</option>
                <option value="openrouter">OpenRouter (Various)</option>
                <option value="midjourney">Midjourney (via Proxy)</option>
                <option value="black_forest_labs">Black Forest Labs (FLUX)</option>
                <option value="ollama">Ollama (Local, Experimental)</option>
              </select>
              <p v-if="t2iForm.provider === 'black_forest_labs'" class="text-[10px] text-slate-500 uppercase tracking-widest font-bold">
                BFL uses `black_forest_labs/flux-dev` for simple images and `black_forest_labs/flux-pro-1.1` for scenes unless you override them.
              </p>
            </div>

            <div v-if="t2iForm.provider === 'ollama'" class="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-4 text-cyan-200 text-sm">
              Experimental: Local image generation with Ollama. Make sure your Ollama server is running and the model is pulled.
            </div>

            <div class="space-y-2 font-mono">
              <label class="block text-sm font-semibold text-slate-300">Simple Image Model (NPCs & Objects)</label>
              <input
                v-model="t2iForm.simple_model"
                type="text"
                :placeholder="t2iForm.provider === 'black_forest_labs' ? 'e.g. flux-dev' : 'e.g. dall-e-2'"
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50"
              />
              <p class="text-[10px] text-slate-500 uppercase tracking-widest font-bold">Fast portraits during world gen.</p>
            </div>

            <div class="space-y-2 font-mono">
              <label class="block text-sm font-semibold text-slate-300">Advanced Image Model (Scenes)</label>
              <input
                v-model="t2iForm.advanced_model"
                type="text"
                :placeholder="t2iForm.provider === 'black_forest_labs' ? 'e.g. flux-pro-1.1' : 'e.g. dall-e-3'"
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50"
              />
              <p class="text-[10px] text-slate-500 uppercase tracking-widest font-bold">High-fidelity scene visualization.</p>
            </div>

            <!-- STORAGE OPTIMIZATION -->
            <div class="pt-6 border-t border-slate-800 space-y-6">
              <div class="flex items-center gap-2 mb-2">
                <i class="ra ra-save text-cyan-400"></i>
                <h3 class="text-xs font-bold uppercase tracking-widest text-slate-500">Storage Optimization</h3>
              </div>
              
              <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="space-y-2">
                  <label class="block text-sm font-semibold text-slate-300">File Format</label>
                  <select v-model="t2iForm.image_format" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-cyan-500/50 outline-none">
                    <option value="jpeg">JPEG (Recommended)</option>
                    <option value="png">PNG (Lossless)</option>
                  </select>
                  <p class="text-[10px] text-slate-500">JPEG significantly reduces file size for assets.</p>
                </div>
                
                <div v-if="t2iForm.image_format === 'jpeg'" class="space-y-2">
                  <div class="flex justify-between items-center mb-1">
                    <label class="block text-sm font-semibold text-slate-300">JPEG Quality</label>
                    <span class="text-xs font-mono font-bold text-cyan-400 bg-cyan-400/10 px-2 py-0.5 rounded">{{ t2iForm.image_quality }}%</span>
                  </div>
                  <input v-model.number="t2iForm.image_quality" type="range" min="10" max="100" step="5" class="w-full h-2 bg-slate-950 border border-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-500" />
                  <div class="flex justify-between text-[10px] text-slate-500 font-mono">
                    <span>Small File</span>
                    <span>Best Quality</span>
                  </div>
                </div>
              </div>
            </div>

            <template v-if="t2iForm.provider === 'ollama'">
              <div class="space-y-2 font-mono">
                <label class="block text-sm font-semibold text-slate-300">Ollama URL</label>
                <input v-model="t2iForm.ollama_url" type="text" placeholder="http://localhost:11434" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50" />
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="space-y-2 font-mono">
                  <label class="block text-sm font-semibold text-slate-300">Width (optional)</label>
                  <input v-model.number="t2iForm.width" type="number" min="64" step="1" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50" />
                </div>
                <div class="space-y-2 font-mono">
                  <label class="block text-sm font-semibold text-slate-300">Height (optional)</label>
                  <input v-model.number="t2iForm.height" type="number" min="64" step="1" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50" />
                </div>
                <div class="space-y-2 font-mono">
                  <label class="block text-sm font-semibold text-slate-300">Steps (optional)</label>
                  <input v-model.number="t2iForm.steps" type="number" min="1" step="1" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50" />
                </div>
                <div class="space-y-2 font-mono">
                  <label class="block text-sm font-semibold text-slate-300">Seed (optional)</label>
                  <input v-model.number="t2iForm.seed" type="number" step="1" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50" />
                </div>
              </div>

              <div class="space-y-2 font-mono">
                <label class="block text-sm font-semibold text-slate-300">Negative Prompt (optional)</label>
                <input v-model="t2iForm.negative_prompt" type="text" placeholder="e.g. blurry, artifacts, low quality" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50" />
              </div>
            </template>

            <button @click="saveT2iSettings" :disabled="isSubmitting" class="w-full py-4 bg-cyan-600 hover:bg-cyan-500 text-white font-bold rounded-xl transition-all shadow-lg disabled:opacity-50">
               {{ isSubmitting ? 'Painting...' : 'Update Visual Artists' }}
            </button>
          </div>
        </div>

        <!-- SECTION: IMAGE STYLES -->
        <div v-if="activeSection === 'styles'" class="space-y-8 animate-fade-in">
          <div>
            <h1 class="text-4xl font-extrabold text-white mb-2">Image Style Catalog</h1>
            <p class="text-slate-400">Define selectable visual styles used during adventure image generation.</p>
          </div>

          <div class="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input v-model="newStyle.name" type="text" placeholder="Name (e.g. Gothic Ink)" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white" />
              <input v-model="newStyle.id" type="text" placeholder="Optional ID (auto from name)" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white" />
              <input v-model="newStyle.image_url" type="text" placeholder="Optional image URL" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white md:col-span-2" />
              <textarea v-model="newStyle.description" rows="2" placeholder="Description" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
              <textarea v-model="newStyle.instruction" rows="2" placeholder="Prompt instruction injected for selected styles" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
            </div>
            <button @click="addStyleTile" class="w-full py-3 bg-amber-600 hover:bg-amber-500 text-white font-bold rounded-xl">Add Style Tile</button>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div v-for="(style, index) in imageStylesCatalog" :key="style.id + '-' + index" class="bg-slate-950 border border-slate-800 rounded-2xl p-4 space-y-3">
                <img v-if="style.image_url" :src="style.image_url" class="w-full h-28 object-cover rounded-lg border border-slate-800" />
                <input v-model="style.name" type="text" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-white" />
                <input v-model="style.id" type="text" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-white" />
                <input v-model="style.image_url" type="text" placeholder="Optional image URL" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-white" />
                <textarea v-model="style.description" rows="2" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-white resize-none"></textarea>
                <textarea v-model="style.instruction" rows="2" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-white resize-none"></textarea>
                <button @click="removeStyleTile(index)" class="w-full py-2 text-sm rounded-lg bg-red-500/15 border border-red-500/30 text-red-200 hover:bg-red-500/25">Remove</button>
              </div>
            </div>

            <button @click="saveStylesCatalog" :disabled="isSubmitting" class="w-full py-4 bg-amber-600 hover:bg-amber-500 text-white font-bold rounded-xl disabled:opacity-50">
              {{ isSubmitting ? 'Saving...' : 'Save Image Styles' }}
            </button>
          </div>
        </div>

        <!-- SECTION: TONES -->
        <div v-if="activeSection === 'tones'" class="space-y-8 animate-fade-in">
          <div>
            <h1 class="text-4xl font-extrabold text-white mb-2">World Tone Catalog</h1>
            <p class="text-slate-400">Define selectable tone presets used for story/world generation.</p>
          </div>

          <div class="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input v-model="newTone.name" type="text" placeholder="Name (e.g. Horror, Sci-Fi, Sitcom)" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white" />
              <input v-model="newTone.id" type="text" placeholder="Optional ID (auto from name)" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white" />
              <input v-model="newTone.image_url" type="text" placeholder="Optional image URL" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white md:col-span-2" />
              <textarea v-model="newTone.description" rows="2" placeholder="Description" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
              <textarea v-model="newTone.instruction" rows="2" placeholder="Tone instruction used in story generation" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
            </div>
            <button @click="addToneTile" class="w-full py-3 bg-pink-600 hover:bg-pink-500 text-white font-bold rounded-xl">Add Tone Tile</button>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div v-for="(tone, index) in toneCatalog" :key="tone.id + '-' + index" class="bg-slate-950 border border-slate-800 rounded-2xl p-4 space-y-3">
                <img v-if="tone.image_url" :src="tone.image_url" class="w-full h-28 object-cover rounded-lg border border-slate-800" />
                <input v-model="tone.name" type="text" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-white" />
                <input v-model="tone.id" type="text" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-white" />
                <input v-model="tone.image_url" type="text" placeholder="Optional image URL" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-white" />
                <textarea v-model="tone.description" rows="2" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-white resize-none"></textarea>
                <textarea v-model="tone.instruction" rows="2" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-white resize-none"></textarea>
                <button @click="removeToneTile(index)" class="w-full py-2 text-sm rounded-lg bg-red-500/15 border border-red-500/30 text-red-200 hover:bg-red-500/25">Remove</button>
              </div>
            </div>

            <button @click="saveToneCatalog" :disabled="isSubmitting" class="w-full py-4 bg-pink-600 hover:bg-pink-500 text-white font-bold rounded-xl disabled:opacity-50">
              {{ isSubmitting ? 'Saving...' : 'Save Tones' }}
            </button>
          </div>
        </div>

        <!-- STATUS MESSAGE FLOATER -->
        <div v-if="statusMessage" 
          :class="['fixed bottom-12 right-12 px-6 py-4 rounded-2xl shadow-2xl text-sm font-bold border max-w-sm animate-slide-in', 
          statusMessage.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20']"
        >
          <div class="flex items-center gap-3">
            <i :class="statusMessage.type === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
            {{ statusMessage.text }}
          </div>
        </div>

      </div>
    </main>
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

.animate-slide-in {
  animation: slideIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
@keyframes slideIn {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.05);
  border-radius: 10px;
}
</style>
