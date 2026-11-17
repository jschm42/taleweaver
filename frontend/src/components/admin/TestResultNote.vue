<script setup lang="ts">
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'

/** Result of a provider test run (`testService.testResults[...]`). */
defineProps<{ result?: { status: 'loading' | 'success' | 'error' | string; message?: string } | null }>()
</script>

<template>
  <div v-if="result" aria-live="polite">
    <p v-if="result.status === 'loading'" class="flex items-center gap-2 wb-body text-wb-muted">
      <UiSpinner size="sm" /> {{ result.message || 'Testing…' }}
    </p>
    <UiNotice v-else :tone="result.status === 'success' ? 'success' : 'danger'">{{ result.message }}</UiNotice>
  </div>
</template>
