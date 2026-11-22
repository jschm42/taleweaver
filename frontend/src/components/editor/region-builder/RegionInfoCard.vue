<script setup lang="ts">
/**
 * Card 1 of the Region Builder: name and description of the region (saved with the region list
 * when the build starts) and its links to neighbouring regions (edited on the Regions map).
 */
import { computed } from 'vue'
import { useRegionBuilderContext } from '@/composables/regionBuilder/regionBuilderContext'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const { form, section, sections } = useRegionBuilderContext()

function travelText(minutes: number | null): string {
  if (!minutes) return ''
  if (minutes < 60) return `${minutes} min`
  return `${Math.round((minutes / 60) * 10) / 10} h`
}

const links = computed(() =>
  (section.value?.planned_links || []).map((link) => {
    const target = sections.value.find((s) => s.id === link.to_section_id)
    return {
      id: link.to_section_id,
      label: target?.label || link.to_section_id,
      built: target?.status === 'built',
      travel: travelText(link.travel_minutes),
    }
  }),
)
</script>

<template>
  <UiCard v-if="form" title="Region" description="Name and description are saved with the region when the build starts.">
    <div class="space-y-4">
      <UiField label="Name" required>
        <UiInput v-model="form.label" placeholder="e.g. Gloom Peaks" />
      </UiField>
      <UiField label="Description" hint="What the region is like; the World-Builder reads it next to the region idea.">
        <UiTextarea v-model="form.description" :rows="3" :max-rows="8" />
      </UiField>
      <div>
        <p class="wb-label">Links to other regions</p>
        <ul v-if="links.length" class="mt-2 space-y-1.5">
          <li v-for="link in links" :key="link.id" class="flex flex-wrap items-center gap-2 wb-body">
            <span class="text-wb-strong">{{ link.label }}</span>
            <UiBadge :tone="link.built ? 'accent' : 'neutral'">{{ link.built ? 'built' : 'planned' }}</UiBadge>
            <span v-if="link.travel" class="wb-hint">{{ link.travel }} travel</span>
          </li>
        </ul>
        <p class="wb-hint mt-1">
          {{
            links.length
              ? 'Exits to built regions start at their gateway scenes.'
              : 'No links: the region is connected to a fitting existing scene.'
          }}
          Links are drawn on the Regions page map.
        </p>
      </div>
    </div>
  </UiCard>
</template>
