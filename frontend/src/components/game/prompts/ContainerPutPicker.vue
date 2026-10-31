<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, PackagePlus } from 'lucide-vue-next'
import PromptItemTile from './PromptItemTile.vue'

/**
 * Inventory tiles inside the container panel: the player selects the items to put into the
 * container (`/container_put_items <container> | A, B`). The container itself is never offered.
 */
const props = defineProps<{
  inventoryItems: any[]
  containerId: string
  busy?: boolean
}>()

const emit = defineEmits<{
  put: [itemIds: string[]]
  cancel: []
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
}>()

const selectedIds = ref<string[]>([])

const itemId = (item: any): string => String(item?.id || '').trim()

const candidates = computed(() => {
  const container = props.containerId.trim().toLowerCase()
  return (props.inventoryItems || []).filter((item: any) => itemId(item) && itemId(item).toLowerCase() !== container)
})

const isSelected = (item: any) => selectedIds.value.includes(itemId(item))

const toggle = (item: any) => {
  if (props.busy) return
  const id = itemId(item)
  selectedIds.value = isSelected(item)
    ? selectedIds.value.filter(selected => selected !== id)
    : [...selectedIds.value, id]
}

const put = () => {
  if (props.busy || !selectedIds.value.length) return
  emit('itemLeave')
  emit('put', [...selectedIds.value])
}
</script>

<template>
  <template v-if="candidates.length">
    <p class="tw-prompt-hint">Select the items to put inside.</p>
    <div class="grid grid-cols-4 sm:grid-cols-6 gap-2 max-h-56 overflow-y-auto p-0.5">
      <PromptItemTile
        v-for="item in candidates"
        :key="itemId(item)"
        :item="item"
        :selected="isSelected(item)"
        :disabled="busy"
        :title="isSelected(item) ? `Keep ${item.name || item.id}` : `Put in ${item.name || item.id}`"
        @click="toggle(item)"
        @mouseenter="emit('itemHover', { ...item, entity_type: 'ITEM' }, $event)"
        @mouseleave="emit('itemLeave')"
      >
        <span v-if="isSelected(item)" class="tw-prompt-tile-check"><Check class="w-3 h-3" stroke-width="3" /></span>
      </PromptItemTile>
    </div>
  </template>
  <p v-else class="tw-prompt-hint">You carry nothing you could put inside.</p>
  <div class="flex flex-wrap justify-end gap-2">
    <button type="button" class="tw-prompt-action tw-prompt-action--ghost" :disabled="busy" @click="emit('cancel')">
      <span>Back</span>
    </button>
    <button type="button" class="tw-prompt-action" :disabled="busy || !selectedIds.length" @click="put">
      <PackagePlus class="w-4 h-4" />
      <span>{{ selectedIds.length ? `Put In (${selectedIds.length})` : 'Put In' }}</span>
    </button>
  </div>
</template>
