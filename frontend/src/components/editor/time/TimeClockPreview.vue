<script setup lang="ts">
import { computed } from 'vue'
import { Clock, Hourglass } from 'lucide-vue-next'
import { useTimeSettings } from '@/composables/editor/useTimeSettings'
import { clockPreview } from '@/utils/timeSettings'

/** What the in-game clock shows at the start of the adventure. */
const { form } = useTimeSettings()
const preview = computed(() => clockPreview(form))
</script>

<template>
  <div class="flex flex-wrap items-center justify-between gap-4">
    <div>
      <p class="wb-label">Clock preview</p>
      <p class="wb-hint">How the in-game clock appears at the start of the adventure.</p>
    </div>
    <div class="flex items-center gap-2.5 rounded-md border border-wb-line bg-wb-raised px-3 py-1.5" aria-live="polite">
      <component :is="preview.isUnits ? Hourglass : Clock" class="h-4 w-4 shrink-0 text-wb-muted" aria-hidden="true" />
      <div class="flex flex-col items-end">
        <span class="wb-hint">{{ preview.date }}</span>
        <span class="wb-mono tabular-nums text-wb-strong">{{ preview.time }}</span>
      </div>
    </div>
  </div>
</template>
