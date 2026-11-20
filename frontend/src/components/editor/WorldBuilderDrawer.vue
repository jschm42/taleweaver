<script setup lang="ts">
import { toRef, watch } from 'vue'
import { Send } from 'lucide-vue-next'
import { WORLD_BUILDER_INSTRUCTION_MAX } from '@/services/worldBuilderService'
import { useWorldBuilderInstructions } from '@/composables/useWorldBuilderInstructions'
import WorldBuilderSuggestionsModal from '@/components/editor/WorldBuilderSuggestionsModal.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiDrawer from '@/components/ui/UiDrawer.vue'
import UiField from '@/components/ui/UiField.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

/**
 * AI panel of the editor (opened from the sidebar or with Ctrl+K): describe a change and get up
 * to three proposals. The drawer closes when the proposal dialog opens, so the two never overlap.
 */
const open = defineModel<boolean>('open', { default: false })

const props = defineProps<{
  templateId: string
}>()

const emit = defineEmits<{
  (e: 'notify', message: string, type: 'error' | 'success' | 'info'): void
  (e: 'applied'): void
}>()

const wb = useWorldBuilderInstructions(
  toRef(props, 'templateId'),
  (message, type) => emit('notify', message, type),
  () => emit('applied'),
)
const { instruction, loading, canSubmit } = wb

watch(wb.modalOpen, (isOpen) => {
  if (isOpen) open.value = false
})

function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || !(event.ctrlKey || event.metaKey)) return
  event.preventDefault()
  void wb.submit()
}
</script>

<template>
  <UiDrawer
    v-model:open="open"
    title="World-Builder"
    description="Describe a change, a new character or item, or a script. You get up to three proposals to review before anything is applied."
  >
    <UiField label="Instruction" hint="Ctrl+Enter sends." :count="instruction.length" :max-length="WORLD_BUILDER_INSTRUCTION_MAX">
      <UiTextarea
        v-model="instruction"
        :rows="6"
        :maxlength="WORLD_BUILDER_INSTRUCTION_MAX"
        :disabled="loading"
        placeholder="e.g. &quot;Make the innkeeper more suspicious&quot; or &quot;The chest only opens after the cellar lever was pulled.&quot;"
        data-autofocus
        @keydown="onKeydown"
      />
    </UiField>
    <template #footer>
      <UiButton @click="open = false">Close</UiButton>
      <UiButton variant="ai" :icon="Send" :loading="loading" :disabled="!canSubmit" @click="wb.submit()">Get proposals</UiButton>
    </template>
  </UiDrawer>

  <WorldBuilderSuggestionsModal
    :open="wb.modalOpen.value"
    :instruction="wb.submittedInstruction.value"
    :proposals="wb.proposals.value"
    :note="wb.note.value"
    :loading="wb.loading.value"
    :applying="wb.applying.value"
    :selected-index="wb.selectedIndex.value"
    :has-backup-confirmed="wb.backupConfirmed.value"
    :error-message="wb.errorMessage.value"
    @close="wb.close()"
    @select="wb.selectedIndex.value = $event"
    @toggle-backup="wb.backupConfirmed.value = $event"
    @retry="wb.retry()"
    @apply="wb.applySelected()"
  />
</template>
