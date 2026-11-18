<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Wand2 } from 'lucide-vue-next'
import WorkbenchShell from '@/components/workbench/WorkbenchShell.vue'
import WorkbenchNav from '@/components/workbench/WorkbenchNav.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import ProviderKeysSection from '@/components/admin/ProviderKeysSection.vue'
import IntelligenceSection from '@/components/admin/IntelligenceSection.vue'
import VisualsSection from '@/components/admin/VisualsSection.vue'
import SpeechSection from '@/components/admin/SpeechSection.vue'
import SpeechToTextSection from '@/components/admin/SpeechToTextSection.vue'
import VoiceMappingSection from '@/components/admin/VoiceMappingSection.vue'
import AudioSection from '@/components/admin/AudioSection.vue'
import CatalogSection from '@/components/admin/CatalogSection.vue'
import NarratorVoicesSection from '@/components/admin/NarratorVoicesSection.vue'
import UserManagementSection from '@/components/admin/UserManagementSection.vue'
import UserEditModal from '@/components/admin/UserEditModal.vue'
import CatalogEditModal from '@/components/admin/CatalogEditModal.vue'
import PromptInputModal from '@/components/admin/PromptInputModal.vue'
import { useAdminNavigation } from '@/components/admin/useAdminNavigation'
import { useCatalogEditing, useSettingsActions, useUserEditing, type CatalogType } from '@/components/admin/useAdminActions'
import { showToast } from '@/composables/useToast'
import { configState } from '@/store/config'
import { restartSetupWizard } from '@/store/setupWizard'
import { settingsService } from '@/services/settingsService'
import { userService } from '@/services/userService'
import { catalogService } from '@/services/catalogService'
import { testService } from '@/services/testService'

const router = useRouter()
const { activeSection, navGroups, hasNoProviderKey, select } = useAdminNavigation()
const settings = useSettingsActions()
const users = useUserEditing()
const catalog = useCatalogEditing()

const catalogType = computed<CatalogType>(() => (activeSection.value === 'tones' ? 'tones' : 'styles'))
const catalogItems = computed(() =>
  catalogType.value === 'tones' ? catalogService.toneCatalog.value : catalogService.imageStylesCatalog.value,
)

// The services keep `statusMessage` (the setup wizard reads it); the admin shows it as a toast.
for (const service of [settingsService, userService, catalogService]) {
  watch(service.statusMessage, (message) => {
    if (message) showToast(message.text, { tone: message.type === 'success' ? 'success' : 'error' })
  })
}

onMounted(() => {
  settingsService.fetchSettings()
  userService.fetchUsers()
})
</script>

<template>
  <WorkbenchShell
    title="Admin console"
    :subtitle="`TaleWeaver v${configState.appVersion}`"
    back-label="Back to the portal"
    :page-key="activeSection"
    :wide="activeSection === 'voice-map'"
    @back="router.push({ name: 'portal' })"
  >
    <template #nav>
      <WorkbenchNav :groups="navGroups" :active="activeSection" @select="select" />
    </template>
    <template #footer>
      <UiButton variant="ghost" size="sm" :icon="Wand2" block class="!justify-start" @click="restartSetupWizard">
        Setup assistant
      </UiButton>
    </template>

    <UiNotice v-if="hasNoProviderKey && activeSection !== 'keys'" tone="warn" title="AI configuration required">
      Add at least one provider key and choose a model before adventures can be generated or played.
      <template #action>
        <UiButton size="sm" @click="select('keys')">Open API keys</UiButton>
      </template>
    </UiNotice>

    <ProviderKeysSection
      v-if="activeSection === 'keys'"
      :configured-keys="settingsService.configuredKeys.value"
      :is-submitting="settingsService.isSubmitting.value"
      @save="({ provider, api_key }) => settings.saveApiKey(provider, api_key)"
      @delete="settings.deleteApiKey"
    />

    <IntelligenceSection
      v-if="activeSection === 'llm'"
      :llm-form="settingsService.llmForm.value"
      :available-constants="settingsService.availableConstants.value"
      :configured-keys="settingsService.configuredKeys.value"
      :is-submitting="settingsService.isSubmitting.value"
      :is-loading-ollama-models="settingsService.isLoadingOllamaModels.value"
      :test-results="testService.testResults.value"
      @save="settings.saveLlm"
      @test="settings.testLlm"
      @refresh-ollama-models="settings.refreshOllamaModels"
      @switch-section="select"
    />

    <VisualsSection
      v-if="activeSection === 't2i'"
      :t2i-form="settingsService.t2iForm.value"
      :available-constants="settingsService.availableConstants.value"
      :configured-keys="settingsService.configuredKeys.value"
      :is-submitting="settingsService.isSubmitting.value"
      :is-loading-stable-diffusion-models="settingsService.isLoadingStableDiffusionModels.value"
      :test-results="testService.testResults.value"
      @save="settings.saveT2i"
      @test="settings.testVision"
      @refresh-stable-diffusion-models="settings.refreshStableDiffusionModels"
      @switch-section="select"
    />

    <SpeechSection
      v-if="activeSection === 'tts'"
      :tts-form="settingsService.ttsForm.value"
      :configured-keys="settingsService.configuredKeys.value"
      :is-submitting="settingsService.isSubmitting.value"
      :test-results="testService.testResults.value"
      @save="settings.saveTts"
      @test="settings.testTts"
      @switch-section="select"
    />

    <VoiceMappingSection v-if="activeSection === 'voice-map'" />

    <SpeechToTextSection
      v-if="activeSection === 'stt'"
      :game-form="settingsService.gameForm.value"
      :is-submitting="settingsService.isSubmitting.value"
      @save="settings.saveGame"
    />

    <AudioSection v-if="activeSection === 'audio'" />

    <CatalogSection
      v-if="activeSection === 'styles' || activeSection === 'tones'"
      :type="catalogType"
      :catalog="catalogItems"
      :is-generating-item="catalogService.isGeneratingItem.value"
      :simple-model="settingsService.t2iForm.value.simple_model"
      @add-item="catalog.open(catalogType)"
      @edit-item="({ item, index }) => catalog.open(catalogType, item, index)"
      @remove-item="(index) => catalog.remove(catalogType, index)"
      @generate-image="({ item, index }) => catalog.generateImage(catalogType, item, index)"
      @open-prompt="({ item, index }) => catalog.openPrompt(catalogType, item, index)"
      @upload-image="({ event, item, index }) => catalog.uploadImage(event, catalogType, item, index)"
    />

    <NarratorVoicesSection v-if="activeSection === 'voices'" />

    <UserManagementSection
      v-if="activeSection === 'users'"
      :users-list="userService.usersList.value"
      @add-user="users.open()"
      @edit-user="users.open"
      @remove-user="users.remove"
    />

    <UserEditModal
      :is-open="users.isOpen.value"
      :is-editing-existing="users.isExisting.value"
      :user="users.user.value"
      :is-submitting="userService.isSubmitting.value"
      @close="users.isOpen.value = false"
      @save="users.save"
    />

    <CatalogEditModal
      :is-open="catalog.isOpen.value"
      :is-editing-existing="catalog.index.value !== null"
      :item="catalog.item.value"
      :index="catalog.index.value"
      :type="catalog.type.value"
      :is-generating="!!catalogService.isGeneratingItem.value.modal_generating"
      :is-submitting="catalogService.isSubmitting.value"
      @close="catalog.isOpen.value = false"
      @save="catalog.save"
      @generate="({ type, item, index, prompt }) => catalog.generateImage(type, item, index, prompt)"
      @upload="({ event, type, item, index }) => catalog.uploadImage(event, type, item, index)"
    />

    <PromptInputModal
      :is-open="catalog.isPromptOpen.value"
      :data="catalog.promptData.value"
      @close="catalog.isPromptOpen.value = false"
      @generate="({ type, item, index, prompt }) => catalog.generateImage(type, item, index, prompt)"
    />
  </WorkbenchShell>
</template>
