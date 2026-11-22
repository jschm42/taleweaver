<script setup lang="ts">
/**
 * Regions (world sections): spatial groups of scenes on a world map, for large adventures.
 * Regions and the campaign outline are edited as one draft and saved through the save bar;
 * choosing scenes and planning regions run immediately; a planned region is built on the
 * Region Builder page (RegionBuilderPage).
 * Spec: docs/specs/world_sections.md.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Globe2, Plus, Sparkles } from 'lucide-vue-next'
import { useEditor } from '@/composables/editor/editorContext'
import { useConfirm, usePrompt } from '@/composables/useDialogs'
import { useDraft } from '@/composables/useDraft'
import { useToast } from '@/composables/useToast'
import { useUnsavedGuard } from '@/composables/useUnsavedGuard'
import {
  layoutOf,
  outlineOf,
  sectionService,
  sectionsOf,
  type RegionPlan,
  type WorldOutline,
  type WorldSection,
} from '@/services/sectionService'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import RegionForm from '@/components/editor/regions/RegionForm.vue'
import RegionGenerateControls from '@/components/editor/regions/RegionGenerateControls.vue'
import RegionGenerationNotes from '@/components/editor/regions/RegionGenerationNotes.vue'
import RegionOutlineCard from '@/components/editor/regions/RegionOutlineCard.vue'
import RegionPlanModal from '@/components/editor/regions/RegionPlanModal.vue'
import RegionSceneAssignModal from '@/components/editor/regions/RegionSceneAssignModal.vue'
import RegionMapCard from '@/components/editor/regions/RegionMapCard.vue'
import { regionIdFor, regionLinks, sceneCount } from '@/components/editor/regions/regionGraph'

interface RegionsDraft {
  sections: WorldSection[]
  outline: WorldOutline
}

const POLL_MS = 5000

const editor = useEditor()
const confirm = useConfirm()
const prompt = usePrompt()
const toast = useToast()
const router = useRouter()

const { draft, isDirty, changedCount, isSaving, reset, commit } = useDraft<RegionsDraft>(() => ({
  sections: sectionsOf(editor.debugData?.adventure),
  outline: outlineOf(editor.debugData?.adventure),
}))
useUnsavedGuard(isDirty)

const selectedId = ref<string | null>(null)
const assignOpen = ref(false)
const planOpen = ref(false)
const assigning = ref(false)
const mapLayout = computed(() => layoutOf(editor.debugData?.adventure))

const sections = computed(() => draft.value.sections)
const scenes = computed(() => (editor.editorScenes || []) as { id: string; label?: string; name?: string; section_id?: string | null }[])
const selected = computed(() => sections.value.find((s) => s.id === selectedId.value) || null)
const links = computed(() => regionLinks(sections.value, scenes.value, editor.debugData?.exits || []))
const counts = computed(() => Object.fromEntries(sections.value.map((s) => [s.id, sceneCount(scenes.value, s.id)])))
const labels = computed(() => Object.fromEntries(sections.value.map((s) => [s.id, s.label])))
const sceneOptions = computed(() =>
  scenes.value.map((s) => ({ id: s.id, label: s.label || s.name || s.id, sectionId: s.section_id || null })),
)
const unassigned = computed(() => scenes.value.filter((s) => !s.section_id).length)
const generating = computed(() => sectionsOf(editor.debugData?.adventure).some((s) => s.status === 'generating'))

// While a region is generated on the server, reload the editor data until it is done.
let pollTimer: ReturnType<typeof setInterval> | null = null
watch(generating, (busy) => {
  if (busy && !pollTimer) pollTimer = setInterval(() => void editor.fetchDebugInfo(), POLL_MS)
  if (!busy && pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}, { immediate: true })
onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})

async function addRegion(): Promise<void> {
  const label = await prompt({ title: 'New region', label: 'Name', placeholder: 'e.g. Harbor Town', validate: (v) => (v.trim() ? null : 'Enter a name.') })
  if (!label) return
  const id = regionIdFor(label, new Set(sections.value.map((s) => s.id)))
  const index = sections.value.length
  draft.value.sections.push({
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
  draft.value.sections = sections.value
    .filter((s) => s.id !== section.id)
    .map((s) => ({ ...s, planned_links: s.planned_links.filter((l) => l.to_section_id !== section.id) }))
  selectedId.value = null
}

function moveRegion(id: string, x: number, y: number): void {
  const section = sections.value.find((s) => s.id === id)
  if (!section) return
  section.map_x = x
  section.map_y = y
}

function applyPlan(plan: RegionPlan): void {
  draft.value.sections = plan.sections
  if (plan.outline) draft.value.outline = plan.outline
  toast.info('Review the planned regions, then save.')
}

async function save(): Promise<void> {
  try {
    await commit(async (value) => {
      const result = await sectionService.saveSections(editor.adventureId, value.sections)
      await sectionService.saveOutline(editor.adventureId, value.outline)
      if (result.cleared_scene_ids.length) toast.info(`${result.cleared_scene_ids.length} scene(s) no longer belong to a region.`)
      await editor.fetchDebugInfo()
    })
    toast.success('Regions saved.')
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Failed to save the regions.')
  }
}

function openBuilder(section: WorldSection): void {
  void router.push({
    name: 'adventure-editor-region-build',
    params: { adventureId: editor.adventureId, sectionId: section.id },
  })
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
        <UiButton variant="ai" :icon="Sparkles" @click="planOpen = true">Plan regions</UiButton>
        <UiButton variant="primary" :icon="Plus" @click="addRegion">Add region</UiButton>
      </template>
    </PageHeader>

    <UiEmptyState
      v-if="!sections.length"
      :icon="Globe2"
      title="No regions yet"
      description="Without regions all scenes share one map, which works well for up to about 15 scenes."
    />

    <template v-else>
      <RegionMapCard
        mode="edit"
        :adventure-id="editor.adventureId"
        :sections="sections"
        :links="links"
        :scenes="sceneOptions"
        :scene-counts="counts"
        :layout="mapLayout"
        :selected-id="selectedId"
        :blocked="isDirty"
        :description="`Drag a region to move it, click it to edit it. ${unassigned} scene(s) belong to no region.`"
        @open-region="selectedId = $event"
        @move="moveRegion"
        @refresh="editor.fetchDebugInfo"
      />

      <UiCard v-if="selected" :title="selected.label">
        <div class="space-y-6">
          <RegionForm
            :key="selected.id"
            v-model="draft.sections[sections.indexOf(selected)]"
            :others="sections.filter((s) => s.id !== selected?.id)"
            :scene-count="counts[selected.id] || 0"
            @assign-scenes="openAssign"
            @delete="deleteRegion(selected)"
          />
          <RegionGenerationNotes
            v-if="selected.status === 'built' && selected.generation_notes?.length"
            :notes="selected.generation_notes"
            @dismiss="selected.generation_notes = []"
          />
          <RegionGenerateControls
            v-if="selected.status !== 'built'"
            :section="selected"
            :dirty="isDirty"
            @build="openBuilder(selected)"
          />
        </div>
      </UiCard>
      <p v-else class="wb-hint">Select a region on the map to edit it.</p>

      <RegionOutlineCard v-model="draft.outline" :labels="labels" />
    </template>

    <RegionSceneAssignModal
      v-model:open="assignOpen"
      :section="selected"
      :scenes="sceneOptions"
      :section-labels="labels"
      :saving="assigning"
      @apply="applyAssignment"
    />
    <RegionPlanModal v-model:open="planOpen" :adventure-id="editor.adventureId" :existing-ids="sections.map((s) => s.id)" @apply="applyPlan" />

    <UiSaveBar :dirty="isDirty" :count="changedCount" :saving="isSaving" @save="save" @discard="reset" />
  </div>
</template>
