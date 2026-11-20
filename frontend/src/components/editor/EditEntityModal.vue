<script setup lang="ts">
import { computed, ref } from 'vue'
import { Save } from 'lucide-vue-next'
import { provideEntityForm } from '@/composables/editor/entityFormContext'
import { useToast } from '@/composables/useToast'
import { provideEntitySubforms } from '@/components/editor/entity/entitySubforms'
import type { EntityFormEmits, EntityFormProps } from '@/composables/editor/useEntityForm'
import EntityFormContent from '@/components/editor/entity/EntityFormContent.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiModal from '@/components/ui/UiModal.vue'

/**
 * Entity form. `variant="page"` renders it inline on the entity detail page; otherwise it is a
 * dialog (cover, protagonist, scene text and creating new entities).
 */
const props = defineProps<EntityFormProps>()
const emit = defineEmits<EntityFormEmits>()

const ef = provideEntityForm(props, emit)
// Combat and companion settings save through their own endpoints; "Save changes" saves them first.
const subforms = provideEntitySubforms()
const toast = useToast()
const savingParts = ref(false)
const busy = computed(() => ef.props.isSaving || savingParts.value)

async function save(): Promise<void> {
  if (ef.isFormInvalid || busy.value) return
  savingParts.value = true
  try {
    const problem = await subforms.saveDirty()
    if (problem) {
      toast.error(problem, 'Not saved')
      return
    }
  } finally {
    savingParts.value = false
  }
  ef.handleSave()
}

const KIND_LABELS: Record<string, string> = {
  npc: 'character',
  object: 'item',
  scene: 'scene',
  cover: 'cover',
  protagonist: 'protagonist',
}
const kind = computed(() => KIND_LABELS[ef.type] ?? ef.type)
const title = computed(() => (ef.props.isCreateEntityMode ? `New ${kind.value}` : `Edit ${kind.value}`))
const saveLabel = computed(() => (ef.props.isCreateEntityMode ? `Create ${kind.value}` : 'Save changes'))

function handleOpenChange(open: boolean): void {
  if (!open) ef.emit('close')
}
</script>

<template>
  <template v-if="ef.props.show && ef.props.context">
    <UiModal
      v-if="!ef.isPage"
      :open="true"
      :title="title"
      size="xl"
      :persistent="busy"
      @update:open="handleOpenChange"
    >
      <EntityFormContent />
      <template #footer>
        <UiButton :disabled="busy" @click="ef.emit('close')">Discard</UiButton>
        <UiButton variant="primary" :icon="Save" :loading="busy" :disabled="ef.isFormInvalid" @click="save">
          {{ saveLabel }}
        </UiButton>
      </template>
    </UiModal>

    <section v-else class="rounded-xl border border-wb-line bg-wb-surface">
      <div class="p-5 sm:p-6">
        <EntityFormContent />
      </div>
      <footer class="sticky bottom-0 z-20 flex items-center justify-end gap-2 rounded-b-xl border-t border-wb-line bg-wb-overlay px-5 py-3">
        <UiButton variant="ghost" :disabled="busy" @click="ef.emit('close')">Back without saving</UiButton>
        <UiButton variant="primary" :icon="Save" :loading="busy" :disabled="ef.isFormInvalid" @click="save">
          {{ saveLabel }}
        </UiButton>
      </footer>
    </section>
  </template>
</template>
