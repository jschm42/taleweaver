<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { configState, refreshConfig } from '@/store/config'
import type { CatalogTile } from '@/types'

const router = useRouter()

// NAVIGATION
type Section = 'keys' | 'llm' | 't2i' | 'styles' | 'tones' | 'game' | 'users'
const activeSection = ref<Section>('keys')

import { api } from '@/composables/useApi'

// FORMS
const keyForm = ref({
  provider: 'openai',
  api_key: ''
})

const llmForm = ref({
  small_model: '',
  small_model_provider: 'openai',
  small_max_tokens: 4096,
  small_enable_thinking: false,
  small_max_thinking_tokens: 1024,
  
  complex_model: '',
  complex_model_provider: 'openai',
  complex_max_tokens: 4096,
  complex_enable_thinking: false,
  complex_max_thinking_tokens: 1024,
  
  preferred_provider: 'openai',
  ollama_url: 'http://localhost:11434',
})

const t2iForm = ref({
  simple_model: '',
  simple_model_provider: 'openai',
  advanced_model: '',
  advanced_model_provider: 'openai',
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

const gameForm = ref({
  clock_24h: false,
  date_format: 'DD.MM.YY',
})

// CONSTANTS FROM BACKEND
const availableConstants = ref({
  llm_providers: [] as { id: string, name: string }[],
  image_providers: [] as { id: string, name: string }[],
  predefined_llm_models: {} as Record<string, string[]>,
  predefined_image_models: {} as Record<string, string[]>,
})

// TEST STATE
const testResults = ref<Record<string, { status: 'loading' | 'success' | 'error', message: string, image_url?: string }>>({})

// STATE
const configuredKeys = ref<Record<string, { masked: string, is_env: boolean }>>({})
const isSubmitting = ref(false)
const statusMessage = ref<{ type: 'success' | 'error', text: string } | null>(null)
const imageStylesCatalog = ref<CatalogTile[]>([])
const toneCatalog = ref<CatalogTile[]>([])
const isHydratingSettings = ref(false)

// MODAL STATE
const isCatalogModalOpen = ref(false)
const catalogModalType = ref<'styles' | 'tones'>('styles')
const editingItem = ref<CatalogTile>({ id: '', name: '', description: '', instruction: '', image_url: '' })
const isEditingExisting = ref(false)
const editingIndex = ref<number | null>(null)

// USER MGMT STATE
const usersList = ref<any[]>([])
const isUserModalOpen = ref(false)
const editingUser = ref<any>({ username: '', password: '', role: 'user', bio: '' })
const isEditingExistingUser = ref(false)

const isPromptModalOpen = ref(false)
const promptModalData = ref<{ type: 'styles' | 'tones', item: CatalogTile, index: number } | null>(null)
const customPrompt = ref('')

const isGeneratingItem = ref<Record<string, boolean>>({})
const openMenuId = ref<string | null>(null)

const goBack = () => {
  router.push({ name: 'portal' })
}

const fetchSettings = async () => {
  try {
    isHydratingSettings.value = true
    const data = await api.getSettings()
    configuredKeys.value = data.keys || {}
    if (data.llm_settings) llmForm.value = { ...data.llm_settings as any }
    if (data.t2i_settings) t2iForm.value = { ...data.t2i_settings as any }
    if (data.game_settings) gameForm.value = { ...data.game_settings as any }
    if ((data as any).available_constants) availableConstants.value = (data as any).available_constants
    imageStylesCatalog.value = data.image_styles_catalog || []
    toneCatalog.value = data.tone_catalog || []
  } catch (error) {
    console.error('Failed to fetch settings', error)
  } finally {
    isHydratingSettings.value = false
  }
}

const fetchUsers = async () => {
  try {
    usersList.value = await api.listUsers()
  } catch (error) {
    console.error('Failed to fetch users', error)
  }
}

const openUserModal = (user?: any) => {
  if (user) {
    editingUser.value = { ...user, password: '' }
    isEditingExistingUser.value = true
  } else {
    editingUser.value = { username: '', password: '', role: 'user', bio: '' }
    isEditingExistingUser.value = false
  }
  isUserModalOpen.value = true
}

const saveUser = async () => {
  if (!editingUser.value.username) return
  isSubmitting.value = true
  try {
    if (isEditingExistingUser.value) {
      await api.updateUser(editingUser.value.id, editingUser.value)
      statusMessage.value = { type: 'success', text: 'User updated.' }
    } else {
      await api.createUser(editingUser.value)
      statusMessage.value = { type: 'success', text: 'User created.' }
    }
    isUserModalOpen.value = false
    fetchUsers()
  } catch (err: any) {
    statusMessage.value = { type: 'error', text: 'Operation failed: ' + err.message }
  } finally {
    isSubmitting.value = false
  }
}

const removeUser = async (user: any) => {
  if (!confirm(`Are you sure you want to delete user "${user.username}"?`)) return
  try {
    await api.deleteUser(user.id)
    fetchUsers()
    statusMessage.value = { type: 'success', text: 'User removed.' }
  } catch (err: any) {
    statusMessage.value = { type: 'error', text: 'Delete failed: ' + err.message }
  }
}

const slugify = (value: string): string =>
  value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') || 'item'

const openCatalogModal = (type: 'styles' | 'tones', item?: CatalogTile, index?: number) => {
  catalogModalType.value = type
  if (item) {
    editingItem.value = JSON.parse(JSON.stringify(item))
    isEditingExisting.value = true
    editingIndex.value = index ?? null
  } else {
    editingItem.value = { id: '', name: '', description: '', instruction: '', image_url: '' }
    isEditingExisting.value = false
    editingIndex.value = null
  }
  isCatalogModalOpen.value = true
}

const saveCatalogItem = () => {
  if (!editingItem.value.name?.trim()) {
    statusMessage.value = { type: 'error', text: 'Name is required.' }
    return
  }

  const item: CatalogTile = {
    ...editingItem.value,
    id: editingItem.value.id?.trim() || slugify(editingItem.value.name),
    name: editingItem.value.name.trim(),
    description: (editingItem.value.description || '').trim(),
    instruction: (editingItem.value.instruction || '').trim(),
    image_url: (editingItem.value.image_url || '').trim() || null,
  }

  const catalog = catalogModalType.value === 'styles' ? imageStylesCatalog : toneCatalog
  
  if (isEditingExisting.value && editingIndex.value !== null) {
    catalog.value[editingIndex.value] = item
  } else {
    catalog.value.push(item)
  }

  isCatalogModalOpen.value = false
  saveCurrentCatalog()
}

const removeCatalogItem = (type: 'styles' | 'tones', index: number) => {
  if (!confirm('Are you sure you want to delete this item?')) return
  const catalog = type === 'styles' ? imageStylesCatalog : toneCatalog
  catalog.value.splice(index, 1)
  saveCurrentCatalog()
}

const saveCurrentCatalog = async (type?: 'styles' | 'tones') => {
  const targetType = type || catalogModalType.value
  if (targetType === 'styles') await saveStylesCatalog()
  else await saveToneCatalog()
}

const saveStylesCatalog = async () => {
  isSubmitting.value = true
  statusMessage.value = null
  try {
    await api.saveImageStylesCatalog(imageStylesCatalog.value)
    statusMessage.value = { type: 'success', text: 'Image styles updated.' }
  } catch {
    statusMessage.value = { type: 'error', text: 'Failed to save image styles.' }
  } finally {
    isSubmitting.value = false
  }
}

const saveToneCatalog = async () => {
  isSubmitting.value = true
  statusMessage.value = null
  try {
    await api.saveToneCatalog(toneCatalog.value)
    statusMessage.value = { type: 'success', text: 'Tones updated.' }
  } catch {
    statusMessage.value = { type: 'error', text: 'Failed to save tones.' }
  } finally {
    isSubmitting.value = false
  }
}

const openPromptModal = (type: 'styles' | 'tones', item: CatalogTile, index: number) => {
  promptModalData.value = { type, item, index }
  customPrompt.value = ''
  isPromptModalOpen.value = true
}

const generateCatalogImage = async (type: 'styles' | 'tones', item: CatalogTile, index: number | null = null, prompt: string | null = null) => {
  if (!t2iForm.value.simple_model) {
    statusMessage.value = { type: 'error', text: 'Please configure and save the "Simple Model" in Visual Preferences before generating catalog images.' }
    return
  }
  
  // If in modal and we have a name but no id, slugify it now
  const targetId = item.id || slugify(item.name)
  if (!targetId) {
    statusMessage.value = { type: 'error', text: 'Please provide a name before generating an image.' }
    return
  }

  const key = index !== null ? `${type}_${index}` : 'modal_generating'
  isGeneratingItem.value[key] = true
  isPromptModalOpen.value = false // Close prompt modal if it was open
  
  try {
    const data = await api.generateCatalogImage({
      target_id: targetId,
      catalog_type: type,
      prompt: prompt,
      name: item.name,
      description: item.description
    })
    
    if (data.status === 'success') {
      item.image_url = data.image_url
      if (index !== null) {
        const catalog = type === 'styles' ? imageStylesCatalog : toneCatalog
        catalog.value[index].image_url = data.image_url
        await saveCurrentCatalog(type)
      }
    } else {
      statusMessage.value = { type: 'error', text: data.message || 'Generation failed.' }
    }
  } catch (error) {
    statusMessage.value = { type: 'error', text: 'Error during generation.' }
  } finally {
    isGeneratingItem.value[key] = false
  }
}

const triggerFileUpload = (id: string) => {
  const input = document.getElementById(id) as HTMLInputElement
  input?.click()
}

const onUploadFile = async (event: Event, type: 'styles' | 'tones', item: CatalogTile, index: number | null = null) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)
  formData.append('catalog_type', type)
  formData.append('target_id', item.id || slugify(item.name))

  try {
    const data = await api.uploadCatalogImage(formData)
    if (data.status === 'success') {
      item.image_url = data.image_url
      if (index !== null) {
        const catalog = type === 'styles' ? imageStylesCatalog : toneCatalog
        catalog.value[index].image_url = data.image_url
        await saveCurrentCatalog(type)
      }
    } else {
      statusMessage.value = { type: 'error', text: data.message || 'Upload failed.' }
    }
  } catch (error) {
    statusMessage.value = { type: 'error', text: 'Error during upload.' }
  } finally {
    input.value = ''
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
    await api.saveApiKey(keyForm.value.provider, keyForm.value.api_key)
    statusMessage.value = { type: 'success', text: `${keyForm.value.provider} key saved securely.` }
    keyForm.value.api_key = ''
    await fetchSettings()
    await refreshConfig()
  } catch (error) {
    statusMessage.value = { type: 'error', text: 'Failed to save key.' }
  } finally {
    isSubmitting.value = false
  }
}

const saveLlmSettings = async () => {
  isSubmitting.value = true
  statusMessage.value = null
  try {
    await api.saveLlmSettings(llmForm.value)
    statusMessage.value = { type: 'success', text: 'Intelligence preferences updated.' }
    await refreshConfig()
  } catch (error) {
    statusMessage.value = { type: 'error', text: 'Failed to save intelligence preferences.' }
  } finally {
    isSubmitting.value = false
  }
}

const saveT2iSettings = async () => {
  isSubmitting.value = true
  statusMessage.value = null
  try {
    await api.saveT2iSettings(t2iForm.value)
    statusMessage.value = { type: 'success', text: 'Visual preferences updated.' }
    await refreshConfig()
  } catch (error) {
    statusMessage.value = { type: 'error', text: 'Failed to save visual preferences.' }
  } finally {
    isSubmitting.value = false
  }
}

const testLlm = async (key: string, model: string, provider: string) => {
  testResults.value[key] = { status: 'loading', message: 'Testing connection...' }
  try {
    const data = await api.testLlm({ model, provider, ollama_url: llmForm.value.ollama_url })
    testResults.value[key] = { 
      status: data.status === 'success' ? 'success' : 'error', 
      message: data.response_time ? `${data.message} (${data.response_time}s)` : data.message 
    }
  } catch (err) {
    testResults.value[key] = { status: 'error', message: 'Test failed.' }
  }
}

const testVision = async (key: string, model: string, provider: string) => {
  testResults.value[key] = { status: 'loading', message: 'Generating test image...' }
  try {
    const data = await api.testVision({ model, provider, ollama_url: t2iForm.value.ollama_url })
    testResults.value[key] = { 
      status: data.status === 'success' ? 'success' : 'error', 
      message: data.message,
      image_url: data.image_url
    }
  } catch (err) {
    testResults.value[key] = { status: 'error', message: 'Test failed.' }
  }
}

const isModelCustom = (model: string, provider: string, type: 'llm' | 'image') => {
  if (!model) return false
  const predefined = type === 'llm' 
    ? availableConstants.value.predefined_llm_models[provider] 
    : availableConstants.value.predefined_image_models[provider]
  if (!predefined) return true
  return !predefined.includes(model)
}

const resolveModelOnProviderChange = (
  currentModel: string,
  newProvider: string,
  oldProvider: string | undefined,
  type: 'llm' | 'image',
) => {
  const getPredefined = (provider: string | undefined) => {
    if (!provider) return [] as string[]
    return type === 'llm'
      ? (availableConstants.value.predefined_llm_models[provider] || [])
      : (availableConstants.value.predefined_image_models[provider] || [])
  }

  const nextPredefined = getPredefined(newProvider)
  if (nextPredefined.length === 0) return currentModel
  if (!currentModel) return nextPredefined[0]

  if (nextPredefined.includes(currentModel)) return currentModel

  const prevPredefined = getPredefined(oldProvider)
  if (prevPredefined.includes(currentModel)) return nextPredefined[0]

  // Keep custom model ids unchanged across provider churn.
  return currentModel
}

onMounted(() => {
  fetchSettings()
  fetchUsers()
})

watch(
  () => t2iForm.value.simple_model_provider,
  (provider, oldProvider) => {
    if (isHydratingSettings.value) return
    t2iForm.value.simple_model = resolveModelOnProviderChange(
      t2iForm.value.simple_model,
      provider,
      oldProvider,
      'image',
    )
  }
)

watch(
  () => t2iForm.value.advanced_model_provider,
  (provider, oldProvider) => {
    if (isHydratingSettings.value) return
    t2iForm.value.advanced_model = resolveModelOnProviderChange(
      t2iForm.value.advanced_model,
      provider,
      oldProvider,
      'image',
    )
  }
)

watch(
  () => llmForm.value.small_model_provider,
  (provider, oldProvider) => {
    if (isHydratingSettings.value) return
    llmForm.value.small_model = resolveModelOnProviderChange(
      llmForm.value.small_model,
      provider,
      oldProvider,
      'llm',
    )
  }
)

watch(
  () => llmForm.value.complex_model_provider,
  (provider, oldProvider) => {
    if (isHydratingSettings.value) return
    llmForm.value.complex_model = resolveModelOnProviderChange(
      llmForm.value.complex_model,
      provider,
      oldProvider,
      'llm',
    )
  }
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
          <span class="font-bold text-md font-mono uppercase tracking-widest">Provider Keys</span>
        </button>
        <button 
          @click="activeSection = 'llm'"
          :class="['w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300', activeSection === 'llm' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300']"
        >
          <i class="ra ra-brain"></i>
          <span class="font-bold text-md font-mono uppercase tracking-widest">Intelligence</span>
        </button>
        <button 
          @click="activeSection = 't2i'"
          :class="['w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300', activeSection === 't2i' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300']"
        >
          <i class="ra ra-camera"></i>
          <span class="font-bold text-md font-mono uppercase tracking-widest">Visuals</span>
        </button>
        <button
          @click="activeSection = 'styles'"
          :class="['w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300', activeSection === 'styles' ? 'bg-amber-500/10 text-amber-300 border border-amber-500/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300']"
        >
          <i class="ra ra-paint-brush"></i>
          <span class="font-bold text-md font-mono uppercase tracking-widest">Image Styles</span>
        </button>
        <button 
          @click="activeSection = 'tones'"
          :class="['w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300', activeSection === 'tones' ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300']"
        >
          <i class="ra ra-scroll"></i>
          <span class="font-bold text-md font-mono uppercase tracking-widest">Narrative Tones</span>
        </button>

        <button 
          @click="activeSection = 'game'"
          :class="['w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300', activeSection === 'game' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300']"
        >
          <i class="ra ra-gear"></i>
          <span class="font-bold text-md font-mono uppercase tracking-widest">Game Settings</span>
        </button>

        <button 
          @click="activeSection = 'users'"
          :class="['w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300', activeSection === 'users' ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300']"
        >
          <i class="ra ra-person"></i>
          <span class="font-bold text-md font-mono uppercase tracking-widest">User Management</span>
        </button>
      </nav>

      <div class="mt-auto pt-6 border-t border-slate-800 opacity-50">
        <div class="text-xs font-bold text-slate-500 uppercase tracking-widest">TaleWeaver Engine v{{ configState.appVersion }}</div>
      </div>
    </aside>

    <!-- CONTENT AREA -->
    <main class="flex-grow p-12 overflow-y-auto max-h-screen custom-scrollbar relative">
      <div class="max-w-4xl mx-auto">
        
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
                  <option value="google">Google Gemini</option>
                  <option value="openrouter">OpenRouter</option>
                  <option value="black_forest_labs">Black Forest Labs</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="ollama">Ollama (Local)</option>
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
            <button @click="saveApiKey" :disabled="isSubmitting || (keyForm.provider !== 'ollama' && !keyForm.api_key) || configuredKeys[keyForm.provider]?.is_env" class="w-full py-4 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition-all shadow-lg disabled:opacity-50">
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
                 <span :class="[info.is_env ? 'text-amber-500 bg-amber-500/10' : 'text-emerald-500 bg-emerald-500/10', 'text-xxs font-mono font-black tracking-widest px-2 py-1 rounded']">
                   {{ info.is_env ? 'READ-ONLY' : 'SECURED' }}
                 </span>
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

          <div class="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-8">
            
            <!-- SIMPLE MODEL -->
            <div class="space-y-4 p-6 bg-slate-950/50 rounded-2xl border border-purple-500/10">
              <div class="flex items-center justify-between mb-2">
                <h3 class="text-lg font-bold text-purple-400 flex items-center gap-2">
                  <i class="ra ra-gear-hammer"></i> Simple Model (Mechanics)
                </h3>
                <button 
                  @click="testLlm('simple', llmForm.small_model, llmForm.small_model_provider)"
                  class="px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/40 text-purple-300 text-xs font-bold rounded-lg border border-purple-600/30 transition-all flex items-center gap-2"
                >
                  <i class="ra ra-gear-hammer"></i> Test Connection
                </button>
              </div>
              
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="space-y-2">
                  <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Provider</label>
                  <select v-model="llmForm.small_model_provider" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50">
                    <option v-for="p in availableConstants.llm_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
                  </select>
                </div>
                <div class="space-y-2">
                  <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Model Selection</label>
                  <select 
                    :value="isModelCustom(llmForm.small_model, llmForm.small_model_provider, 'llm') ? 'custom' : llmForm.small_model"
                    @change="(e) => { 
                      const val = (e.target as HTMLSelectElement).value; 
                      if(val !== 'custom') llmForm.small_model = val;
                      else if(!isModelCustom(llmForm.small_model, llmForm.small_model_provider, 'llm')) llmForm.small_model = '';
                    }"
                    class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50 font-mono"
                  >
                    <option value="" disabled>-- Please Select --</option>
                    <option v-for="m in availableConstants.predefined_llm_models[llmForm.small_model_provider]" :key="m" :value="m">{{ m }}</option>
                    <option value="custom">-- Custom Model String --</option>
                  </select>
                </div>
              </div>

              <div v-if="isModelCustom(llmForm.small_model, llmForm.small_model_provider, 'llm') || llmForm.small_model === ''" class="space-y-2 animate-fade-in">
                <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Custom Model ID</label>
                <input v-model="llmForm.small_model" type="text" maxlength="100" placeholder="e.g. gpt-4o-mini" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50 font-mono" />
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

              <!-- PER-MODEL SETTINGS -->
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-slate-900">
                <div class="space-y-2">
                  <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Max Tokens</label>
                  <input v-model.number="llmForm.small_max_tokens" type="number" step="1024" min="128" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50" />
                </div>
                <div class="space-y-2">
                  <div class="flex items-center justify-between mb-2">
                    <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Thinking Mode</label>
                    <label class="relative inline-flex items-center cursor-pointer scale-75 origin-right">
                      <input type="checkbox" v-model="llmForm.small_enable_thinking" class="sr-only peer">
                      <div class="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600 peer-checked:after:bg-white"></div>
                    </label>
                  </div>
                  <input v-if="llmForm.small_enable_thinking" v-model.number="llmForm.small_max_thinking_tokens" type="number" step="1024" min="0" placeholder="Thinking tokens" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50" />
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
                  @click="testLlm('complex', llmForm.complex_model, llmForm.complex_model_provider)"
                  class="px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/40 text-purple-300 text-xs font-bold rounded-lg border border-purple-600/30 transition-all flex items-center gap-2"
                >
                  <i class="ra ra-gear-hammer"></i> Test Connection
                </button>
              </div>
              
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="space-y-2">
                  <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Provider</label>
                  <select v-model="llmForm.complex_model_provider" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50">
                    <option v-for="p in availableConstants.llm_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
                  </select>
                </div>
                <div class="space-y-2">
                  <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Model Selection</label>
                  <select 
                    :value="isModelCustom(llmForm.complex_model, llmForm.complex_model_provider, 'llm') ? 'custom' : llmForm.complex_model"
                    @change="(e) => { 
                      const val = (e.target as HTMLSelectElement).value; 
                      if(val !== 'custom') llmForm.complex_model = val;
                      else if(!isModelCustom(llmForm.complex_model, llmForm.complex_model_provider, 'llm')) llmForm.complex_model = '';
                    }"
                    class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50 font-mono"
                  >
                    <option value="" disabled>-- Please Select --</option>
                    <option v-for="m in availableConstants.predefined_llm_models[llmForm.complex_model_provider]" :key="m" :value="m">{{ m }}</option>
                    <option value="custom">-- Custom Model String --</option>
                  </select>
                </div>
              </div>

              <div v-if="isModelCustom(llmForm.complex_model, llmForm.complex_model_provider, 'llm') || llmForm.complex_model === ''" class="space-y-2 animate-fade-in">
                <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Custom Model ID</label>
                <input v-model="llmForm.complex_model" type="text" maxlength="100" placeholder="e.g. gpt-4o" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50 font-mono" />
              </div>
              <p class="text-xxs text-slate-500">Rich storytelling, complex world-building, and high-fidelity prose (Pass 2).</p>

              <!-- Test Result Feedback -->
              <div v-if="testResults.complex" :class="['p-4 rounded-xl text-sm font-medium border animate-fade-in', testResults.complex.status === 'loading' ? 'bg-slate-800 border-slate-700 text-slate-300' : testResults.complex.status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400']">
                 <div class="flex items-center justify-between gap-2">
                    <div class="flex items-center gap-2">
                      <div v-if="testResults.complex.status === 'loading'" class="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div>
                      <i v-else :class="testResults.complex.status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
                      {{ testResults.complex.message }}
                    </div>
                 </div>
              </div>

              <!-- PER-MODEL SETTINGS -->
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-slate-900">
                <div class="space-y-2">
                  <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Max Tokens</label>
                  <input v-model.number="llmForm.complex_max_tokens" type="number" step="1024" min="128" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50" />
                </div>
                <div class="space-y-2">
                  <div class="flex items-center justify-between mb-2">
                    <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Thinking Mode</label>
                    <label class="relative inline-flex items-center cursor-pointer scale-75 origin-right">
                      <input type="checkbox" v-model="llmForm.complex_enable_thinking" class="sr-only peer">
                      <div class="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600 peer-checked:after:bg-white"></div>
                    </label>
                  </div>
                  <input v-if="llmForm.complex_enable_thinking" v-model.number="llmForm.complex_max_thinking_tokens" type="number" step="1024" min="0" placeholder="Thinking tokens" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50" />
                </div>
              </div>
            </div>

            <!-- GLOBAL LLM SETTINGS -->
            <div class="pt-6 border-t border-slate-800 space-y-6">
              <h4 class="text-xs font-black uppercase tracking-[0.2em] text-purple-400">Global Infrastructure</h4>
              
              <div class="space-y-4">
                <div v-if="llmForm.small_model_provider === 'ollama' || llmForm.complex_model_provider === 'ollama'" class="space-y-2 p-4 bg-purple-500/5 rounded-xl border border-purple-500/20">
                  <label class="block text-sm font-semibold text-slate-300">Ollama API Base URL</label>
                  <input v-model="llmForm.ollama_url" type="text" placeholder="http://localhost:11434" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-purple-500/50 font-mono" />
                  <p class="text-xxs text-slate-500">Local endpoint used for local model execution.</p>
                </div>
              </div>
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

          <div class="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-8">
            
            <!-- SIMPLE VISUALS -->
            <div class="space-y-4 p-6 bg-slate-950/50 rounded-2xl border border-cyan-500/10">
              <div class="flex items-center justify-between mb-2">
                <h3 class="text-lg font-bold text-cyan-400 flex items-center gap-2">
                  <i class="ra ra-camera"></i> Simple Visuals (NPCs & Items)
                </h3>
                <button 
                  @click="testVision('simple_v', t2iForm.simple_model, t2iForm.simple_model_provider)"
                  class="px-3 py-1.5 bg-cyan-600/20 hover:bg-cyan-600/40 text-cyan-300 text-xs font-bold rounded-lg border border-cyan-600/30 transition-all flex items-center gap-2"
                >
                  <i class="ra ra-eye-shield"></i> Test Connection
                </button>
              </div>
              
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="space-y-2">
                  <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Provider</label>
                  <select v-model="t2iForm.simple_model_provider" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50">
                    <option v-for="p in availableConstants.image_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
                  </select>
                </div>
                <div class="space-y-2">
                  <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Model Selection</label>
                  <select 
                    :value="isModelCustom(t2iForm.simple_model, t2iForm.simple_model_provider, 'image') ? 'custom' : t2iForm.simple_model"
                    @change="(e) => { 
                      const val = (e.target as HTMLSelectElement).value; 
                      if(val !== 'custom') t2iForm.simple_model = val;
                      else if(!isModelCustom(t2iForm.simple_model, t2iForm.simple_model_provider, 'image')) t2iForm.simple_model = '';
                    }"
                    class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono"
                  >
                    <option value="" disabled>-- Please Select --</option>
                    <option v-for="m in availableConstants.predefined_image_models[t2iForm.simple_model_provider]" :key="m" :value="m">{{ m }}</option>
                    <option value="custom">-- Custom Model String --</option>
                  </select>
                </div>
              </div>

              <div v-if="isModelCustom(t2iForm.simple_model, t2iForm.simple_model_provider, 'image') || t2iForm.simple_model === ''" class="space-y-2 animate-fade-in">
                <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Custom Model ID</label>
                <input v-model="t2iForm.simple_model" type="text" maxlength="100" placeholder="e.g. dall-e-2" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono" />
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
                  @click="testVision('advanced_v', t2iForm.advanced_model, t2iForm.advanced_model_provider)"
                  class="px-3 py-1.5 bg-cyan-600/20 hover:bg-cyan-600/40 text-cyan-300 text-xs font-bold rounded-lg border border-cyan-600/30 transition-all flex items-center gap-2"
                >
                  <i class="ra ra-eye-shield"></i> Test Connection
                </button>
              </div>
              
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="space-y-2">
                  <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Provider</label>
                  <select v-model="t2iForm.advanced_model_provider" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50">
                    <option v-for="p in availableConstants.image_providers" :key="p.id" :value="p.id">{{ p.name }}</option>
                  </select>
                </div>
                <div class="space-y-2">
                  <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Model Selection</label>
                  <select 
                    :value="isModelCustom(t2iForm.advanced_model, t2iForm.advanced_model_provider, 'image') ? 'custom' : t2iForm.advanced_model"
                    @change="(e) => { 
                      const val = (e.target as HTMLSelectElement).value; 
                      if(val !== 'custom') t2iForm.advanced_model = val;
                      else if(!isModelCustom(t2iForm.advanced_model, t2iForm.advanced_model_provider, 'image')) t2iForm.advanced_model = '';
                    }"
                    class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono"
                  >
                    <option value="" disabled>-- Please Select --</option>
                    <option v-for="m in availableConstants.predefined_image_models[t2iForm.advanced_model_provider]" :key="m" :value="m">{{ m }}</option>
                    <option value="custom">-- Custom Model String --</option>
                  </select>
                </div>
              </div>

              <div v-if="isModelCustom(t2iForm.advanced_model, t2iForm.advanced_model_provider, 'image') || t2iForm.advanced_model === ''" class="space-y-2 animate-fade-in">
                <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Custom Model ID</label>
                <input v-model="t2iForm.advanced_model" type="text" maxlength="100" placeholder="e.g. dall-e-3" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono" />
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
                <div v-if="t2iForm.simple_model_provider === 'ollama' || t2iForm.advanced_model_provider === 'ollama'" class="space-y-2 p-4 bg-cyan-500/5 rounded-xl border border-cyan-500/20">
                  <label class="block text-sm font-semibold text-slate-300">Ollama API Base URL</label>
                  <input v-model="t2iForm.ollama_url" type="text" placeholder="http://localhost:11434" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono" />
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div class="space-y-2">
                    <label class="block text-sm font-semibold text-slate-300">File Format</label>
                    <select v-model="t2iForm.image_format" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-cyan-500/50 outline-none">
                      <option value="jpeg">JPEG (Recommended)</option>
                      <option value="png">PNG (Lossless)</option>
                    </select>
                    <p class="text-xxs text-slate-500">JPEG significantly reduces file size for assets.</p>
                  </div>
                  
                  <div v-if="t2iForm.image_format === 'jpeg'" class="space-y-2">
                    <div class="flex justify-between items-center mb-1">
                      <label class="block text-sm font-semibold text-slate-300">JPEG Quality</label>
                      <span class="text-xs font-mono font-bold text-cyan-400 bg-cyan-400/10 px-2 py-0.5 rounded">{{ t2iForm.image_quality }}%</span>
                    </div>
                    <input v-model.number="t2iForm.image_quality" type="range" min="10" max="100" step="5" class="w-full h-2 bg-slate-950 border border-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-500" />
                  </div>
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
                </div>
              </div>
            </div>

            <button @click="saveT2iSettings" :disabled="isSubmitting" class="w-full py-4 bg-cyan-600 hover:bg-cyan-500 text-white font-bold rounded-xl transition-all shadow-lg disabled:opacity-50">
               {{ isSubmitting ? 'Painting...' : 'Update Visual Artists' }}
            </button>
          </div>
        </div>

        <!-- SECTION: IMAGE STYLES -->
        <div v-if="activeSection === 'styles'" class="space-y-8 animate-fade-in">
          <div class="flex items-center justify-between">
            <div>
              <h1 class="text-4xl font-extrabold text-white mb-2">Image Style Catalog</h1>
              <p class="text-slate-400 text-sm">Define selectable visual styles used during adventure image generation.</p>
            </div>
            <button @click="openCatalogModal('styles')" class="px-6 py-3 bg-amber-600 hover:bg-amber-500 text-white font-bold rounded-xl shadow-lg shadow-amber-900/20 flex items-center gap-2 transition-all">
              <i class="ra ra-plus"></i> Add Style
            </button>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div v-for="(style, index) in imageStylesCatalog" :key="style.id + '-' + index" class="group relative bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden hover:border-amber-500/50 transition-all shadow-xl">
              <!-- Image Section -->
              <div class="relative aspect-[4/3] bg-slate-950 overflow-hidden">
                <img v-if="style.image_url" :src="style.image_url.startsWith('http') ? style.image_url : style.image_url" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                <div v-else class="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-slate-900 to-slate-950 text-slate-700">
                  <svg class="w-16 h-16 opacity-30 mb-2 animate-pulse-slow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z" />
                    <path d="M12 8v4l3 3" />
                    <path d="M9 3v2" /><path d="M5 5L6.5 6.5" /><path d="M3 9h2" /><path d="M3 15h2" /><path d="M5 19l1.5-1.5" /><path d="M9 21v-2" /><path d="M15 21v-2" /><path d="M19 19l-1.5-1.5" /><path d="M21 15h-2" /><path d="M21 9h-2" /><path d="M19 5L17.5 6.5" /><path d="M15 3v2" />
                  </svg>
                  <span class="text-xxs uppercase tracking-widest font-bold opacity-30">No Style Image</span>
                </div>
                
                <!-- Overlay Buttons -->
                <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <button @click="generateCatalogImage('styles', style, index)" :disabled="isGeneratingItem['styles_' + index]" class="p-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg shadow-lg disabled:opacity-50" :title="'Quick Generate using ' + t2iForm.simple_model">
                    <i v-if="isGeneratingItem['styles_' + index]" class="ra ra-cycle animate-spin"></i>
                    <i v-else class="ra ra-cycle"></i>
                  </button>
                  <button @click="openPromptModal('styles', style, index)" class="p-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg shadow-lg">
                    <i class="ra ra-quill-ink" title="Custom Prompt"></i>
                  </button>
                  <input :id="'style-upload-' + index" type="file" class="hidden" accept="image/*" @change="(e) => onUploadFile(e, 'styles', style, index)" />


                </div>

                <!-- Loading Overlay -->
                <div v-if="isGeneratingItem['styles_' + index]" class="absolute inset-0 bg-black/60 flex items-center justify-center">
                  <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-emerald-500"></div>
                </div>
              </div>

              <!-- Content Section -->
              <div class="p-4">
                <div class="flex items-start justify-between gap-2">
                  <div class="min-w-0">
                    <h3 class="text-white font-bold truncate">{{ style.name }}</h3>
                    <p class="text-slate-500 text-xxs uppercase font-mono truncate">{{ style.id }}</p>
                  </div>
                  <div class="relative">
                    <button @click.stop="openMenuId = openMenuId === 'style-' + index ? null : 'style-' + index" class="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors text-lg font-bold leading-none flex items-center justify-center min-w-[32px] h-8" title="Options">
                      <span class="mb-0.5">...</span>
                    </button>
                    <div v-if="openMenuId === 'style-' + index" class="fixed inset-0 z-[90]" @click="openMenuId = null"></div>
                    <div v-if="openMenuId === 'style-' + index" class="absolute right-0 bottom-full mb-1 w-32 bg-slate-800 border border-slate-700 rounded-xl shadow-[0_0_50px_rgba(0,0,0,0.5)] z-[100] py-1 overflow-hidden">
                      <button @click="openCatalogModal('styles', style, index); openMenuId = null" class="w-full text-left px-4 py-2 text-xs font-bold text-slate-300 hover:bg-slate-700 hover:text-white">
                        Rename
                      </button>
                      <button @click="openCatalogModal('styles', style, index); openMenuId = null" class="w-full text-left px-4 py-2 text-xs font-bold text-slate-300 hover:bg-slate-700 hover:text-white">
                        Edit
                      </button>
                      <button @click="openPromptModal('styles', style, index); openMenuId = null" class="w-full text-left px-4 py-2 text-xs font-bold text-slate-300 hover:bg-slate-700 hover:text-white">
                        Custom Prompt
                      </button>
                      <button @click="triggerFileUpload('style-upload-' + index); openMenuId = null" class="w-full text-left px-4 py-2 text-xs font-bold text-slate-300 hover:bg-slate-700 hover:text-white">
                        Upload Image
                      </button>
                      <div class="h-px bg-slate-700 my-1"></div>
                      <button @click="removeCatalogItem('styles', index); openMenuId = null" class="w-full text-left px-4 py-2 text-xs font-bold text-red-400 hover:bg-red-500/20">
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
                <p class="text-slate-400 text-xs mt-2 line-clamp-2 min-h-[2.5em]">{{ style.description || 'No description provided.' }}</p>
              </div>
            </div>
            
            <div v-if="imageStylesCatalog.length === 0" class="col-span-full py-20 text-center border-2 border-dashed border-slate-800 rounded-3xl text-slate-600 italic">
              No styles in catalog yet. Click "Add Style" to begin.
            </div>
          </div>
        </div>

        <!-- SECTION: TONES -->
        <div v-if="activeSection === 'tones'" class="space-y-8 animate-fade-in">
          <div class="flex items-center justify-between">
            <div>
              <h1 class="text-4xl font-extrabold text-white mb-2">World Tone Catalog</h1>
              <p class="text-slate-400 text-sm">Define selectable tone presets used for story/world generation.</p>
            </div>
            <button @click="openCatalogModal('tones')" class="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl shadow-lg shadow-indigo-900/20 flex items-center gap-2 transition-all">
              <i class="ra ra-plus"></i> Add Tone
            </button>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div v-for="(tone, index) in toneCatalog" :key="tone.id + '-' + index" class="group relative bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden hover:border-indigo-500/50 transition-all shadow-xl">
              <!-- Image Section -->
              <div class="relative aspect-[4/3] bg-slate-950 overflow-hidden">
                <img v-if="tone.image_url" :src="tone.image_url.startsWith('http') ? tone.image_url : tone.image_url" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                <div v-else class="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-slate-900 to-slate-950 text-slate-700">
                  <svg class="w-16 h-16 opacity-30 mb-2 animate-pulse-slow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                  <span class="text-xxs uppercase tracking-widest font-bold opacity-30">No Tone Image</span>
                </div>
                
                <!-- Overlay Buttons -->
                <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <button @click="generateCatalogImage('tones', tone, index)" :disabled="isGeneratingItem['tones_' + index]" class="p-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg shadow-lg disabled:opacity-50" :title="'Quick Generate using ' + t2iForm.simple_model">
                    <i v-if="isGeneratingItem['tones_' + index]" class="ra ra-cycle animate-spin"></i>
                    <i v-else class="ra ra-cycle"></i>
                  </button>
                  <button @click="openPromptModal('tones', tone, index)" class="p-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg shadow-lg">
                    <i class="ra ra-quill-ink" title="Custom Prompt"></i>
                  </button>
                  <input :id="'tone-upload-' + index" type="file" class="hidden" accept="image/*" @change="(e) => onUploadFile(e, 'tones', tone, index)" />


                </div>

                <!-- Loading Overlay -->
                <div v-if="isGeneratingItem['tones_' + index]" class="absolute inset-0 bg-black/60 flex items-center justify-center">
                  <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-emerald-500"></div>
                </div>
              </div>

              <!-- Content Section -->
              <div class="p-4">
                <div class="flex items-start justify-between gap-2">
                  <div class="min-w-0">
                    <h3 class="text-white font-bold truncate">{{ tone.name }}</h3>
                    <p class="text-slate-500 text-xxs uppercase font-mono truncate">{{ tone.id }}</p>
                  </div>
                  <div class="relative">
                    <button @click.stop="openMenuId = openMenuId === 'tone-' + index ? null : 'tone-' + index" class="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors text-lg font-bold leading-none flex items-center justify-center min-w-[32px] h-8" title="Options">
                      <span class="mb-0.5">...</span>
                    </button>
                    <div v-if="openMenuId === 'tone-' + index" class="fixed inset-0 z-[90]" @click="openMenuId = null"></div>
                    <div v-if="openMenuId === 'tone-' + index" class="absolute right-0 bottom-full mb-1 w-32 bg-slate-800 border border-slate-700 rounded-xl shadow-[0_0_50px_rgba(0,0,0,0.5)] z-[100] py-1 overflow-hidden">
                      <button @click="openCatalogModal('tones', tone, index); openMenuId = null" class="w-full text-left px-4 py-2 text-xs font-bold text-slate-300 hover:bg-slate-700 hover:text-white">
                        Rename
                      </button>
                      <button @click="openCatalogModal('tones', tone, index); openMenuId = null" class="w-full text-left px-4 py-2 text-xs font-bold text-slate-300 hover:bg-slate-700 hover:text-white">
                        Edit
                      </button>
                      <button @click="openPromptModal('tones', tone, index); openMenuId = null" class="w-full text-left px-4 py-2 text-xs font-bold text-slate-300 hover:bg-slate-700 hover:text-white">
                        Custom Prompt
                      </button>
                      <button @click="triggerFileUpload('tone-upload-' + index); openMenuId = null" class="w-full text-left px-4 py-2 text-xs font-bold text-slate-300 hover:bg-slate-700 hover:text-white">
                        Upload Image
                      </button>
                      <div class="h-px bg-slate-700 my-1"></div>
                      <button @click="removeCatalogItem('tones', index); openMenuId = null" class="w-full text-left px-4 py-2 text-xs font-bold text-red-400 hover:bg-red-500/20">
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
                <p class="text-slate-400 text-xs mt-2 line-clamp-2 min-h-[2.5em]">{{ tone.description || 'No description provided.' }}</p>
              </div>
            </div>

            <div v-if="toneCatalog.length === 0" class="col-span-full py-20 text-center border-2 border-dashed border-slate-800 rounded-3xl text-slate-600 italic">
              No tones in catalog yet. Click "Add Tone" to begin.
            </div>
          </div>
        </div>

        <!-- SECTION: GAME SETTINGS -->
        <div v-if="activeSection === 'game'" class="space-y-8 animate-fade-in">
          <div>
            <h1 class="text-4xl font-extrabold text-white mb-2">Game Preferences</h1>
            <p class="text-slate-400">Configure global interface and gameplay options.</p>
          </div>

          <div class="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
            <div class="p-6 bg-slate-950/40 border border-slate-800/40 rounded-2xl space-y-6">
              <!-- Clock Settings -->
              <div class="flex items-center justify-between p-4 bg-slate-900/60 rounded-xl border border-white/5">
                <div>
                  <div class="text-sm font-bold text-white">24-Hour Format</div>
                  <div class="text-xs text-slate-500">Enable to use 24h clock, otherwise 12h (AM/PM) is used.</div>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" v-model="gameForm.clock_24h" class="sr-only peer">
                  <div class="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
                </label>
              </div>

              <!-- Date Format Settings -->
              <div class="flex items-center justify-between p-4 bg-slate-900/60 rounded-xl border border-white/5">
                <div>
                  <div class="text-sm font-bold text-white">Date Format</div>
                  <div class="text-xs text-slate-500">Choose how the in-game date is presented.</div>
                </div>
                <select 
                  v-model="gameForm.date_format"
                  class="bg-slate-950 border border-slate-800 text-white text-xs rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block p-2 px-4"
                >
                  <option value="DD.MM.YY">DD.MM.YY (e.g. 24.12.26)</option>
                  <option value="MM/DD/YY">MM/DD/YY (e.g. 12/24/26)</option>
                  <option value="YY-MM-DD">YY-MM-DD (e.g. 26-12-24)</option>
                </select>
              </div>
            </div>

            <button @click="saveGameSettings" :disabled="isSubmitting" class="w-full py-4 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl disabled:opacity-50 shadow-lg shadow-blue-500/20">
              {{ isSubmitting ? 'Saving...' : 'Apply Game Settings' }}
            </button>
          </div>
        </div>

        <!-- SECTION: USERS -->
        <div v-if="activeSection === 'users'" class="space-y-8 animate-fade-in">
          <div class="flex items-center justify-between">
            <div>
              <h1 class="text-4xl font-extrabold text-white mb-2">User Management</h1>
              <p class="text-slate-400 text-sm">Create and manage accounts for your TaleWeaver domain.</p>
            </div>
            <button @click="openUserModal()" class="px-6 py-3 bg-red-600 hover:bg-red-500 text-white font-bold rounded-xl shadow-lg shadow-red-900/20 flex items-center gap-2 transition-all">
              <i class="ra ra-plus"></i> Add User
            </button>
          </div>

          <div class="bg-slate-900 border border-slate-800 rounded-3xl overflow-hidden shadow-2xl">
            <table class="w-full text-left">
              <thead>
                <tr class="border-b border-slate-800 bg-slate-950/50">
                  <th class="px-6 py-4 text-xxs font-black text-slate-500 uppercase tracking-widest">User</th>
                  <th class="px-6 py-4 text-xxs font-black text-slate-500 uppercase tracking-widest">Role</th>
                  <th class="px-6 py-4 text-xxs font-black text-slate-500 uppercase tracking-widest text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800">
                <tr v-for="user in usersList" :key="user.id" class="hover:bg-white/[0.02] transition-colors group">
                  <td class="px-6 py-4">
                    <div class="flex items-center gap-3">
                      <div class="w-8 h-8 rounded-full bg-white/5 border border-white/10 overflow-hidden">
                        <img v-if="user.profile_image_url" :src="user.profile_image_url" class="w-full h-full object-cover" />
                        <div v-else class="w-full h-full flex items-center justify-center text-slate-600">
                          <i class="ra ra-hood"></i>
                        </div>
                      </div>
                      <span class="font-bold text-white">{{ user.username }}</span>
                    </div>
                  </td>
                  <td class="px-6 py-4">
                    <span :class="['px-2 py-0.5 rounded text-xxs font-black uppercase tracking-tighter', user.role === 'admin' ? 'bg-red-500/10 text-red-400' : 'bg-blue-500/10 text-blue-400']">
                      {{ user.role }}
                    </span>
                  </td>
                  <td class="px-6 py-4 text-right">
                    <div class="flex items-center justify-end gap-2">
                      <button @click="openUserModal(user)" class="p-2 text-slate-500 hover:text-white transition-colors" title="Edit">
                        <i class="ra ra-quill-ink"></i>
                      </button>
                      <button @click="removeUser(user)" class="p-2 text-slate-500 hover:text-red-400 transition-colors" title="Delete">
                        <i class="ra ra-cancel"></i>
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>

    <!-- STATUS MESSAGE FLOATER -->
    <div v-if="statusMessage" 
      :class="['fixed bottom-12 right-12 px-6 py-4 rounded-2xl shadow-2xl text-sm font-bold border max-w-sm animate-slide-in z-[100]', 
      statusMessage.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20']"
    >
      <div class="flex items-center gap-3">
        <i :class="statusMessage.type === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
        {{ statusMessage.text }}
      </div>
    </div>

    <!-- USER MODAL -->
    <Teleport to="body">
      <div v-if="isUserModalOpen" class="fixed inset-0 z-[110] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/90 backdrop-blur-md" @click="isUserModalOpen = false"></div>
        <div class="relative w-full max-w-lg bg-[#0a111c] border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden animate-fade-in">
          <div class="p-10">
            <h2 class="text-2xl font-black text-white font-display mb-8">
              {{ isEditingExistingUser ? 'Edit Domain Dweller' : 'Summon New Dweller' }}
            </h2>

            <form @submit.prevent="saveUser" class="space-y-6">
              <div class="space-y-2">
                <label class="text-xxs font-black text-slate-500 uppercase tracking-widest">Username</label>
                <input v-model="editingUser.username" type="text" required class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white outline-none focus:border-red-500/50" />
              </div>

              <div class="space-y-2">
                <label class="text-xxs font-black text-slate-500 uppercase tracking-widest">
                  {{ isEditingExistingUser ? 'Reset Password (optional)' : 'Master Password' }}
                </label>
                <input v-model="editingUser.password" type="password" :required="!isEditingExistingUser" class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white outline-none focus:border-red-500/50" />
              </div>

              <div class="space-y-2">
                <label class="text-xxs font-black text-slate-500 uppercase tracking-widest">Role</label>
                <select v-model="editingUser.role" class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white outline-none focus:border-red-500/50">
                  <option value="user">User (Storyteller)</option>
                  <option value="admin">Admin (World Weaver)</option>
                </select>
              </div>

              <div class="flex gap-4 pt-4">
                <button type="button" @click="isUserModalOpen = false" class="flex-1 py-3 text-slate-500 font-bold hover:text-white transition-colors">Cancel</button>
                <button type="submit" :disabled="isSubmitting" class="flex-[2] btn-primary !bg-red-600 hover:!bg-red-500 shadow-red-900/20">
                  {{ isSubmitting ? 'Weaving...' : 'Save Soul' }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- CATALOG ADD/EDIT MODAL -->
    <Teleport to="body">
      <div v-if="isCatalogModalOpen" class="fixed inset-0 z-[80] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="isCatalogModalOpen = false"></div>
        <div class="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl p-8 animate-fade-in">
          <div class="flex items-center justify-between mb-6">
            <h2 class="text-2xl font-bold text-white flex items-center gap-3 capitalize">
              <i :class="catalogModalType === 'styles' ? 'ra ra-paint-brush text-amber-500' : 'ra ra-scroll text-indigo-500'"></i>
              {{ isEditingExisting ? 'Edit' : 'Add' }} {{ catalogModalType.replace('s', '') }}
            </h2>
            <button @click="isCatalogModalOpen = false" class="text-slate-500 hover:text-white transition-colors">
              <i class="ra ra-cancel"></i>
            </button>
          </div>

          <!-- Image Preview & Actions in Modal -->
          <div class="mb-8 flex items-center gap-6 bg-slate-950/50 p-4 rounded-2xl border border-slate-800">
            <div class="w-24 h-24 rounded-xl overflow-hidden bg-slate-900 border border-slate-800 flex-shrink-0 relative group">
              <img v-if="editingItem.image_url" :src="editingItem.image_url.startsWith('http') ? editingItem.image_url : editingItem.image_url" class="w-full h-full object-cover" />
              <div v-else class="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-900 to-slate-950 text-slate-800">
                <svg v-if="catalogModalType === 'styles'" class="w-10 h-10 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z" /><path d="M12 8v4l3 3" /><path d="M9 3v2" /><path d="M5 5L6.5 6.5" /><path d="M3 9h2" /><path d="M3 15h2" /><path d="M5 19l1.5-1.5" /><path d="M9 21v-2" /><path d="M15 21v-2" /><path d="M19 19l-1.5-1.5" /><path d="M21 15h-2" /><path d="M21 9h-2" /><path d="M19 5L17.5 6.5" /><path d="M15 3v2" /></svg>
                <svg v-else class="w-10 h-10 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
              </div>
              <div v-if="isGeneratingItem.modal_generating" class="absolute inset-0 bg-black/60 flex items-center justify-center">
                <div class="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-emerald-500"></div>
              </div>
            </div>
            <div class="flex flex-col gap-2 flex-grow">
              <button 
                @click="generateCatalogImage(catalogModalType, editingItem, isEditingExisting ? editingIndex : null)" 
                :disabled="!editingItem.name || isGeneratingItem.modal_generating"
                class="flex items-center justify-center gap-2 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg transition-all disabled:opacity-50"
              >
                <i class="ra ra-cycle" :class="{'animate-spin': isGeneratingItem.modal_generating}"></i>
                AI Generate Image
              </button>
              <button 
                @click="triggerFileUpload('modal-upload')"
                class="flex items-center justify-center gap-2 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded-lg transition-all"
              >
                <i class="ra ra-camera"></i>
                Upload Manually
              </button>
              <input id="modal-upload" type="file" class="hidden" accept="image/*" @change="(e) => onUploadFile(e, catalogModalType, editingItem, isEditingExisting ? editingIndex : null)" />
            </div>
          </div>

          <div class="space-y-6">
            <div>
              <div class="flex justify-between items-center mb-2">
                <label class="block text-xs font-bold text-slate-500 uppercase tracking-widest">Display Name</label>
                <span class="text-xxs font-mono text-slate-600">{{ (editingItem.name || '').length }} / 30</span>
              </div>
              <input v-model="editingItem.name" type="text" maxlength="30" placeholder="e.g. Dark Fantasy" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none" />
            </div>
            <div>
              <div class="flex justify-between items-center mb-2">
                <label class="block text-xs font-bold text-slate-500 uppercase tracking-widest">Description</label>
                <span class="text-xxs font-mono text-slate-600">{{ (editingItem.description || '').length }} / 200</span>
              </div>
              <textarea v-model="editingItem.description" rows="2" maxlength="200" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none resize-y"></textarea>
            </div>
            <div>
              <div class="flex justify-between items-center mb-2">
                <label class="block text-xs font-bold text-slate-500 uppercase tracking-widest">System Instruction / Prompt Prefix</label>
                <span class="text-xxs font-mono text-slate-600">{{ (editingItem.instruction || '').length }} / 500</span>
              </div>
              <textarea v-model="editingItem.instruction" rows="3" maxlength="500" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none resize-y font-mono text-xs"></textarea>
            </div>
            
            <button @click="saveCatalogItem" class="w-full py-4 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition-all shadow-lg">
              Save Entry
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- CUSTOM PROMPT MODAL -->
    <Teleport to="body">
      <div v-if="isPromptModalOpen" class="fixed inset-0 z-[90] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="isPromptModalOpen = false"></div>
        <div class="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl p-8 animate-fade-in">
          <h2 class="text-xl font-bold text-white mb-6 flex items-center gap-3">
            <i class="ra ra-quill-ink text-blue-500"></i>
            Custom Image Generation
          </h2>
          <p class="text-slate-400 text-sm mb-4">Provide a specific prompt for the profile image of <strong>{{ promptModalData?.item.name }}</strong>.</p>
          <textarea v-model="customPrompt" rows="4" placeholder="A dark moody oil painting of..." class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-blue-500/50 outline-none resize-none mb-6"></textarea>
          <div class="flex gap-4">
            <button @click="isPromptModalOpen = false" class="flex-1 py-3 border border-slate-800 text-slate-400 hover:text-white rounded-xl transition-colors font-bold">Cancel</button>
            <button 
              @click="generateCatalogImage(promptModalData!.type, promptModalData!.item, promptModalData!.index, customPrompt)" 
              :disabled="!customPrompt.trim()"
              class="flex-grow py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl transition-all font-bold shadow-lg shadow-blue-900/20 disabled:opacity-50"
            >
              Generate
            </button>
          </div>
        </div>
      </div>
    </Teleport>
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

