<script setup lang="ts">
import { Gift } from 'lucide-vue-next'
import { getImageUrl } from '@/utils/game_icons'
import InlinePromptPanel from './InlinePromptPanel.vue'
import InventoryPicker from './InventoryPicker.vue'

/**
 * Give dialog, shown inline at the end of the story feed: the player selects inventory items
 * and hands them to an NPC (`/give_items <npc> | A, B`). The NPC's on_receive_item trigger
 * fires once for the whole batch, then the Game Master narrates the NPC's reaction.
 */
defineProps<{
  open: boolean
  npcName: string
  npcImageUrl?: string | null
  inventoryItems: any[]
  busy?: boolean
}>()

const emit = defineEmits<{
  close: []
  give: [itemIds: string[]]
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
}>()
</script>

<template>
  <InlinePromptPanel
    :open="open"
    label="Give"
    :title="npcName"
    :image-url="getImageUrl(npcImageUrl) || null"
    :busy="busy"
    :reveal-key="npcName"
    @close="emit('close')"
  >
    <template #label-icon><Gift class="w-3 h-3" /></template>

    <InventoryPicker
      v-if="open"
      :inventory-items="inventoryItems"
      :busy="busy"
      :hint="`Select the items to give to ${npcName}.`"
      empty-hint="You carry nothing you could give."
      action-label="Give"
      tile-verb="Give"
      @confirm="(ids) => emit('give', ids)"
      @cancel="emit('close')"
      @item-hover="(item, event) => emit('itemHover', item, event)"
      @item-leave="emit('itemLeave')"
    >
      <template #action-icon><Gift class="w-4 h-4" /></template>
    </InventoryPicker>
  </InlinePromptPanel>
</template>
