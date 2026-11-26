<script setup lang="ts">
/**
 * Card 5 of the Region Builder: the adventure's global settings a region inherits and cannot
 * change (spec 4.3), each with a link to the editor page that changes it.
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useEditor } from '@/composables/editor/editorContext'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiDisclosure from '@/components/ui/UiDisclosure.vue'

const editor = useEditor()
const router = useRouter()

const RULE_MODES: Record<string, string> = { rpg: 'RPG', story: 'Story', strict: 'Story', chat: 'Chat' }

function nameOf(value: unknown): string {
  if (typeof value === 'string') return value
  if (!value || typeof value !== 'object') return ''
  const entry = value as Record<string, unknown>
  return String(entry.name || entry.label || entry.id || '')
}

const rows = computed(() => {
  const adv = (editor.adventure || {}) as Record<string, unknown>
  const styles = Array.isArray(adv.selected_image_styles) ? adv.selected_image_styles : []
  return [
    { label: 'Language', value: String(adv.language || 'English'), page: 'world' },
    { label: 'Play style', value: RULE_MODES[String(adv.rule_enforcement_mode || 'story')] || 'Story', page: 'world' },
    { label: 'Time per turn', value: adv.time_per_turn ? `${adv.time_per_turn} min` : 'Default', page: 'time' },
    { label: 'Image style', value: nameOf(styles[0]) || 'None', page: 'visuals' },
    { label: 'Tone', value: nameOf(adv.selected_tone) || 'None', page: 'tone' },
    { label: 'Narrator persona', value: nameOf(adv.narrator_voice) || 'Default', page: 'tone' },
  ]
})

function open(page: string): void {
  void router.push({ name: 'adventure-editor', params: { adventureId: editor.adventureId }, query: { tab: page } })
}
</script>

<template>
  <UiCard title="Inherited from the adventure" description="Regions share these settings with the rest of the world.">
    <UiDisclosure label="Show the settings">
      <dl class="divide-y divide-wb-line">
        <div v-for="row in rows" :key="row.label" class="flex flex-wrap items-center justify-between gap-3 py-2">
          <dt class="wb-label">{{ row.label }}</dt>
          <dd class="flex items-center gap-2 wb-body text-wb-strong">
            {{ row.value }}
            <UiButton size="sm" variant="ghost" @click="open(row.page)">Change</UiButton>
          </dd>
        </div>
      </dl>
    </UiDisclosure>
  </UiCard>
</template>
