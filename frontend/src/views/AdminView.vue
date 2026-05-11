<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { configState, refreshConfig } from '@/store/config'
import { audioService } from '@/services/audioService'
import type { CatalogTile } from '@/types'

const router = useRouter()

// NAVIGATION
type Section = 'keys' | 'llm' | 't2i' | 'tts' | 'styles' | 'tones' | 'game' | 'users'
const activeSection = ref<Section>('keys')

import { api } from '@/composables/useApi'

type VoiceCatalogEntry = {
  name: string
  gender?: string
  description?: string
}

// FORMS
const keyForm = ref({
  provider: 'openai',
  api_key: ''
})

const llmForm = ref({
  small_model: '',
  small_model_provider: 'openai',
  small_max_tokens: 12288,
  small_enable_thinking: false,
  small_max_thinking_tokens: 1024,
  
  complex_model: '',
  complex_model_provider: 'openai',
  complex_max_tokens: 24576,
  complex_enable_thinking: false,
  complex_max_thinking_tokens: 1024,
  
  generator_model: '',
  generator_model_provider: 'openai',
  generator_max_tokens: 32768,
  generator_enable_thinking: false,
  generator_max_thinking_tokens: 1024,
  
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

const ttsForm = ref({
  enabled: false,
  provider: 'google',
  selected_model: 'gemini-3.1-flash-tts-preview',
  elevenlabs_voice_id: '',
  use_vocal_tags: true,
  use_text_chunking: true,
  voice_catalog: [] as VoiceCatalogEntry[],
  selected_voice: 'Puck',
  sample_context: '',
  speech_rate: 1.0,
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

// COMPONENTS
import ProviderKeysSection from '@/components/admin/ProviderKeysSection.vue'
import IntelligenceSection from '@/components/admin/IntelligenceSection.vue'
import VisualsSection from '@/components/admin/VisualsSection.vue'
import SpeechSection from '@/components/admin/SpeechSection.vue'
import CatalogSection from '@/components/admin/CatalogSection.vue'
import GameSettingsSection from '@/components/admin/GameSettingsSection.vue'
import UserManagementSection from '@/components/admin/UserManagementSection.vue'
import UserEditModal from '@/components/admin/UserEditModal.vue'
import CatalogEditModal from '@/components/admin/CatalogEditModal.vue'
import PromptInputModal from '@/components/admin/PromptInputModal.vue'

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
    if (data.tts_settings) {
      const ttsSettings = data.tts_settings as any
      ttsForm.value = {
        ...ttsForm.value,
        ...ttsSettings,
        use_vocal_tags: ttsSettings.use_vocal_tags !== false,
        use_text_chunking: String(ttsSettings.use_text_chunking).toLowerCase() !== 'false' && ttsSettings.use_text_chunking !== null,
      }
      
      
      audioService.speechRate.value = ttsForm.value.speech_rate ?? 1.0
      console.info('[Admin] Settings hydrated. use_text_chunking:', ttsForm.value.use_text_chunking)
      audioService.useTextChunking.value = ttsForm.value.use_text_chunking
    }
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

const deleteApiKey = async (provider: string) => {
  if (!confirm(`Are you sure you want to remove the API key for ${provider}? This will stop related AI services from functioning.`)) return
  isSubmitting.value = true
  try {
    await api.deleteApiKey(provider)
    statusMessage.value = { type: 'success', text: `${provider} key removed successfully.` }
    fetchSettings()
  } catch (err: any) {
    statusMessage.value = { type: 'error', text: 'Delete failed: ' + err.message }
  } finally {
    isSubmitting.value = false
  }
}

const saveLlmSettings = async (payload: any) => {
  llmForm.value = { ...payload }
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

const saveGameSettings = async (payload: any) => {
  gameForm.value = { ...payload }
  isSubmitting.value = true
  statusMessage.value = null
  try {
    await api.saveGameSettings(gameForm.value)
    statusMessage.value = { type: 'success', text: 'Game preferences updated.' }
    await refreshConfig()
  } catch (error) {
    statusMessage.value = { type: 'error', text: 'Failed to save game preferences.' }
  } finally {
    isSubmitting.value = false
  }
}

const saveT2iSettings = async (payload: any) => {
  t2iForm.value = { ...payload }
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

const saveTTSSettings = async (payload: any) => {
  ttsForm.value = { ...payload }
  isSubmitting.value = true
  statusMessage.value = null
  try {
    console.info('[Admin] Saving TTS Settings:', ttsForm.value)
    await api.saveTTSSettings(ttsForm.value)
    audioService.speechRate.value = ttsForm.value.speech_rate
    audioService.useTextChunking.value = ttsForm.value.use_text_chunking
    statusMessage.value = { type: 'success', text: 'TTS settings updated.' }
    await refreshConfig()
  } catch (error) {
    statusMessage.value = { type: 'error', text: 'Failed to update TTS settings.' }
  } finally {
    isSubmitting.value = false
  }
}

const testTTS = async () => {
  testResults.value['tts'] = { status: 'loading', message: 'Testing Speech...' }
  try {
    const data = await api.testTTS()
    if (data.status === 'success' && data.audio_url) {
      const audio = new Audio(data.audio_url)
      await audio.play()
      testResults.value['tts'] = { status: 'success', message: 'Speech generated!' }
    } else {
      testResults.value['tts'] = { status: 'error', message: data.message || 'No audio generated.' }
    }
  } catch (err: any) {
    testResults.value['tts'] = { status: 'error', message: err.message || 'Test failed.' }
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


onMounted(() => {
  fetchSettings()
  fetchUsers()
})



</script>

<<template>
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
          v-for="section in [
            { id: 'keys', label: 'Provider Keys', icon: 'ra-locked', color: 'emerald' },
            { id: 'llm', label: 'Intelligence', icon: 'ra-brain', color: 'purple' },
            { id: 't2i', label: 'Visuals', icon: 'ra-camera', color: 'cyan' },
            { id: 'tts', label: 'Speech (TTS)', icon: 'ra-microphone', color: 'blue' },
            { id: 'styles', label: 'Image Styles', icon: 'ra-paint-brush', color: 'amber' },
            { id: 'tones', label: 'Narrative Tones', icon: 'ra-scroll', color: 'indigo' },
            { id: 'game', label: 'Game Settings', icon: 'ra-gear', color: 'blue' },
            { id: 'users', label: 'User Management', icon: 'ra-person', color: 'red' }
          ]"
          :key="section.id"
          @click="activeSection = section.id as Section"
          :class="['w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300', activeSection === section.id ? `bg-${section.color}-500/10 text-${section.color}-400 border border-${section.color}-500/20` : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300']"
        >
          <i :class="['ra', section.icon || 'opacity-0']"></i>
          <span class="font-bold text-md font-mono uppercase tracking-widest">{{ section.label }}</span>
        </button>
      </nav>

      <div class="mt-auto pt-6 border-t border-slate-800 opacity-50">
        <div class="text-xs font-bold text-slate-500 uppercase tracking-widest">TaleWeaver Engine v{{ configState.appVersion }}</div>
      </div>
    </aside>

    <!-- CONTENT AREA -->
    <main class="flex-grow p-12 overflow-y-auto max-h-screen custom-scrollbar relative">
      <div class="max-w-4xl mx-auto">
        
        <!-- GLOBAL WARNING -->
        <div v-if="Object.keys(configuredKeys).length === 0 && !isHydratingSettings" class="mb-10 bg-amber-500/10 border border-amber-500/20 rounded-3xl p-8 animate-pulse shadow-2xl">
          <div class="flex items-start gap-6">
            <div class="p-4 bg-amber-500/20 rounded-2xl text-amber-500">
              <i class="ra ra-warning ra-2x"></i>
            </div>
            <div>
              <h3 class="text-xl font-bold text-amber-500 mb-2">AI Configuration Required</h3>
              <p class="text-amber-500/70">TaleWeaver is currently offline. Please configure at least one <strong>Intelligence Provider</strong> (Provider Keys) and select a model to start generating adventures.</p>
            </div>
          </div>
        </div>
        
        <!-- SECTIONS -->
        <ProviderKeysSection 
          v-if="activeSection === 'keys'"
          :configured-keys="configuredKeys"
          :is-submitting="isSubmitting"
          @save="({ provider, api_key }) => { keyForm.provider = provider; keyForm.api_key = api_key; saveApiKey() }"
          @delete="deleteApiKey"
        />

        <IntelligenceSection 
          v-if="activeSection === 'llm'"
          :llm-form="llmForm"
          :available-constants="availableConstants"
          :configured-keys="configuredKeys"
          :is-submitting="isSubmitting"
          :test-results="testResults"
          @save="saveLlmSettings"
          @test="({ key, model, provider }) => testLlm(key, model, provider)"
          @switch-section="(s) => activeSection = s as Section"
        />

        <VisualsSection 
          v-if="activeSection === 't2i'"
          :t2i-form="t2iForm"
          :available-constants="availableConstants"
          :configured-keys="configuredKeys"
          :is-submitting="isSubmitting"
          :test-results="testResults"
          @save="saveT2iSettings"
          @test="({ key, model, provider }) => testVision(key, model, provider)"
          @switch-section="(s) => activeSection = s as Section"
        />

        <SpeechSection 
          v-if="activeSection === 'tts'"
          :tts-form="ttsForm"
          :configured-keys="configuredKeys"
          :is-submitting="isSubmitting"
          :test-results="testResults"
          @save="saveTTSSettings"
          @test="testTTS"
          @switch-section="(s) => activeSection = s as Section"
        />

        <CatalogSection 
          v-if="activeSection === 'styles' || activeSection === 'tones'"
          :type="activeSection as 'styles' | 'tones'"
          :catalog="activeSection === 'styles' ? imageStylesCatalog : toneCatalog"
          :is-generating-item="isGeneratingItem"
          :open-menu-id="openMenuId"
          :simple-model="t2iForm.simple_model"
          @add-item="openCatalogModal(activeSection as 'styles' | 'tones')"
          @edit-item="({ item, index }) => openCatalogModal(activeSection as 'styles' | 'tones', item, index)"
          @remove-item="(index) => removeCatalogItem(activeSection as 'styles' | 'tones', index)"
          @generate-image="({ item, index }) => generateCatalogImage(activeSection as 'styles' | 'tones', item, index)"
          @open-prompt="({ item, index }) => openPromptModal(activeSection as 'styles' | 'tones', item, index)"
          @upload-image="({ event, item, index }) => onUploadFile(event, activeSection as 'styles' | 'tones', item, index)"
          @update-menu-id="(id) => openMenuId = id"
        />

        <GameSettingsSection 
          v-if="activeSection === 'game'"
          :game-form="gameForm"
          :is-submitting="isSubmitting"
          @save="saveGameSettings"
        />

        <UserManagementSection 
          v-if="activeSection === 'users'"
          :users-list="usersList"
          @add-user="openUserModal()"
          @edit-user="openUserModal"
          @remove-user="removeUser"
        />

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

    <!-- MODALS -->
    <UserEditModal 
      :is-open="isUserModalOpen"
      :is-editing-existing="isEditingExistingUser"
      :user="editingUser"
      :is-submitting="isSubmitting"
      @close="isUserModalOpen = false"
      @save="(u) => { editingUser = u; saveUser() }"
    />

    <CatalogEditModal 
      :is-open="isCatalogModalOpen"
      :is-editing-existing="isEditingExisting"
      :item="editingItem"
      :index="editingIndex"
      :type="catalogModalType"
      :is-generating="isGeneratingItem.modal_generating"
      :is-submitting="isSubmitting"
      @close="isCatalogModalOpen = false"
      @save="(item) => { editingItem = item; saveCatalogItem() }"
      @generate="({ type, item, index }) => generateCatalogImage(type, item, index)"
      @upload="({ event, type, item, index }) => onUploadFile(event, type, item, index)"
    />

    <PromptInputModal 
      :is-open="isPromptModalOpen"
      :data="promptModalData"
      @close="isPromptModalOpen = false"
      @generate="({ type, item, index, prompt }) => generateCatalogImage(type, item, index, prompt)"
    />

  </div>
</template>
>

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

