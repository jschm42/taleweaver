<script setup lang="ts">
import { computed } from 'vue'
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import UiField from '@/components/ui/UiField.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'

const ef = useEntityFormContext()

type SlotChoice = '0' | '2' | '4' | '6' | '8'
const SLOT_OPTIONS: { value: SlotChoice; label: string }[] = [
  { value: '0', label: 'Off' },
  { value: '2', label: '2' },
  { value: '4', label: '4' },
  { value: '6', label: '6' },
  { value: '8', label: '8' },
]

// Odd values from imports or the AI fix round up to the next offered step.
const slots = computed<SlotChoice>({
  get: () => {
    const value = Math.max(0, Math.min(8, Number(ef.localForm.memory_slots) || 0))
    return String(Math.ceil(value / 2) * 2) as SlotChoice
  },
  set: (value) => {
    ef.localForm.memory_slots = Number(value)
  },
})
</script>

<template>
  <UiField
    v-if="ef.type === 'npc'"
    label="Memory"
    hint="How many facts about the protagonist this character remembers, e.g. their name, a deal or how they were treated."
    info="The Game Master stores short facts while the protagonist talks to the character; a known topic is updated, and when all slots are full the oldest fact is forgotten. The memories are only sent to the AI while the character is in the scene, but every slot costs prompt tokens, so leave memory off for enemies and extras."
  >
    <UiSegmented v-model="slots" :options="SLOT_OPTIONS" label="Memory slots" />
  </UiField>
</template>
