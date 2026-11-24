<script setup lang="ts">
/**
 * Fields of one region in the Regions page draft. Planned regions also get the author's brief
 * and their planned links (routes to neighbours that have no exits yet). Description and brief
 * can be written by the World-Builder (RegionTextGenerate) into the draft.
 */
import { computed } from 'vue'
import { Plus, Trash2, Users } from 'lucide-vue-next'
import type { PlannedLink, WorldSection } from '@/services/sectionService'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'
import RegionTextGenerate from '@/components/editor/regions/RegionTextGenerate.vue'

const section = defineModel<WorldSection>({ required: true })

const props = defineProps<{
  adventureId: string
  others: WorldSection[]
  sceneCount: number
}>()

const emit = defineEmits<{
  (e: 'assign-scenes'): void
  (e: 'delete'): void
}>()

const STATUS_OPTIONS = [
  { value: 'built', label: 'Built' },
  { value: 'stub', label: 'Planned' },
]

const isGenerating = computed(() => section.value.status === 'generating')
const isPlanned = computed(() => section.value.status !== 'built')
const allSections = computed(() => [section.value, ...props.others])
const linkTargets = computed(() => props.others.map((s) => ({ value: s.id, label: s.label })))

const status = computed<string>({
  get: () => section.value.status,
  set: (value) => {
    section.value.status = value === 'stub' ? 'stub' : 'built'
  },
})

function linkHours(link: PlannedLink): number | null {
  return link.travel_minutes ? Math.round((link.travel_minutes / 60) * 10) / 10 : null
}

function setLinkHours(link: PlannedLink, hours: string | number | null): void {
  const value = Number(hours)
  link.travel_minutes = Number.isFinite(value) && value > 0 ? Math.round(value * 60) : null
}

function addLink(): void {
  const used = new Set(section.value.planned_links.map((l) => l.to_section_id))
  const target = props.others.find((s) => !used.has(s.id))
  if (!target) return
  section.value.planned_links.push({ to_section_id: target.id, travel_minutes: null, note: '' })
}

function removeLink(index: number): void {
  section.value.planned_links.splice(index, 1)
}
</script>

<template>
  <div class="space-y-4">
    <UiNotice v-if="isGenerating" tone="ai" title="Build in progress">
      Editing is locked while the World-Builder is building this region.
    </UiNotice>
    <fieldset :disabled="isGenerating" class="space-y-4 disabled:opacity-60">
      <div class="grid gap-4 md:grid-cols-2">
        <UiField label="Name" hint="Shown to the player on the world map.">
          <UiInput v-model="section.label" />
        </UiField>
        <UiField
          label="Status"
          info="Built regions hold scenes and appear in play. Planned regions have no scenes yet and stay hidden from players until you build them."
        >
          <UiBadge v-if="sceneCount > 0" tone="accent">Built (has scenes)</UiBadge>
          <UiSegmented v-else v-model="status" :options="STATUS_OPTIONS" label="Region status" :disabled="isGenerating" />
        </UiField>
      </div>
      <UiField label="Description" hint="One paragraph; the Game Master sees it while the player is in this region.">
        <UiTextarea v-model="section.description" :rows="3" />
      </UiField>
      <RegionTextGenerate
        :adventure-id="adventureId"
        field="description"
        :section="section"
        :sections="allSections"
        @generated="section.description = $event"
      />

      <div v-if="isPlanned" class="space-y-4">
        <UiField label="Brief" hint="Your directions for building this region later.">
          <UiTextarea v-model="section.brief" :rows="2" />
        </UiField>
        <RegionTextGenerate
          :adventure-id="adventureId"
          field="brief"
          :section="section"
          :sections="allSections"
          @generated="section.brief = $event"
        />
        <div class="space-y-2">
          <p class="wb-label">Planned routes</p>
          <div v-for="(link, index) in section.planned_links" :key="index" class="grid gap-2 md:grid-cols-[1fr_8rem_auto] items-end">
            <UiField label="To region">
              <UiSelect v-model="link.to_section_id" :options="linkTargets" size="sm" />
            </UiField>
            <UiField label="Travel (hours)">
              <UiInput :model-value="linkHours(link)" type="number" size="sm" @update:model-value="setLinkHours(link, $event)" />
            </UiField>
            <UiIconButton :icon="Trash2" label="Remove route" variant="danger" @click="removeLink(index)" />
          </div>
          <UiButton :icon="Plus" size="sm" variant="ghost" :disabled="section.planned_links.length >= others.length" @click="addLink">
            Add route
          </UiButton>
        </div>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-2 border-t border-wb-line pt-4">
        <span class="wb-hint">{{ sceneCount }} scene(s) in this region</span>
        <div class="flex gap-2">
          <UiButton :icon="Users" size="sm" @click="emit('assign-scenes')">Choose scenes</UiButton>
          <UiButton :icon="Trash2" size="sm" variant="danger" @click="emit('delete')">Delete region</UiButton>
        </div>
      </div>
    </fieldset>
  </div>
</template>
