<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { Save } from 'lucide-vue-next'
import UiButton from '@/components/ui/UiButton.vue'

/**
 * Sticky bar at the bottom of a page while it has unsaved changes. Ctrl+S / Cmd+S saves.
 * Pair it with `useDraft` (dirty state, count, commit) and `useUnsavedGuard`.
 */
const props = withDefaults(
  defineProps<{ dirty: boolean; count?: number; saving?: boolean; errorCount?: number }>(),
  { count: 0, saving: false, errorCount: 0 },
)

const emit = defineEmits<{ save: []; discard: [] }>()

function handleKeydown(event: KeyboardEvent): void {
  const isSave = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's'
  if (!isSave || !props.dirty) {
    return
  }
  event.preventDefault()
  if (!props.saving && props.errorCount === 0) {
    emit('save')
  }
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <Transition
    enter-active-class="transition duration-150 ease-out"
    enter-from-class="opacity-0 translate-y-2"
    leave-active-class="transition duration-100 ease-in"
    leave-to-class="opacity-0 translate-y-2"
  >
    <div
      v-if="dirty"
      class="sticky bottom-0 z-30 mt-6 flex items-center justify-between gap-4 rounded-xl border border-wb-line-strong bg-wb-overlay px-4 py-3 shadow-wb-float font-wb"
      role="region"
      aria-label="Unsaved changes"
    >
      <p class="wb-label flex items-center gap-2">
        <span class="h-2 w-2 rounded-full bg-wb-warn" aria-hidden="true" />
        <span v-if="errorCount > 0" class="text-wb-danger-text">
          {{ errorCount }} {{ errorCount === 1 ? 'field needs' : 'fields need' }} attention
        </span>
        <span v-else>{{ count }} unsaved {{ count === 1 ? 'change' : 'changes' }}</span>
      </p>
      <div class="flex items-center gap-2">
        <UiButton variant="ghost" size="sm" :disabled="saving" @click="emit('discard')">Discard</UiButton>
        <UiButton
          variant="primary"
          size="sm"
          :icon="Save"
          :loading="saving"
          :disabled="errorCount > 0"
          @click="emit('save')"
        >
          Save
        </UiButton>
      </div>
    </div>
  </Transition>
</template>
