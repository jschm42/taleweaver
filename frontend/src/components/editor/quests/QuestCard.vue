<script setup lang="ts">
import { computed } from 'vue'
import { Pencil, ShieldCheck, Trash2 } from 'lucide-vue-next'
import type { Quest } from '@/composables/editor/useSideQuests'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'

/** One side quest: title, reward, description and whether the engine checks completion. */
const props = defineProps<{ quest: Quest; busy: boolean }>()

const emit = defineEmits<{ edit: []; remove: [] }>()

const hasHardRules = computed(() => {
  const q = props.quest
  return Boolean(q.required_item_id || q.required_scene_id || q.required_defeated_npc_id || q.guard_expression)
})
</script>

<template>
  <article class="flex flex-col gap-3 rounded-xl border border-wb-line bg-wb-surface p-4 transition-colors hover:border-wb-line-strong">
    <div class="flex items-start justify-between gap-3">
      <button
        type="button"
        class="wb-subheading min-w-0 rounded-md text-left hover:text-wb-accent-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
        @click="emit('edit')"
      >
        {{ quest.title || 'Untitled quest' }}
      </button>
      <UiBadge tone="accent" class="shrink-0">{{ quest.exp_reward ?? 0 }} XP</UiBadge>
    </div>
    <p class="wb-body line-clamp-3 text-wb-muted">{{ quest.description }}</p>
    <div class="mt-auto flex items-center justify-between gap-2 border-t border-wb-line pt-3">
      <UiBadge v-if="hasHardRules" tone="info">
        <ShieldCheck class="h-3 w-3" aria-hidden="true" />
        Engine-checked
      </UiBadge>
      <span v-else class="wb-hint">Judged by the Game Master</span>
      <div class="flex gap-0.5">
        <UiIconButton :icon="Pencil" label="Edit quest" size="sm" :disabled="busy" @click="emit('edit')" />
        <UiIconButton :icon="Trash2" label="Delete quest" size="sm" variant="danger" :disabled="busy" @click="emit('remove')" />
      </div>
    </div>
  </article>
</template>
