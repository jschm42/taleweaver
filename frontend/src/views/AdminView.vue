<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { configState } from '@/store/config'
import type { CatalogTile } from '@/types'
import { settingsService } from '@/services/settingsService'
import { userService } from '@/services/userService'
import { catalogService } from '@/services/catalogService'
import { testService } from '@/services/testService'
import { restartSetupWizard } from '@/store/setupWizard'

const router = useRouter()

// ============ NAVIGATION & UI STATE ============
type Section = 'keys' | 'llm' | 't2i' | 'tts' | 'stt' | 'styles' | 'tones' | 'game' | 'users'
const activeSection = ref<Section>('keys')

// ============ MODAL STATE (UI only, not shared with services) ============
const isCatalogModalOpen = ref(false)
const catalogModalType = ref<'styles' | 'tones'>('styles')
const editingItem = ref<CatalogTile>({ id: '', name: '', description: '', instruction: '', image_url: '' })
const isEditingExisting = ref(false)
const editingIndex = ref<number | null>(null)

const isUserModalOpen = ref(false)
const editingUser = ref<any>({ username: '', password: '', role: 'user', bio: '' })
const isEditingExistingUser = ref(false)

const isPromptModalOpen = ref(false)
const promptModalData = ref<{ type: 'styles' | 'tones'; item: CatalogTile; index: number } | null>(null)
const customPrompt = ref('')

const openMenuId = ref<string | null>(null)

// ============ COMPONENT IMPORTS ============
import ProviderKeysSection from '@/components/admin/ProviderKeysSection.vue'
import IntelligenceSection from '@/components/admin/IntelligenceSection.vue'
import VisualsSection from '@/components/admin/VisualsSection.vue'
import SpeechSection from '@/components/admin/SpeechSection.vue'
import SpeechToTextSection from '@/components/admin/SpeechToTextSection.vue'
import CatalogSection from '@/components/admin/CatalogSection.vue'
import GameSettingsSection from '@/components/admin/GameSettingsSection.vue'
import UserManagementSection from '@/components/admin/UserManagementSection.vue'
import UserEditModal from '@/components/admin/UserEditModal.vue'
import CatalogEditModal from '@/components/admin/CatalogEditModal.vue'
import PromptInputModal from '@/components/admin/PromptInputModal.vue'

// ============ NAVIGATION & UTILS ============

const goBack = () => {
  router.push({ name: 'portal' })
}

// ============ PROVIDER KEY HANDLERS ============

const handleSaveApiKey = async (provider: string, apiKey: string) => {
  settingsService.statusMessage.value = null
  await settingsService.saveApiKey(provider, apiKey)
}

const handleDeleteApiKey = async (provider: string) => {
  await settingsService.deleteApiKey(provider)
}

// ============ SETTINGS SAVE HANDLERS ============

const handleSaveLlmSettings = async (payload: any) => {
  await settingsService.saveLlmSettings(payload)
}

const handleRefreshOllamaModels = async (ollamaUrl?: string) => {
  await settingsService.fetchOllamaModels(ollamaUrl)
}

const handleRefreshMinimaxModels = async (minimaxUrl?: string) => {
  await settingsService.fetchMinimaxModels(minimaxUrl)
}

const handleRefreshStableDiffusionModels = async (sdUrl?: string) => {
  await settingsService.fetchStableDiffusionModels(sdUrl)
}

const handleSaveT2iSettings = async (payload: any) => {
  await settingsService.saveT2iSettings(payload)
}

const handleSaveTTSSettings = async (payload: any) => {
  await settingsService.saveTTSSettings(payload)
}

const handleSaveGameSettings = async (payload: any) => {
  await settingsService.saveGameSettings(payload)
}

// ============ TEST HANDLERS ============

const handleTestLlm = async (key: string, model: string, provider: string, openrouterProvider?: string) => {
  await testService.testLlm(key, model, provider, settingsService.llmForm.value.ollama_url, openrouterProvider)
}

const handleTestVision = async (payload: any) => {
  await testService.testVision(
    payload.key,
    payload.model,
    payload.provider,
    payload.ollama_url,
    payload.stable_diffusion_url,
    payload.steps,
    payload.cfg_scale,
    payload.width,
    payload.height,
    payload.sampler_name,
    payload.scheduler,
    payload.min_long_edge,
    payload.comfyui_url,
    payload.comfyui_timeout,
    payload.comfyui_workflow
  )
}

const handleTestTTS = async () => {
  await testService.testTTS()
}

// ============ USER MANAGEMENT HANDLERS ============

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

const handleSaveUser = async (userData: any) => {
  editingUser.value = userData
  if (isEditingExistingUser.value) {
    await userService.updateUser(editingUser.value.id, editingUser.value)
  } else {
    await userService.createUser(editingUser.value)
  }
  isUserModalOpen.value = false
}

const handleRemoveUser = async (user: any) => {
  await userService.deleteUser(user.id, user.username)
}

// ============ CATALOG MANAGEMENT HANDLERS ============

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

const handleSaveCatalogItem = async (item: CatalogTile) => {
  catalogService.saveItem(catalogModalType.value, item, isEditingExisting.value ? editingIndex.value : null)
  isCatalogModalOpen.value = false
  await catalogService.saveCurrentCatalog(catalogModalType.value)
}

const handleRemoveCatalogItem = async (index: number) => {
  catalogService.removeItem(catalogModalType.value, index)
  await catalogService.saveCurrentCatalog(catalogModalType.value)
}

const openPromptModal = (type: 'styles' | 'tones', item: CatalogTile, index: number) => {
  promptModalData.value = { type, item, index }
  customPrompt.value = ''
  isPromptModalOpen.value = true
}

const handleGenerateCatalogImage = async (
  type: 'styles' | 'tones',
  item: CatalogTile,
  index: number | null = null,
  prompt: string | null = null,
) => {
  await catalogService.generateImage(type, item, settingsService.t2iForm.value.simple_model, index, prompt)
  isPromptModalOpen.value = false
}

const handleUploadCatalogImage = async (event: Event, type: 'styles' | 'tones', item: CatalogTile, index: number | null = null) => {
  await catalogService.uploadImage(event, type, item, index)
}

// ============ LIFECYCLE ============

onMounted(() => {
  settingsService.fetchSettings()
  userService.fetchUsers()
})



// ============ NAVIGATION CATEGORIES ============
interface NavCategory {
  title: string
  items: {
    id: Section
    label: string
    icon: string
    activeClass: string
    iconColor: string
    badge?: () => string | number | null
  }[]
}

const navCategories: NavCategory[] = [
  {
    title: 'AI & Pipeline',
    items: [
      {
        id: 'keys',
        label: 'Provider Vault',
        icon: 'ra-locked',
        activeClass: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30 shadow-sm shadow-emerald-950/20',
        iconColor: 'text-emerald-400',
        badge: () => Object.keys(settingsService.configuredKeys.value).length || null
      },
      {
        id: 'llm',
        label: 'Intelligence (LLM)',
        icon: 'ra-brain',
        activeClass: 'bg-purple-500/15 text-purple-400 border-purple-500/30 shadow-sm shadow-purple-950/20',
        iconColor: 'text-purple-400'
      },
      {
        id: 't2i',
        label: 'Visuals (Image Gen)',
        icon: 'ra-camera',
        activeClass: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30 shadow-sm shadow-cyan-950/20',
        iconColor: 'text-cyan-400'
      },
      {
        id: 'tts',
        label: 'Speech (TTS)',
        icon: 'ra-speech-bubble',
        activeClass: 'bg-blue-500/15 text-blue-400 border-blue-500/30 shadow-sm shadow-blue-950/20',
        iconColor: 'text-blue-400'
      },
      {
        id: 'stt',
        label: 'Voice Input (STT)',
        icon: 'ra-microphone',
        activeClass: 'bg-teal-500/15 text-teal-400 border-teal-500/30 shadow-sm shadow-teal-950/20',
        iconColor: 'text-teal-400'
      }
    ]
  },
  {
    title: 'Adventure Catalogs',
    items: [
      {
        id: 'styles',
        label: 'Image Styles',
        icon: 'ra-paint-brush',
        activeClass: 'bg-amber-500/15 text-amber-400 border-amber-500/30 shadow-sm shadow-amber-950/20',
        iconColor: 'text-amber-400',
        badge: () => catalogService.imageStylesCatalog.value.length || null
      },
      {
        id: 'tones',
        label: 'Narrative Tones',
        icon: 'ra-scroll',
        activeClass: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30 shadow-sm shadow-indigo-950/20',
        iconColor: 'text-indigo-400',
        badge: () => catalogService.toneCatalog.value.length || null
      }
    ]
  },
  {
    title: 'System & Realm',
    items: [
      {
        id: 'game',
        label: 'Game Settings',
        icon: 'ra-gear',
        activeClass: 'bg-sky-500/15 text-sky-400 border-sky-500/30 shadow-sm shadow-sky-950/20',
        iconColor: 'text-sky-400'
      },
      {
        id: 'users',
        label: 'User Management',
        icon: 'ra-person',
        activeClass: 'bg-rose-500/15 text-rose-400 border-rose-500/30 shadow-sm shadow-rose-950/20',
        iconColor: 'text-rose-400',
        badge: () => userService.usersList.value.length || null
      }
    ]
  }
]
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 font-sans flex overflow-hidden">
    
    <!-- SIDEBAR -->
    <aside class="w-72 bg-slate-900/95 backdrop-blur-sm border-r border-slate-800 flex flex-col p-5 h-screen sticky top-0 z-20">
      <div class="flex items-center gap-3 mb-6 pb-4 border-b border-slate-800/80">
        <button @click="goBack" class="p-2.5 rounded-xl bg-slate-950 border border-slate-800 hover:bg-slate-800 hover:text-white transition-all text-slate-400" title="Return to Portal">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" />
          </svg>
        </button>
        <div>
          <h2 class="text-base font-bold tracking-tight text-white leading-tight">Admin Console</h2>
          <p class="text-[11px] text-slate-500 font-mono">TaleWeaver Engine</p>
        </div>
      </div>

      <!-- Grouped Navigation -->
      <nav class="flex-grow space-y-5 overflow-y-auto pr-1 custom-scrollbar">
        <div v-for="category in navCategories" :key="category.title" class="space-y-1">
          <div class="px-3 text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1.5">
            {{ category.title }}
          </div>
          <button 
            v-for="item in category.items"
            :key="item.id"
            @click="activeSection = item.id as Section"
            :class="[
              'w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left border transition-all duration-200 group',
              activeSection === item.id 
                ? item.activeClass 
                : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/70'
            ]"
          >
            <div class="flex items-center min-w-0">
              <span class="text-xs font-bold truncate">{{ item.label }}</span>
            </div>
            
            <span 
              v-if="item.badge && item.badge() !== null"
              class="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-slate-950/80 border border-slate-800 text-slate-400"
            >
              {{ item.badge() }}
            </span>
          </button>
        </div>
      </nav>

      <button
        type="button"
        class="mt-4 w-full px-3 py-2.5 rounded-xl border border-slate-800 text-left text-xs font-bold text-slate-400 hover:text-white hover:bg-slate-800/70 transition-all"
        title="Walk through API keys, models, visuals and voice step by step"
        @click="restartSetupWizard"
      >
        Setup assistant
      </button>

      <div class="mt-4 pt-4 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500 font-mono">
        <span class="flex items-center gap-1.5">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          Online
        </span>
        <span>v{{ configState.appVersion }}</span>
      </div>
    </aside>

    <!-- CONTENT AREA -->
    <main class="flex-grow p-12 overflow-y-auto max-h-screen custom-scrollbar relative">
      <div class="max-w-4xl mx-auto">
        
        <!-- GLOBAL WARNING -->
        <div v-if="Object.keys(settingsService.configuredKeys).length === 0 && !settingsService.isHydratingSettings.value" class="mb-10 bg-amber-500/10 border border-amber-500/20 rounded-3xl p-8 animate-pulse shadow-2xl">
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
          :configured-keys="settingsService.configuredKeys.value"
          :is-submitting="settingsService.isSubmitting.value"
          @save="({ provider, api_key }) => handleSaveApiKey(provider, api_key)"
          @delete="handleDeleteApiKey"
        />

        <IntelligenceSection 
          v-if="activeSection === 'llm'"
          :llm-form="settingsService.llmForm.value"
          :available-constants="settingsService.availableConstants.value"
          :configured-keys="settingsService.configuredKeys.value"
          :is-submitting="settingsService.isSubmitting.value"
          :is-loading-ollama-models="settingsService.isLoadingOllamaModels.value"
          :is-loading-minimax-models="settingsService.isLoadingMinimaxModels.value"
          :test-results="testService.testResults.value"
          @save="handleSaveLlmSettings"
          @test="({ key, model, provider, openrouterProvider }) => handleTestLlm(key, model, provider, openrouterProvider)"
          @refresh-ollama-models="handleRefreshOllamaModels"
          @refresh-minimax-models="handleRefreshMinimaxModels"
          @switch-section="(s) => activeSection = s as Section"
        />

        <VisualsSection 
          v-if="activeSection === 't2i'"
          :t2i-form="settingsService.t2iForm.value"
          :available-constants="settingsService.availableConstants.value"
          :configured-keys="settingsService.configuredKeys.value"
          :is-submitting="settingsService.isSubmitting.value"
          :is-loading-stable-diffusion-models="settingsService.isLoadingStableDiffusionModels.value"
          :test-results="testService.testResults.value"
          @save="handleSaveT2iSettings"
          @test="handleTestVision"
          @refresh-stable-diffusion-models="handleRefreshStableDiffusionModels"
          @switch-section="(s) => activeSection = s as Section"
        />

        <SpeechSection 
          v-if="activeSection === 'tts'"
          :tts-form="settingsService.ttsForm.value"
          :configured-keys="settingsService.configuredKeys.value"
          :is-submitting="settingsService.isSubmitting.value"
          :test-results="testService.testResults.value"
          @save="handleSaveTTSSettings"
          @test="handleTestTTS"
          @switch-section="(s) => activeSection = s as Section"
        />

        <SpeechToTextSection 
          v-if="activeSection === 'stt'"
          :game-form="settingsService.gameForm.value"
          :is-submitting="settingsService.isSubmitting.value"
          @save="handleSaveGameSettings"
        />

        <CatalogSection 
          v-if="activeSection === 'styles' || activeSection === 'tones'"
          :type="activeSection as 'styles' | 'tones'"
          :catalog="activeSection === 'styles' ? catalogService.imageStylesCatalog.value : catalogService.toneCatalog.value"
          :is-generating-item="catalogService.isGeneratingItem.value"
          :open-menu-id="openMenuId"
          :simple-model="settingsService.t2iForm.value.simple_model"
          @add-item="openCatalogModal(activeSection as 'styles' | 'tones')"
          @edit-item="({ item, index }) => openCatalogModal(activeSection as 'styles' | 'tones', item, index)"
          @remove-item="(index) => handleRemoveCatalogItem(index)"
          @generate-image="({ item, index }) => handleGenerateCatalogImage(activeSection as 'styles' | 'tones', item, index)"
          @open-prompt="({ item, index }) => openPromptModal(activeSection as 'styles' | 'tones', item, index)"
          @upload-image="({ event, item, index }) => handleUploadCatalogImage(event, activeSection as 'styles' | 'tones', item, index)"
          @update-menu-id="(id) => openMenuId = id"
        />

        <GameSettingsSection 
          v-if="activeSection === 'game'"
          :game-form="settingsService.gameForm.value"
          :is-submitting="settingsService.isSubmitting.value"
          @save="handleSaveGameSettings"
        />

        <UserManagementSection 
          v-if="activeSection === 'users'"
          :users-list="userService.usersList.value"
          @add-user="openUserModal()"
          @edit-user="openUserModal"
          @remove-user="handleRemoveUser"
        />

      </div>
    </main>

    <!-- STATUS MESSAGE FLOATER -->
    <div v-if="settingsService.statusMessage.value || userService.statusMessage.value || catalogService.statusMessage.value" 
      :class="['fixed bottom-12 right-12 px-6 py-4 rounded-2xl shadow-2xl text-sm font-bold border max-w-sm animate-slide-in z-[100]', 
      (settingsService.statusMessage.value?.type ?? userService.statusMessage.value?.type ?? catalogService.statusMessage.value?.type) === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20']"
    >
      <div class="flex items-center gap-3">
        <i :class="(settingsService.statusMessage.value?.type ?? userService.statusMessage.value?.type ?? catalogService.statusMessage.value?.type) === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
        {{ settingsService.statusMessage.value?.text ?? userService.statusMessage.value?.text ?? catalogService.statusMessage.value?.text }}
      </div>
    </div>

    <!-- MODALS -->
    <UserEditModal 
      :is-open="isUserModalOpen"
      :is-editing-existing="isEditingExistingUser"
      :user="editingUser"
      :is-submitting="userService.isSubmitting.value"
      @close="isUserModalOpen = false"
      @save="(u) => handleSaveUser(u)"
    />

    <CatalogEditModal 
      :is-open="isCatalogModalOpen"
      :is-editing-existing="isEditingExisting"
      :item="editingItem"
      :index="editingIndex"
      :type="catalogModalType"
      :is-generating="!!catalogService.isGeneratingItem.value.modal_generating"
      :is-submitting="catalogService.isSubmitting.value"
      @close="isCatalogModalOpen = false"
      @save="(item) => handleSaveCatalogItem(item)"
      @generate="({ type, item, index, prompt }) => handleGenerateCatalogImage(type, item, index, prompt)"
      @upload="({ event, type, item, index }) => handleUploadCatalogImage(event, type, item, index)"
    />

    <PromptInputModal 
      :is-open="isPromptModalOpen"
      :data="promptModalData"
      @close="isPromptModalOpen = false"
      @generate="({ type, item, index, prompt }) => handleGenerateCatalogImage(type, item, index, prompt)"
    />

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

