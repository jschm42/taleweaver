<script setup lang="ts">
import { ref, watch } from 'vue'
import { Check, Copy } from 'lucide-vue-next'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const open = defineModel<boolean>('open', { default: false })

const props = defineProps<{
  plainToken: string
}>()

const emit = defineEmits<{
  close: []
}>()

const copied = ref(false)
const copyError = ref('')

watch(open, (isOpen) => {
  if (isOpen) {
    copied.value = false
    copyError.value = ''
  }
})

async function copyToken(): Promise<void> {
  copyError.value = ''
  try {
    await navigator.clipboard.writeText(props.plainToken)
    copied.value = true
  } catch {
    copyError.value = 'Could not copy to clipboard; copy the token manually.'
  }
}

function finish(): void {
  open.value = false
  emit('close')
}
</script>

<template>
  <UiModal v-model:open="open" title="Access token created" persistent>
    <div class="space-y-4">
      <UiNotice tone="warn" title="Save this token now">
        For security, this token is shown only once. If you lose it, revoke it and create a new one.
      </UiNotice>

      <UiField label="Bearer token">
        <div class="flex flex-col gap-2 sm:flex-row">
          <UiInput
            :model-value="plainToken"
            readonly
            mono
            class="flex-1"
            @focus="($event.target as HTMLInputElement).select()"
          />
          <UiButton variant="secondary" :icon="copied ? Check : Copy" @click="copyToken">
            {{ copied ? 'Copied' : 'Copy token' }}
          </UiButton>
        </div>
      </UiField>

      <p v-if="copyError" class="wb-hint !text-wb-danger-text" role="alert">{{ copyError }}</p>
    </div>

    <template #footer>
      <UiButton variant="primary" @click="finish">Done</UiButton>
    </template>
  </UiModal>
</template>
