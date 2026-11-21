<script setup lang="ts">
/** Filter row of the editor's lists: region (when the adventure has regions), scene, result count, clear. */
import { X } from 'lucide-vue-next'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import type { PlaceFilter } from '@/components/editor/filters/placeFilter'

withDefaults(
  defineProps<{
    filter: PlaceFilter
    /** Shown entries and all entries, for the "x of y" summary. */
    shown: number
    total: number
    /** What the list holds, plural ("scenes", "characters", "items"). */
    noun: string
    showScene?: boolean
  }>(),
  { showScene: true },
)
</script>

<template>
  <div class="flex flex-wrap items-end gap-4">
    <UiField v-if="filter.hasRegions.value" label="Region" class="w-full sm:w-64">
      <UiSelect
        :model-value="filter.regionFilter.value"
        :options="filter.regionOptions.value"
        size="sm"
        @update:model-value="filter.setRegion"
      />
    </UiField>
    <UiField v-if="showScene" label="Scene" class="w-full sm:w-64">
      <UiSelect
        :model-value="filter.sceneFilter.value"
        :options="filter.sceneOptions.value"
        size="sm"
        @update:model-value="filter.setScene"
      />
    </UiField>
    <template v-if="filter.isActive.value">
      <p class="wb-hint pb-2">Showing {{ shown }} of {{ total }} {{ noun }}</p>
      <UiButton variant="ghost" size="sm" :icon="X" class="mb-0.5" @click="filter.clear()">Clear filter</UiButton>
    </template>
  </div>
</template>
