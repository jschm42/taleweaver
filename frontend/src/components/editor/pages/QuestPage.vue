<script setup lang="ts">
import { ref } from 'vue'
import { Plus, ScrollText, Sparkles } from 'lucide-vue-next'
import { useEditor } from '@/composables/editor/editorContext'
import { useEntityReferences } from '@/composables/editor/useEntityReferences'
import { useSideQuests, type Quest } from '@/composables/editor/useSideQuests'
import { useConfirm } from '@/composables/useDialogs'
import QuestCard from '@/components/editor/quests/QuestCard.vue'
import QuestEditModal from '@/components/editor/quests/QuestEditModal.vue'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'

/** Side quests: optional goals for extra XP. The dialog and deleting save the quest list at once. */
const editor = useEditor()
const confirm = useConfirm()
const list = useSideQuests(editor)
const references = useEntityReferences(editor)

const dialogOpen = ref(false)
const isNew = ref(false)
const draft = ref<Quest>(list.blankQuest())

function openNew(): void {
  isNew.value = true
  draft.value = list.blankQuest()
  dialogOpen.value = true
}

async function openDrafted(): Promise<void> {
  const result = await list.draftQuest()
  if (!result) return
  isNew.value = true
  draft.value = list.blankQuest(result.title, result.description)
  dialogOpen.value = true
}

async function redraft(): Promise<void> {
  const result = await list.draftQuest(String(draft.value.id))
  if (!result) return
  draft.value.title = result.title
  draft.value.description = result.description
}

function openEdit(quest: Quest): void {
  isNew.value = false
  draft.value = list.editableCopy(quest)
  dialogOpen.value = true
}

function save(): void {
  list.save(draft.value, isNew.value)
  dialogOpen.value = false
}

async function remove(quest: Quest): Promise<void> {
  const yes = await confirm({
    title: `Delete "${quest.title || quest.id}"?`,
    message: 'The quest is removed from the quest log.',
    confirmLabel: 'Delete quest',
    danger: true,
  })
  if (yes) list.remove(String(quest.id))
}
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Side quests" description="Optional goals and bounties that reward extra XP.">
      <template #badge>
        <UiBadge>{{ list.quests.value.length }}</UiBadge>
      </template>
      <template #actions>
        <UiButton variant="ai" :icon="Sparkles" :loading="list.isGeneratingQuest.value" @click="openDrafted">Draft a quest</UiButton>
        <UiButton variant="primary" :icon="Plus" @click="openNew">Add side quest</UiButton>
      </template>
    </PageHeader>

    <UiEmptyState
      v-if="!list.quests.value.length"
      :icon="ScrollText"
      title="No side quests yet"
      description="Side quests reward exploration off the main path."
    >
      <template #action>
        <UiButton variant="primary" :icon="Plus" @click="openNew">Add the first side quest</UiButton>
      </template>
    </UiEmptyState>

    <div v-else class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <QuestCard
        v-for="quest in list.quests.value"
        :key="quest.id"
        :quest="quest"
        :busy="editor.isSaving"
        @edit="openEdit(quest)"
        @remove="remove(quest)"
      />
    </div>

    <QuestEditModal
      v-model:open="dialogOpen"
      v-model:quest="draft"
      :is-new="isNew"
      :saving="editor.isSaving"
      :references="references.all.value"
      :text-references="editor.referenceOptions || []"
      :generating-quest="list.isGeneratingQuest.value"
      :generating-description="list.isGeneratingDescription.value"
      @save="save"
      @draft-quest="redraft"
      @draft-description="list.draftDescription(draft)"
    />
  </div>
</template>
