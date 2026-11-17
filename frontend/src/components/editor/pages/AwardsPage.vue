<script setup lang="ts">
import { computed, ref } from 'vue'
import { Award as AwardIcon, Plus } from 'lucide-vue-next'
import { useEditor } from '@/composables/editor/editorContext'
import { useAwards, type Award } from '@/composables/editor/useAwards'
import { useEntityReferences } from '@/composables/editor/useEntityReferences'
import { useConfirm } from '@/composables/useDialogs'
import AwardCard from '@/components/editor/awards/AwardCard.vue'
import AwardEditModal from '@/components/editor/awards/AwardEditModal.vue'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'

/** Awards: achievements players earn. The dialog and deleting save the award list at once. */
const editor = useEditor()
const confirm = useConfirm()
const list = useAwards(editor)
const references = useEntityReferences(editor)

const dialogOpen = ref(false)
const isNew = ref(false)
const draft = ref<Award>(list.blankAward())
const takenKeys = computed(() => list.awards.value.map((a) => String(a.key || '')))

function openNew(): void {
  isNew.value = true
  draft.value = list.blankAward()
  dialogOpen.value = true
}

function openEdit(award: Award): void {
  isNew.value = false
  draft.value = list.editableCopy(award)
  dialogOpen.value = true
}

function save(): void {
  if (list.save(draft.value, isNew.value)) dialogOpen.value = false
}

async function remove(award: Award): Promise<void> {
  const yes = await confirm({
    title: `Delete "${award.title || award.key}"?`,
    message: 'Players can no longer earn this award.',
    confirmLabel: 'Delete award',
    danger: true,
  })
  if (yes) list.remove(String(award.key))
}
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Awards" description="Achievements in bronze, silver and gold, plus negative awards for blunders.">
      <template #badge>
        <UiBadge>{{ list.awards.value.length }}</UiBadge>
      </template>
      <template #actions>
        <UiButton variant="primary" :icon="Plus" @click="openNew">Add award</UiButton>
      </template>
    </PageHeader>

    <UiEmptyState
      v-if="!list.awards.value.length"
      :icon="AwardIcon"
      title="No awards yet"
      description="Awards celebrate clever solutions, secrets found and battles won."
    >
      <template #action>
        <UiButton variant="primary" :icon="Plus" @click="openNew">Add the first award</UiButton>
      </template>
    </UiEmptyState>

    <div v-else class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <AwardCard
        v-for="award in list.awards.value"
        :key="award.key || award.title"
        :award="award"
        :busy="editor.isSaving"
        @edit="openEdit(award)"
        @remove="remove(award)"
      />
    </div>

    <AwardEditModal
      v-model:open="dialogOpen"
      v-model:award="draft"
      :is-new="isNew"
      :saving="editor.isSaving"
      :taken-keys="takenKeys"
      :references="references.all.value"
      :text-references="editor.referenceOptions || []"
      @save="save"
    />
  </div>
</template>
