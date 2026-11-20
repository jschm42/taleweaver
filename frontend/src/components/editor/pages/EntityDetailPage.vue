<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ChevronLeft, ChevronRight, SearchX } from 'lucide-vue-next'
import { useEditor } from '@/composables/editor/editorContext'
import EditEntityModal from '@/components/editor/EditEntityModal.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiIdTag from '@/components/ui/UiIdTag.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'

/**
 * Detail page of a character or item (route adventure-editor-entity). The form tab lives in
 * `?panel=`; previous / next step through the list of the same kind.
 */
const editor = useEditor()
const route = useRoute()
const router = useRouter()

const entityId = computed(() => String(route.params.entityId ?? ''))
const panel = computed(() => (typeof route.query.panel === 'string' ? route.query.panel : 'simple'))

const kind = computed<'npc' | 'object' | null>(() => {
  if ((editor.debugData?.npcs || []).some((npc: any) => String(npc.id) === entityId.value)) return 'npc'
  if (editor.editorAllItems.some((item: any) => String(item.id) === entityId.value)) return 'object'
  return null
})

const listTab = computed(() => (kind.value === 'npc' ? 'inhabitants' : 'items'))
const listLabel = computed(() => (kind.value === 'npc' ? 'Characters' : 'Items'))
const siblings = computed<any[]>(() => (kind.value === 'npc' ? editor.editorNpcs : editor.editorAllItems) || [])
const position = computed(() => siblings.value.findIndex((entry: any) => String(entry.id) === entityId.value))
const entity = computed(() => siblings.value[position.value] ?? null)

const isLoaded = computed(
  () => editor.editEntityContext?.id === entityId.value && !editor.showEditModal && !editor.isCreateEntityMode,
)

// Load the form for this id; again after a save (the save clears the context) or a reload.
watch(
  [entityId, () => editor.debugData, () => editor.editEntityContext],
  () => {
    if (!editor.debugData || isLoaded.value || editor.showEditModal) return
    editor.loadEntityFromWorld(entityId.value)
  },
  { immediate: true },
)

watch(kind, (value) => {
  if (value) editor.activeTab = listTab.value as typeof editor.activeTab
}, { immediate: true })

function openSibling(step: number): void {
  const next = siblings.value[position.value + step]
  if (next) void router.push({ params: { entityId: String(next.id) }, query: { ...route.query } })
}

function backToList(): void {
  void router.push({
    name: 'adventure-editor',
    params: { adventureId: editor.adventureId },
    query: { ...route.query, tab: listTab.value, panel: undefined },
  })
}

function setPanel(tab: string): void {
  if (route.query.panel === tab || (!route.query.panel && tab === 'simple')) return
  void router.replace({ query: { ...route.query, panel: tab === 'simple' ? undefined : tab } })
}

async function save(data: any): Promise<void> {
  const newId = String(data?.entity_id || '').trim().toUpperCase()
  await editor.saveEntityText(data)
  // saveEntityText reloads the world after clearing the form; fill the form from the fresh data.
  editor.loadEntityFromWorld(newId || entityId.value)
  if (newId && newId !== entityId.value) {
    void router.replace({ params: { entityId: newId }, query: { ...route.query } })
  }
}
</script>

<template>
  <div class="space-y-4">
    <nav class="flex flex-wrap items-center justify-between gap-3" aria-label="Breadcrumb">
      <div class="flex min-w-0 items-center gap-2">
        <UiButton variant="ghost" size="sm" :icon="ArrowLeft" @click="backToList">{{ listLabel }}</UiButton>
        <span class="wb-hint" aria-hidden="true">/</span>
        <span class="wb-subheading truncate">{{ entity?.name || entityId }}</span>
        <UiIdTag :value="entityId" />
      </div>
      <div v-if="position >= 0" class="flex items-center gap-1">
        <span class="wb-hint tabular-nums">{{ position + 1 }} / {{ siblings.length }}</span>
        <UiIconButton :icon="ChevronLeft" label="Previous" size="sm" :disabled="position <= 0" @click="openSibling(-1)" />
        <UiIconButton :icon="ChevronRight" label="Next" size="sm" :disabled="position >= siblings.length - 1" @click="openSibling(1)" />
      </div>
    </nav>

    <div v-if="!editor.debugData" class="flex justify-center py-16"><UiSpinner label="Loading" /></div>
    <UiEmptyState
      v-else-if="!kind"
      :icon="SearchX"
      :title="`No character or item “${entityId}”`"
      description="It may have been renamed or deleted."
    >
      <template #action>
        <UiButton @click="backToList">Back to the list</UiButton>
      </template>
    </UiEmptyState>
    <EditEntityModal
      v-else
      variant="page"
      :tab="panel"
      :show="isLoaded"
      :context="editor.editEntityContext"
      :initial-form="editor.editForm"
      :reference-options="editor.referenceOptions"
      :rule-enforcement-mode="editor.form.rule_enforcement_mode"
      :is-saving="editor.isSavingText"
      :adventure-id="editor.adventureId"
      :is-create-entity-mode="false"
      :npc-data="kind === 'npc' ? entity : null"
      :voice-list="editor.voiceList"
      @update:tab="setPanel"
      @close="backToList"
      @save="save"
      @combat-saved="editor.onSpecialAttacksSaved"
    />
  </div>
</template>
