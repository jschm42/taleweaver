<script setup lang="ts">
import { computed, ref } from 'vue'
import { BookOpen, Plus } from 'lucide-vue-next'
import { useEditor } from '@/composables/editor/editorContext'
import { MAX_CHAPTERS, useChapters, type Chapter, type ProgressionMode } from '@/composables/editor/useChapters'
import { useConfirm } from '@/composables/useDialogs'
import ChapterCard from '@/components/editor/chapters/ChapterCard.vue'
import ChapterEditModal from '@/components/editor/chapters/ChapterEditModal.vue'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'

/** Chapters: the story's sequences. List actions and the chapter dialog save at once. */
const editor = useEditor()
const confirm = useConfirm()
const list = useChapters(editor)

const MODES = [
  { value: 'linear' as const, label: 'Linear' },
  { value: 'dynamic' as const, label: 'Dynamic' },
]
const modeHint = computed(() =>
  list.mode.value === 'dynamic'
    ? 'Dynamic: chapters start on entering a scene or by script, without advancing in order. For hubs and sandboxes.'
    : 'Linear: chapters form the main story arc and advance in order when one is completed.',
)
const progression = computed({
  get: (): ProgressionMode => list.mode.value,
  set: (mode: ProgressionMode) => list.setMode(mode),
})

const dialogOpen = ref(false)
const isNew = ref(false)
const draft = ref<Chapter>(list.newChapter())
const references = computed(() => [...list.items.value, ...list.scenes.value, ...list.npcs.value])
const takenIds = computed(() => list.chapters.value.map((s) => String(s.id || '')))
const full = computed(() => list.chapters.value.length >= MAX_CHAPTERS)

function openNew(): void {
  isNew.value = true
  draft.value = list.newChapter()
  dialogOpen.value = true
}

function openEdit(chapter: Chapter): void {
  isNew.value = false
  draft.value = list.editableCopy(chapter)
  dialogOpen.value = true
}

function save(): void {
  if (list.save(draft.value, isNew.value)) dialogOpen.value = false
}

async function remove(chapter: Chapter): Promise<void> {
  const yes = await confirm({
    title: `Delete "${chapter.title || chapter.id}"?`,
    message: list.mode.value === 'dynamic' ? 'The chapter is removed.' : 'The chapter is removed; the others are renumbered.',
    confirmLabel: 'Delete chapter',
    danger: true,
  })
  if (yes) list.remove(String(chapter.id))
}
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Chapters" :description="modeHint">
      <template #badge>
        <UiBadge>{{ list.chapters.value.length }} / {{ MAX_CHAPTERS }}</UiBadge>
      </template>
      <template #actions>
        <UiSegmented v-model="progression" :options="MODES" label="Progression mode" />
        <UiButton variant="primary" :icon="Plus" :disabled="full || editor.isSaving" @click="openNew">Add chapter</UiButton>
      </template>
    </PageHeader>

    <UiEmptyState
      v-if="!list.chapters.value.length"
      :icon="BookOpen"
      title="No chapters yet"
      description="Break the adventure into chapters with their own goal, walkthrough and completion rules."
    >
      <template #action>
        <UiButton variant="primary" :icon="Plus" @click="openNew">Add the first chapter</UiButton>
      </template>
    </UiEmptyState>

    <div v-else class="space-y-3">
      <ChapterCard
        v-for="(chapter, index) in list.chapters.value"
        :key="chapter.id || index"
        :chapter="chapter"
        :index="index"
        :count="list.chapters.value.length"
        :mode="list.mode.value"
        :busy="editor.isSaving"
        @edit="openEdit(chapter)"
        @remove="remove(chapter)"
        @move="(step) => list.move(index, step)"
      />
    </div>

    <ChapterEditModal
      v-model:open="dialogOpen"
      v-model:chapter="draft"
      :is-new="isNew"
      :mode="list.mode.value"
      :saving="editor.isSaving"
      :taken-ids="takenIds"
      :references="references"
      @save="save"
    />
  </div>
</template>
