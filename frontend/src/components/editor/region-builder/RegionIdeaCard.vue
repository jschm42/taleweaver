<script setup lang="ts">
/** Card 2 of the Region Builder: the region idea (stored as the region's brief). */
import { useRegionBuilderContext } from '@/composables/regionBuilder/regionBuilderContext'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const BRIEF_MAX_LENGTH = 4000

const { form } = useRegionBuilderContext()
</script>

<template>
  <UiCard v-if="form" title="Region idea" description="What should happen here: places, characters, puzzles, the mood.">
    <UiField
      label="Region idea"
      :count="form.brief.length"
      :max-length="BRIEF_MAX_LENGTH"
      hint="Plain text. Blueprint headings for regions follow in a later version."
    >
      <UiTextarea
        v-model="form.brief"
        :rows="6"
        :max-rows="20"
        :maxlength="BRIEF_MAX_LENGTH"
        placeholder="e.g. Frozen dwarven ruins above the harbor. The surveyor's trail ends at a collapsed gatehouse; an old hermit knows more…"
      />
    </UiField>
  </UiCard>
</template>
