<script setup lang="ts">
/**
 * The campaign outline: premise and acts are editable; the region plans and story threads come
 * from "Plan regions" and the region generations and are shown for review.
 */
import { computed } from 'vue'
import type { WorldOutline } from '@/services/sectionService'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const outline = defineModel<WorldOutline>({ required: true })

defineProps<{ labels: Record<string, string> }>()

const arcText = computed<string>({
  get: () => outline.value.arc.join('\n'),
  set: (value) => {
    outline.value.arc = value.split('\n').map((line) => line.trim()).filter(Boolean)
  },
})
</script>

<template>
  <UiCard title="Campaign outline" description="Generated regions follow it, so early regions can plant what later ones need.">
    <div class="space-y-4">
      <UiField label="Premise">
        <UiTextarea v-model="outline.premise" :rows="2" />
      </UiField>
      <UiField label="Acts" hint="One act per line.">
        <UiTextarea v-model="arcText" :rows="3" />
      </UiField>
      <div v-if="outline.sections.length" class="space-y-1">
        <p class="wb-label">Region plans</p>
        <p v-for="plan in outline.sections" :key="plan.id" class="wb-body">
          <span class="text-wb-strong">{{ labels[plan.id] || plan.id }}:</span> {{ plan.purpose }}
          <span v-if="plan.gating" class="text-wb-muted"> · needs {{ plan.gating }}</span>
        </p>
      </div>
      <div v-if="outline.threads.length" class="space-y-1">
        <p class="wb-label">Story threads</p>
        <p v-for="thread in outline.threads" :key="thread.id" class="wb-body flex flex-wrap items-center gap-2">
          <UiBadge :tone="thread.status === 'resolved' ? 'accent' : 'neutral'">{{ thread.status }}</UiBadge>
          <span>{{ thread.id }}</span>
          <span class="text-wb-muted">{{ thread.note }}</span>
        </p>
      </div>
    </div>
  </UiCard>
</template>
