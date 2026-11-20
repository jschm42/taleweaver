<script setup lang="ts">
import { computed, type Component } from 'vue'
import { ChevronDown, ChevronUp, Code2, MapPin, Milestone, Package, Pencil, Swords, Trash2 } from 'lucide-vue-next'
import type { Chapter, ProgressionMode } from '@/composables/editor/useChapters'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'

/** One chapter in the list: number, title, goal and completion rules at a glance. */
const props = defineProps<{
  chapter: Chapter
  index: number
  count: number
  mode: ProgressionMode
  busy: boolean
}>()

const emit = defineEmits<{ edit: []; remove: []; move: [step: -1 | 1] }>()

interface RuleChip {
  icon: Component
  text: string
}

const rules = computed((): RuleChip[] => {
  const c = props.chapter
  const chips: RuleChip[] = []
  if (c.required_item_id) chips.push({ icon: Package, text: `Item ${c.required_item_id}` })
  if (c.required_scene_id) chips.push({ icon: MapPin, text: `Scene ${c.required_scene_id}` })
  if (c.required_defeated_npc_id) chips.push({ icon: Swords, text: `Defeat ${c.required_defeated_npc_id}` })
  if (c.guard_expression || c.completion_guard_expression) chips.push({ icon: Code2, text: 'Guard' })
  return chips
})
</script>

<template>
  <article class="flex gap-4 rounded-xl border border-wb-line bg-wb-surface p-4 transition-colors hover:border-wb-line-strong">
    <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-wb-line bg-wb-raised">
      <Milestone v-if="mode === 'dynamic'" class="h-4 w-4 text-wb-muted" aria-label="Dynamic chapter" />
      <span v-else class="wb-mono text-wb-strong">{{ index + 1 }}</span>
    </div>

    <div class="min-w-0 flex-1 space-y-2">
      <div class="flex flex-wrap items-center gap-2">
        <button
          type="button"
          class="wb-subheading rounded-md text-left hover:text-wb-accent-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
          @click="emit('edit')"
        >
          {{ chapter.title || 'Untitled chapter' }}
        </button>
        <UiBadge tone="accent">{{ chapter.exp_reward ?? 50 }} XP</UiBadge>
        <span class="wb-mono text-wb-faint">{{ chapter.id }}</span>
      </div>
      <p v-if="chapter.description" class="wb-body line-clamp-2 text-wb-muted">{{ chapter.description }}</p>
      <p v-if="chapter.end_condition" class="wb-hint"><span class="text-wb-body">Ends when:</span> {{ chapter.end_condition }}</p>
      <div v-if="rules.length" class="flex flex-wrap gap-1.5">
        <UiBadge v-for="rule in rules" :key="rule.text">
          <component :is="rule.icon" class="h-3 w-3" aria-hidden="true" />
          {{ rule.text }}
        </UiBadge>
      </div>
    </div>

    <div class="flex shrink-0 items-start gap-0.5">
      <template v-if="mode !== 'dynamic'">
        <UiIconButton :icon="ChevronUp" label="Move up" size="sm" :disabled="index === 0 || busy" @click="emit('move', -1)" />
        <UiIconButton :icon="ChevronDown" label="Move down" size="sm" :disabled="index === count - 1 || busy" @click="emit('move', 1)" />
      </template>
      <UiIconButton :icon="Pencil" label="Edit chapter" size="sm" :disabled="busy" @click="emit('edit')" />
      <UiIconButton :icon="Trash2" label="Delete chapter" size="sm" variant="danger" :disabled="busy" @click="emit('remove')" />
    </div>
  </article>
</template>
