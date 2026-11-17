<script setup lang="ts">
import { computed } from 'vue'
import { dialogQueue, settleDialog } from '@/composables/useDialogs'
import UiConfirmDialog from '@/components/ui/UiConfirmDialog.vue'
import UiPromptDialog from '@/components/ui/UiPromptDialog.vue'

/** Shows the first queued question dialog. Mounted once in App.vue. */
const current = computed(() => dialogQueue.items[0] ?? null)
</script>

<template>
  <template v-if="current">
    <UiConfirmDialog
      v-if="current.kind === 'confirm'"
      :key="current.id"
      :options="current.options"
      @resolve="(value) => settleDialog(current!.id, value)"
    />
    <UiPromptDialog
      v-else
      :key="current.id"
      :options="current.options"
      @resolve="(value) => settleDialog(current!.id, value)"
    />
  </template>
</template>
