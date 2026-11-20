<script setup lang="ts">
import { ref } from 'vue'
import type { ConfirmOptions } from '@/composables/useDialogs'
import UiButton from '@/components/ui/UiButton.vue'
import UiModal from '@/components/ui/UiModal.vue'

/** Yes/no question. Usually opened through `useConfirm()`, not placed by hand. */
const props = defineProps<{ options: ConfirmOptions }>()
const emit = defineEmits<{ resolve: [value: boolean] }>()

const open = ref(true)

function answer(value: boolean): void {
  open.value = false
  emit('resolve', value)
}
</script>

<template>
  <UiModal v-model:open="open" :title="props.options.title" size="sm" alert @close="answer(false)">
    <p v-if="props.options.message" class="whitespace-pre-line">{{ props.options.message }}</p>
    <template #footer>
      <UiButton @click="answer(false)">{{ props.options.cancelLabel ?? 'Cancel' }}</UiButton>
      <UiButton
        :variant="props.options.danger ? 'danger' : 'primary'"
        data-autofocus
        @click="answer(true)"
      >
        {{ props.options.confirmLabel ?? 'Confirm' }}
      </UiButton>
    </template>
  </UiModal>
</template>
