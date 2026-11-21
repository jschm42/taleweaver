<script setup lang="ts">
/**
 * What the author should check after the World-Builder built a region: the fix-ups it made
 * and the validation findings the region introduced (details on the Validation page).
 */
import UiButton from '@/components/ui/UiButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

defineProps<{ notes: string[] }>()

const emit = defineEmits<{ (e: 'dismiss'): void }>()
</script>

<template>
  <UiNotice tone="warn" title="Check the generated region">
    <ul class="list-disc pl-5 space-y-1">
      <li v-for="(note, index) in notes" :key="index">{{ note }}</li>
    </ul>
    <template #action>
      <UiButton size="sm" variant="ghost" @click="emit('dismiss')">Dismiss</UiButton>
    </template>
  </UiNotice>
</template>
