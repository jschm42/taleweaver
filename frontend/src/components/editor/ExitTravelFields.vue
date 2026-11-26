<script setup lang="ts">
// Travel time of an exit (WorldExit.travel_minutes / travel_label): a long way between distant
// places costs in-game time when the player uses it (docs/specs/world_sections.md, 6.2).
import { computed } from 'vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'

const minutes = defineModel<number | null>('minutes', { default: null })
const label = defineModel<string>('label', { default: '' })

const hours = computed<number | null>({
  get: () => (minutes.value ? Math.round((minutes.value / 60) * 100) / 100 : null),
  set: (value) => {
    const next = Number(value)
    minutes.value = Number.isFinite(next) && next > 0 ? Math.round(next * 60) : null
  },
})
</script>

<template>
  <div class="grid gap-3 md:grid-cols-[10rem_1fr]">
    <UiField
      label="Travel time (hours)"
      hint="Empty for doors and short paths."
      info="Using this exit advances the in-game clock by this time, instead of the usual few minutes per message. Timers that come due on the way fire on arrival."
    >
      <UiInput v-model="hours" type="number" size="sm" placeholder="0" />
    </UiField>
    <UiField label="Journey" hint="Optional, e.g. 'two days by ship'.">
      <UiInput v-model="label" size="sm" :disabled="!minutes" />
    </UiField>
  </div>
</template>
