<script setup lang="ts">
import { Users } from 'lucide-vue-next'
import { getImageUrl } from '@/utils/game_icons'
import InlinePromptPanel from './InlinePromptPanel.vue'
import InventoryPicker from './InventoryPicker.vue'

/**
 * Recruit dialog, shown inline at the end of the story feed (like the lock dialog of a
 * container): a companion NPC wants an item before it joins the party. The player offers one
 * inventory item (`/recruit <npc> | <item>`); only the wanted item convinces the NPC, which
 * then keeps it. A wrong item stays with the player and triggers the failure narration.
 */
defineProps<{
  open: boolean
  npcName: string
  npcImageUrl?: string | null
  hint?: string
  inventoryItems: any[]
  busy?: boolean
}>()

const emit = defineEmits<{
  close: []
  offer: [itemIds: string[]]
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
}>()
</script>

<template>
  <InlinePromptPanel
    :open="open"
    label="Recruit"
    :title="npcName"
    :image-url="getImageUrl(npcImageUrl) || null"
    :busy="busy"
    :reveal-key="npcName"
    @close="emit('close')"
  >
    <template #label-icon><Users class="w-3 h-3" /></template>

    <p v-if="hint" class="tw-prompt-description italic mb-3">“{{ hint }}”</p>
    <InventoryPicker
      v-if="open"
      :inventory-items="inventoryItems"
      :busy="busy"
      :max-select="1"
      :capacity-hint="false"
      :hint="`${npcName} wants something before joining you. Choose one item to offer.`"
      empty-hint="You carry nothing you could offer."
      action-label="Offer"
      tile-verb="Offer"
      @confirm="(ids) => emit('offer', ids)"
      @cancel="emit('close')"
      @item-hover="(item, event) => emit('itemHover', item, event)"
      @item-leave="emit('itemLeave')"
    >
      <template #action-icon><Users class="w-4 h-4" /></template>
    </InventoryPicker>
  </InlinePromptPanel>
</template>
