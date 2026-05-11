<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { configState } from '@/store/config'
import type { CatalogTile } from '@/types'
import { settingsService } from '@/services/settingsService'
import { userService } from '@/services/userService'
import { catalogService } from '@/services/catalogService'
import { testService } from '@/services/testService'

const router = useRouter()

// ============ NAVIGATION & UI STATE ============
type Section = 'keys' | 'llm' | 't2i' | 'tts' | 'styles' | 'tones' | 'game' | 'users'
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

const handleTestLlm = async (key: string, model: string, provider: string) => {
  await testService.testLlm(key, model, provider, settingsService.llmForm.value.ollama_url)
}

const handleTestVision = async (key: string, model: string, provider: string) => {
  await testService.testVision(key, model, provider, settingsService.t2iForm.value.ollama_url)
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
          :test-results="testService.testResults.value"
          @save="handleSaveLlmSettings"
          @test="({ key, model, provider }) => handleTestLlm(key, model, provider)"
          @switch-section="(s) => activeSection = s as Section"
        />

        <VisualsSection 
          v-if="activeSection === 't2i'"
          :t2i-form="settingsService.t2iForm.value"
          :available-constants="settingsService.availableConstants.value"
          :configured-keys="settingsService.configuredKeys.value"
          :is-submitting="settingsService.isSubmitting.value"
          :test-results="testService.testResults.value"
          @save="handleSaveT2iSettings"
          @test="({ key, model, provider }) => handleTestVision(key, model, provider)"
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
      :is-generating="catalogService.isGeneratingItem.value.modal_generating"
      :is-submitting="catalogService.isSubmitting.value"
      @close="isCatalogModalOpen = false"
      @save="(item) => handleSaveCatalogItem(item)"
      @generate="({ type, item, index }) => handleGenerateCatalogImage(type, item, index)"
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

