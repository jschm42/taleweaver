<script setup lang="ts">
import { computed, toRef } from 'vue'
import { Footprints } from 'lucide-vue-next'
import type { CharacterSheet, CombatState, InventoryItem } from '@/types'
import { getImageUrl, getItemIcon, getTypeColor, hasRenderableImagePath } from '@/utils/game_icons'
import { useCombatLoadout } from './useCombatLoadout'

const props = defineProps<{
  combat: CombatState
  playerSheet: CharacterSheet | null
  consumables: InventoryItem[]
  locked: boolean
}>()

const emit = defineEmits<{
  consume: [name: string]
  rest: []
  run: []
  hover: [entity: Record<string, unknown>, event: MouseEvent]
  leave: []
}>()

const { resources, weapon } = useCombatLoadout(toRef(props, 'combat'), toRef(props, 'playerSheet'))
const restHighlighted = computed(() => resources.value.stamina < weapon.value.cost)

function consumableTooltip(item: InventoryItem): Record<string, unknown> {
  return { ...item, entity_type: 'ITEM', description: (item.description as string) || 'A consumable that can be used during combat.' }
}
</script>

<template>
  <div class="flex flex-col sm:flex-row gap-3 items-stretch">
    <div class="tw-item-tray flex-1 min-w-0" role="toolbar" aria-label="Items">
      <span class="tw-combat-eyebrow shrink-0 self-center [writing-mode:vertical-rl] rotate-180 hidden sm:block">Items</span>
      <button
        v-for="item in consumables"
        :key="item.id || item.name"
        type="button"
        class="tw-item-tile"
        :disabled="locked"
        @click="emit('consume', item.name)"
        @mouseenter="emit('hover', consumableTooltip(item), $event)"
        @mousemove="emit('hover', consumableTooltip(item), $event)"
        @mouseleave="emit('leave')"
      >
        <span class="tw-item-tile-art">
          <img v-if="hasRenderableImagePath(item.image_url as string)" :src="getImageUrl(item.image_url as string)" class="w-full h-full object-cover" :alt="item.name">
          <i v-else :class="['ra text-2xl', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
        </span>
        <span class="block w-full text-[11px] font-bold leading-tight truncate">{{ item.name }}</span>
      </button>
      <span v-if="consumables.length === 0" class="text-xs italic self-center opacity-60">No usable items.</span>
    </div>

    <div class="grid grid-cols-2 sm:grid-cols-1 sm:w-40 gap-2 content-center">
      <button
        type="button"
        class="tw-dialog-button tw-dialog-button--ghost !py-2.5"
        :class="{ 'tw-combat-rest-hint': restHighlighted }"
        :disabled="locked"
        @click="emit('rest')"
      >
        <i class="ra ra-hourglass"></i> Rest <span class="text-[10px] font-mono opacity-70 normal-case">+40 STA</span>
      </button>
      <button
        type="button"
        class="tw-dialog-button tw-dialog-button--ghost !py-2.5"
        :disabled="locked"
        @click="emit('run')"
      >
        <Footprints class="w-4 h-4" /> Flee
      </button>
    </div>
  </div>
</template>
