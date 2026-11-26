<script setup lang="ts">
/**
 * Card 2 of the Region Builder: the region idea (stored as the region's brief). Free text, or a
 * blueprint in region mode; the preview reports its blocks and issues (spec 6).
 */
import { computed } from 'vue'
import { useRegionBuilderContext } from '@/composables/regionBuilder/regionBuilderContext'
import BlueprintSyntaxHelp from '@/components/create-adventure/BlueprintSyntaxHelp.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInfoPopover from '@/components/ui/UiInfoPopover.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const BRIEF_MAX_LENGTH = 20000

const KIND_LABELS: Record<string, [string, string]> = {
  scene: ['scene', 'scenes'],
  exit: ['exit', 'exits'],
  npc: ['character', 'characters'],
  item: ['item', 'items'],
  sequence: ['chapter', 'chapters'],
  script: ['script', 'scripts'],
  sidequest: ['side quest', 'side quests'],
  award: ['award', 'awards'],
}

function kindText(kind: string, count: number): string {
  const [one, many] = KIND_LABELS[kind] || [kind, kind]
  return `${count} ${count === 1 ? one : many}`
}

const { form, preview } = useRegionBuilderContext()

const report = computed(() => preview.value?.blueprint || null)
const errors = computed(() => (report.value?.issues || []).filter((i) => i.severity === 'error'))
const warnings = computed(() => (report.value?.issues || []).filter((i) => i.severity === 'warning'))
const kinds = computed(() =>
  Object.entries(report.value?.kinds || {}).map(([kind, count]) => kindText(kind, count)),
)
</script>

<template>
  <UiCard v-if="form" title="Region idea" description="What should happen here: places, characters, puzzles, the mood.">
    <div class="space-y-3">
      <UiField
        label="Region idea"
        :count="form.brief.length"
        :max-length="BRIEF_MAX_LENGTH"
        :error="errors.length ? 'The blueprint has errors; see below.' : null"
        hint="Optional blueprint headings pin the region's scenes, characters, exits and chapters."
      >
        <UiTextarea
          v-model="form.brief"
          :rows="6"
          :max-rows="24"
          :maxlength="BRIEF_MAX_LENGTH"
          :invalid="errors.length > 0"
          placeholder="e.g. Frozen dwarven ruins above the harbor. The surveyor's trail ends at a collapsed gatehouse; an old hermit knows more…"
        />
      </UiField>
      <div class="flex flex-wrap items-center gap-2">
        <span class="wb-hint">Blueprint syntax</span>
        <UiInfoPopover title="Blueprint syntax" wide>
          <BlueprintSyntaxHelp />
          <p class="wb-hint mt-3">
            In a region, World, Protagonist and Audio blocks are global and ignored. Existing ids may be referenced
            (exits from existing scenes, keys), never declared again. Chapters start at 1 and follow the existing ones.
          </p>
        </UiInfoPopover>
        <UiBadge v-if="kinds.length" tone="info">Blueprint: {{ kinds.join(', ') }}</UiBadge>
      </div>
      <UiNotice v-if="errors.length" tone="danger" title="Blueprint errors">
        <ul class="list-disc space-y-1 pl-5">
          <li v-for="issue in errors" :key="`e-${issue.line}-${issue.message}`">Line {{ issue.line }}: {{ issue.message }}</li>
        </ul>
      </UiNotice>
      <UiNotice v-if="warnings.length" tone="warn" title="Blueprint notes">
        <ul class="list-disc space-y-1 pl-5">
          <li v-for="issue in warnings" :key="`w-${issue.line}-${issue.message}`">Line {{ issue.line }}: {{ issue.message }}</li>
        </ul>
      </UiNotice>
    </div>
  </UiCard>
</template>
