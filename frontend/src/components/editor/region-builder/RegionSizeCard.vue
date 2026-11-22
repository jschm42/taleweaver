<script setup lang="ts">
/**
 * Card 4 of the Region Builder: how much the region gets. Simple mode picks a size preset;
 * advanced mode sets a range per category, the feature switches, scripts and strictness.
 */
import { useRegionBuilderContext } from '@/composables/regionBuilder/regionBuilderContext'
import { SIZE_PRESETS, type SizePreset } from '@/composables/regionBuilder/regionBuilderForm'
import LimitRow from '@/components/create-adventure/LimitRow.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const { form } = useRegionBuilderContext()

type EnabledKey = 'quest_generation_enabled' | 'container_generation_enabled' | 'text_log_generation_enabled' | 'award_generation_enabled'

const PRESETS = (Object.keys(SIZE_PRESETS) as SizePreset[]).map((key) => ({
  value: key,
  label: `${SIZE_PRESETS[key].label} (${SIZE_PRESETS[key].scenes[0]}-${SIZE_PRESETS[key].scenes[1]} scenes)`,
}))

const STRICTNESS = [
  { value: 'creative' as const, label: 'Creative' },
  { value: 'strict' as const, label: 'Strict' },
]

const ROWS: {
  limit: string
  label: string
  description: string
  bounds: [number, number]
  defaults: [number, number]
  enabledKey?: EnabledKey
}[] = [
  { limit: 'scenes', label: 'Scenes', description: 'Places to explore in this region.', bounds: [1, 30], defaults: [6, 10] },
  { limit: 'items', label: 'Items', description: 'Objects in the region and in inventories.', bounds: [0, 40], defaults: [4, 12] },
  { limit: 'sequences', label: 'Chapters', description: 'Only when the region carries its own story step.', bounds: [0, 5], defaults: [0, 1] },
  { limit: 'quests', label: 'Side quests', description: 'Optional goals in this region.', bounds: [0, 10], defaults: [0, 2], enabledKey: 'quest_generation_enabled' },
  { limit: 'containers', label: 'Containers', description: 'Chests, drawers and other holders of items.', bounds: [0, 15], defaults: [1, 3], enabledKey: 'container_generation_enabled' },
  { limit: 'text_logs', label: 'Readable texts', description: 'Letters, books and signs.', bounds: [0, 15], defaults: [0, 3], enabledKey: 'text_log_generation_enabled' },
  { limit: 'awards', label: 'Awards', description: 'Achievements in bronze, silver and gold.', bounds: [0, 10], defaults: [0, 2], enabledKey: 'award_generation_enabled' },
]
</script>

<template>
  <UiCard v-if="form" title="Region size" description="Larger regions take longer to build.">
    <div v-if="form.mode === 'simple'" class="space-y-2">
      <UiSegmented v-model="form.size" :options="PRESETS" label="Region size" />
      <p class="wb-hint">Characters, items and quests adapt to the idea. Switch to Advanced to set every count.</p>
    </div>
    <template v-else>
      <div class="divide-y divide-wb-line">
        <LimitRow v-for="row in ROWS" :key="row.limit" :form="form.options" v-bind="row" />
      </div>
      <div class="mt-2 space-y-4 border-t border-wb-line pt-4">
        <UiToggle
          v-model="form.options.scripts_generation_enabled"
          label="Event scripts"
          description="Python scripts for puzzles, traps and scene logic, checked before the region is saved."
        />
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="min-w-0">
            <p class="wb-label text-wb-strong">Strictness</p>
            <p class="wb-hint">Strict builds exactly what the idea names; creative expands it freely.</p>
          </div>
          <UiSegmented v-model="form.options.generation_strictness" :options="STRICTNESS" label="Strictness" />
        </div>
      </div>
    </template>
  </UiCard>
</template>
