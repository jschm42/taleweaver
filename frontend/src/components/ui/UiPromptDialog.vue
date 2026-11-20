<script setup lang="ts">
import { computed, ref } from 'vue'
import type { PromptOptions } from '@/composables/useDialogs'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

/** Asks for a single value. Usually opened through `usePrompt()`, not placed by hand. */
const props = defineProps<{ options: PromptOptions }>()
const emit = defineEmits<{ resolve: [value: string | null] }>()

const open = ref(true)
const value = ref(props.options.initial ?? '')
const touched = ref(false)

const error = computed(() => (touched.value ? (props.options.validate?.(value.value) ?? null) : null))

function cancel(): void {
  open.value = false
  emit('resolve', null)
}

function submit(): void {
  touched.value = true
  if (props.options.validate?.(value.value)) {
    return
  }
  open.value = false
  emit('resolve', value.value)
}
</script>

<template>
  <UiModal v-model:open="open" :title="props.options.title" size="sm" alert @close="cancel">
    <form class="space-y-3" @submit.prevent="submit">
      <p v-if="props.options.message" class="whitespace-pre-line">{{ props.options.message }}</p>
      <UiField :label="props.options.label ?? 'Value'" :error="error">
        <UiTextarea
          v-if="props.options.multiline"
          v-model="value"
          :placeholder="props.options.placeholder"
          data-autofocus
          @keydown.enter.ctrl.prevent="submit"
        />
        <UiInput v-else v-model="value" :placeholder="props.options.placeholder" data-autofocus />
      </UiField>
      <button type="submit" class="hidden" tabindex="-1" aria-hidden="true" />
    </form>
    <template #footer>
      <UiButton @click="cancel">{{ props.options.cancelLabel ?? 'Cancel' }}</UiButton>
      <UiButton variant="primary" @click="submit">{{ props.options.confirmLabel ?? 'OK' }}</UiButton>
    </template>
  </UiModal>
</template>
