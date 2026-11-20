<script setup lang="ts">
/**
 * Regions (world sections): spatial groups of scenes on a world map, for large adventures.
 * The region list is edited as a draft and saved through the save bar; choosing a region's
 * scenes runs immediately. Spec: docs/specs/world_sections.md.
 */
import { computed, ref } from 'vue'
import { Globe2, Plus } from 'lucide-vue-next'
import { useEditor } from '@/composables/editor/editorContext'
import { useConfirm, usePrompt } from '@/composables/useDialogs'
import { useDraft } from '@/composables/useDraft'
import { useToast } from '@/composables/useToast'
import { useUnsavedGuard } from '@/composables/useUnsavedGuard'
import { sectionService, sectionsOf, type WorldSection } from '@/services/sectionService'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import RegionForm from '@/components/editor/regions/RegionForm.vue'
import RegionSceneAssignModal from '@/components/editor/regions/RegionSceneAssignModal.vue'
import RegionWorldMap from '@/components/editor/regions/RegionWorldMap.vue'
import { regionIdFor, regionLinks, sceneCount } from '@/components/editor/regions/regionGraph'

const editor = useEditor()
const confirm = useConfirm()
const prompt = usePrompt()
const toast = useToast()

const { draft, isDirty, changedCount, isSaving, reset, commit } = useDraft<WorldSection[]>(() =>
  sectionsOf(editor.debugData?.adventure),
)
useUnsavedGuard(isDirty)

const selectedId = ref<string | null>(null)
const assignOpen = ref(false)
const assigning = ref(false)

const scenes = computed(() => (editor.editorScenes || []) as { id: string; label?: string; name?: string; section_id?: string | null }[])
const selected = computed(() => draft.value.find((s) => s.id === selectedId.value) || null)
const links = computed(() => regionLinks(draft.value, scenes.value, editor.debugData?.exits || []))
const counts = computed(() => Object.fromEntries(draft.value.map((s) => [s.id, sceneCount(scenes.value, s.id)])))
const labels = computed(() => Object.fromEntries(draft.value.map((s) => [s.id, s.label])))
const sceneOptions = computed(() =>
  scenes.value.map((s) => ({ id: s.id, label: s.label || s.name || s.id, sectionId: s.section_id || null })),
)
const unassigned = computed(() => scenes.value.filter((s) => !s.section_id).length)

async function addRegion(): Promise<void> {
  const label = await prompt({ title: 'New region', label: 'Name', placeholder: 'e.g. Harbor Town', validate: (v) => (v.trim() ? null : 'Enter a name.') })
  if (!label) return
  const id = regionIdFor(label, new Set(draft.value.map((s) => s.id)))
  const index = draft.value.length
  draft.value.push({
    id, label: label.trim(), description: '', map_x: 15 + (index % 4) * 23, map_y: Math.min(90, 20 + Math.floor(index / 4) * 25),
    order_index: index, status: 'stub', brief: '', summary: '', planned_links: [],
  })
  selectedId.value = id
}

async function deleteRegion(section: WorldSection): Promise<void> {
  const count = counts.value[section.id] || 0
  const ok = await confirm({
    title: `Delete ${section.label}?`,
    message: count ? `Its ${count} scene(s) stay in the adventure but no longer belong to a region.` : 'The region is removed when you save.',
    confirmLabel: 'Delete region',
    danger: true,
  })
  if (!ok) return
  draft.value = draft.value
    .filter((s) => s.id !== section.id)
    .map((s) => ({ ...s, planned_links: s.planned_links.filter((l) => l.to_section_id !== section.id) }))
  selectedId.value = null
}

function moveRegion(id: string, x: number, y: number): void {
  const section = draft.value.find((s) => s.id === id)
  if (!section) return
  section.map_x = x
  section.map_y = y
}

async function save(): Promise<void> {
  try {
    await commit(async (sections) => {
      const result = await sectionService.saveSections(editor.adventureId, sections)
      if (result.cleared_scene_ids.length) toast.info(`${result.cleared_scene_ids.length} scene(s) no longer belong to a region.`)
      await editor.fetchDebugInfo()
    })
    toast.success('Regions saved.')
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Failed to save the regions.')
  }
}

function openAssign(): void {
  if (isDirty.value) {
    toast.warn('Save the regions first, then choose their scenes.')
    return
  }
  assignOpen.value = true
}

async function applyAssignment(added: string[], removed: string[]): Promise<void> {
  const id = selectedId.value
  if (!id) return
  assigning.value = true
  try {
    if (added.length) await sectionService.assignScenes(editor.adventureId, id, added)
    if (removed.length) await sectionService.assignScenes(editor.adventureId, null, removed)
    await editor.fetchDebugInfo()
    assignOpen.value = false
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Failed to move the scenes.')
  } finally {
    assigning.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Regions" description="Group the scenes of a large world into regions on a world map. Small adventures need none.">
      <template #actions>
        <UiButton variant="primary" :icon="Plus" @click="addRegion">Add region</UiButton>
      </template>
    </PageHeader>

    <UiEmptyState
      v-if="!draft.length"
      :icon="Globe2"
      title="No regions yet"
      description="Without regions all scenes share one map, which works well for up to about 15 scenes."
    />

    <template v-else>
      <UiCard title="World map" :description="`Drag a region to move it. ${unassigned} scene(s) belong to no region.`">
        <RegionWorldMap :sections="draft" :links="links" :selected-id="selectedId" :scene-counts="counts" @select="selectedId = $event" @move="moveRegion" />
      </UiCard>

      <UiCard v-if="selected" :title="selected.label">
        <RegionForm
          :key="selected.id"
          v-model="draft[draft.indexOf(selected)]"
          :others="draft.filter((s) => s.id !== selected?.id)"
          :scene-count="counts[selected.id] || 0"
          @assign-scenes="openAssign"
          @delete="deleteRegion(selected)"
        />
      </UiCard>
      <p v-else class="wb-hint">Select a region on the map to edit it.</p>
    </template>

    <RegionSceneAssignModal
      v-model:open="assignOpen"
      :section="selected"
      :scenes="sceneOptions"
      :section-labels="labels"
      :saving="assigning"
      @apply="applyAssignment"
    />

    <UiSaveBar :dirty="isDirty" :count="changedCount" :saving="isSaving" @save="save" @discard="reset" />
  </div>
</template>
