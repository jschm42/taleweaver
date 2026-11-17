<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Sparkles, Square } from 'lucide-vue-next'
import { provideEditor } from '@/composables/editor/editorContext'
import { useEditorFormDraft } from '@/composables/editor/useEditorFormDraft'
import { EDITOR_PAGES, useEditorNavigation } from '@/components/editor/editorNavigation'
import EditorModals from '@/components/editor/EditorModals.vue'
import EntityDetailPage from '@/components/editor/pages/EntityDetailPage.vue'
import WorldBuilderDrawer from '@/components/editor/WorldBuilderDrawer.vue'
import WorkbenchNav from '@/components/workbench/WorkbenchNav.vue'
import WorkbenchShell from '@/components/workbench/WorkbenchShell.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'

/**
 * Adventure editor: Workbench shell, grouped navigation and the World-Builder panel. State and
 * actions live in useAdventureEditor (provided to the pages through the editor context).
 */
const props = defineProps<{
  adventureId: string
}>()

const route = useRoute()
const router = useRouter()
const editor = provideEditor(props)
const { groups, validation } = useEditorNavigation(editor)
const worldBuilderOpen = ref(false)
// Adventure settings: edited on several pages, saved together through the save bar.
const formDraft = useEditorFormDraft(editor)

const WIDE_PAGES = new Set(['map', 'scenes', 'scripts', 'triggers', 'validation'])
const isEntityPage = computed(() => route.name === 'adventure-editor-entity')
const page = computed(() => (isEntityPage.value ? EntityDetailPage : (EDITOR_PAGES[editor.activeTab] ?? EDITOR_PAGES.world)))
const pageKey = computed(() => (isEntityPage.value ? `entity-${String(route.params.entityId)}` : editor.activeTab))

function selectPage(key: string): void {
  if (!(key in EDITOR_PAGES)) return
  if (route.name !== 'adventure-editor') {
    void router.push({ name: 'adventure-editor', params: { adventureId: props.adventureId }, query: { ...route.query, tab: key } })
  }
  editor.activeTab = key as typeof editor.activeTab
}

// The open page lives in the URL (?tab=scripts) on the editor's main route.
watch(
  () => route.query.tab,
  (tab) => {
    if (route.name === 'adventure-editor' && typeof tab === 'string' && tab in EDITOR_PAGES) {
      editor.activeTab = tab as typeof editor.activeTab
    }
  },
  { immediate: true },
)

watch(
  () => editor.activeTab,
  (tab) => {
    if (route.name === 'adventure-editor' && route.query.tab !== tab) {
      void router.replace({ query: { ...route.query, tab } })
    }
  },
)

function handleShortcut(event: KeyboardEvent): void {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    worldBuilderOpen.value = true
  }
}

onMounted(() => window.addEventListener('keydown', handleShortcut))
onBeforeUnmount(() => window.removeEventListener('keydown', handleShortcut))
</script>

<template>
  <WorkbenchShell
    :title="editor.adventure?.title || 'Adventure editor'"
    subtitle="Adventure editor"
    back-label="Back to the portal"
    :page-key="pageKey"
    :wide="!isEntityPage && WIDE_PAGES.has(editor.activeTab)"
    @back="editor.goBack"
  >
    <template #nav>
      <WorkbenchNav :groups="groups" :active="editor.activeTab" @select="selectPage" />
    </template>

    <template #footer>
      <div class="space-y-2">
        <WorkbenchNav :groups="[validation]" :active="editor.activeTab" @select="selectPage" />
        <UiButton variant="ai" size="sm" :icon="Sparkles" block title="Open the World-Builder (Ctrl+K)" @click="worldBuilderOpen = true">
          World-Builder
        </UiButton>
        <UiButton v-if="editor.isGenerating" variant="danger" size="sm" :icon="Square" block @click="editor.stopAllGenerations">
          Stop generation
        </UiButton>
      </div>
    </template>

    <UiNotice v-if="editor.adventure?.cover_source_adventure_name" tone="info">
      This adventure is a cover of “{{ editor.adventure.cover_source_adventure_name }}”.
    </UiNotice>

    <div v-if="editor.isLoading" class="flex justify-center py-24">
      <UiSpinner size="lg" label="Loading the adventure" />
    </div>
    <component :is="page" v-else :key="pageKey" />

    <UiSaveBar
      v-if="!isEntityPage"
      :dirty="formDraft.isDirty.value"
      :count="formDraft.changedFields.value.length"
      :saving="editor.isSaving"
      :error-count="formDraft.errorCount.value"
      @save="formDraft.save"
      @discard="formDraft.discard"
    />

    <EditorModals />
    <WorldBuilderDrawer
      v-model:open="worldBuilderOpen"
      :template-id="adventureId"
      @notify="editor.addNotification"
      @applied="editor.refreshData"
    />
  </WorkbenchShell>
</template>
