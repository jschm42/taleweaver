<script setup lang="ts">
import { Eye, User } from 'lucide-vue-next'
import type { CombatEnemyState } from '@/types'
import { getImageUrl, hasRenderableImagePath } from '@/utils/game_icons'

defineProps<{
  bystanders: CombatEnemyState[]
  selectedTargetId: string | null
}>()

const emit = defineEmits<{
  select: [id: string]
  hover: [id: string, event: MouseEvent]
  leave: []
}>()

function portrait(raw: string | null | undefined): string | null {
  return hasRenderableImagePath(raw) ? getImageUrl(raw as string) : null
}
</script>

<template>
  <details class="tw-combat-panel shrink-0 p-3 group">
    <summary class="tw-combat-eyebrow cursor-pointer select-none flex items-center justify-between gap-2">
      <span>Bystanders ({{ bystanders.length }})</span>
      <Eye class="w-3.5 h-3.5 opacity-60 group-open:opacity-100" />
    </summary>
    <p class="text-[11px] opacity-70 mt-2 mb-2">
      Not part of this fight. Attacking one pulls it, and its allies, into the battle.
    </p>
    <ul class="space-y-1.5 max-h-36 overflow-y-auto pr-1">
      <li v-for="npc in bystanders" :key="npc.id">
        <button
          type="button"
          class="tw-combat-loot-row w-full text-left"
          :class="{ 'ring-1 ring-rose-400/70': npc.id === selectedTargetId }"
          :aria-pressed="npc.id === selectedTargetId"
          :title="`Choose ${npc.name} as target`"
          @click="emit('select', npc.id)"
          @mouseenter="emit('hover', npc.id, $event)"
          @mousemove="emit('hover', npc.id, $event)"
          @mouseleave="emit('leave')"
        >
          <span class="flex items-center gap-2 min-w-0">
            <img
              v-if="portrait(npc.image_url)"
              :src="portrait(npc.image_url) as string"
              :alt="npc.name"
              class="w-6 h-6 rounded-full object-cover shrink-0"
            />
            <User v-else class="w-4 h-4 shrink-0 opacity-70" />
            <span class="text-sm truncate">{{ npc.name }}</span>
          </span>
          <span class="text-[10px] uppercase tracking-wider opacity-70 shrink-0">
            {{ npc.id === selectedTargetId ? 'Target' : 'Pick' }}
          </span>
        </button>
      </li>
    </ul>
  </details>
</template>
