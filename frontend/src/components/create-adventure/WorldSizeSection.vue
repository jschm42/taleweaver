<script setup lang="ts">
/** How much the World-Builder generates: ranges per category and the event script switch. */
import { useCreateAdventureContext } from '@/composables/createAdventure/createAdventureContext'
import type { LimitKey } from '@/composables/createAdventure/createAdventureForm'
import LimitRow from '@/components/create-adventure/LimitRow.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const { form } = useCreateAdventureContext()

type EnabledKey = 'quest_generation_enabled' | 'container_generation_enabled' | 'text_log_generation_enabled' | 'award_generation_enabled'

const ROWS: {
  limit: LimitKey
  label: string
  description: string
  bounds: [number, number]
  defaults: [number, number]
  enabledKey?: EnabledKey
}[] = [
  { limit: 'sequences', label: 'Chapters', description: 'Story chapters played in order.', bounds: [1, 15], defaults: [3, 5] },
  { limit: 'scenes', label: 'Scenes', description: 'Places to explore.', bounds: [1, 20], defaults: [3, 6] },
  { limit: 'items', label: 'Items', description: 'Objects in the world and in inventories.', bounds: [0, 50], defaults: [5, 25] },
  { limit: 'quests', label: 'Side quests', description: 'Optional goals next to the main story.', bounds: [0, 10], defaults: [3, 5], enabledKey: 'quest_generation_enabled' },
  { limit: 'containers', label: 'Containers', description: 'Chests, drawers and other holders of items.', bounds: [0, 20], defaults: [2, 6], enabledKey: 'container_generation_enabled' },
  { limit: 'text_logs', label: 'Readable texts', description: 'Letters, books and signs.', bounds: [0, 20], defaults: [1, 5], enabledKey: 'text_log_generation_enabled' },
  { limit: 'awards', label: 'Awards', description: 'Achievements in bronze, silver and gold.', bounds: [0, 10], defaults: [3, 8], enabledKey: 'award_generation_enabled' },
]
</script>

<template>
  <UiCard
    title="World size"
    description="Larger worlds take longer to build. Regions are added later in the World-Editor (Regions page)."
  >
    <div class="divide-y divide-wb-line">
      <LimitRow v-for="row in ROWS" :key="row.limit" :form="form" v-bind="row" />
    </div>
    <div class="mt-2 border-t border-wb-line pt-4">
      <UiToggle
        v-model="form.scripts_generation_enabled"
        label="Event scripts"
        description="Python scripts for puzzles, traps and scene logic, checked before the world is saved."
      />
    </div>
  </UiCard>
</template>
