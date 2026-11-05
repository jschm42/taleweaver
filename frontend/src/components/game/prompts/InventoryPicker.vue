<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { Check, PackagePlus } from 'lucide-vue-next'
import PromptItemTile from './PromptItemTile.vue'

/**
 * Inventory tiles inside an inline prompt: the player selects items and confirms. Used by the
 * container panel ("Put In", `/container_put_items`) and the give panel ("Give",
 * `/give_items`). `excludeId` hides one item, e.g. the container itself.
 */
const props = withDefaults(defineProps<{
  inventoryItems: any[]
  excludeId?: string
  busy?: boolean
  /** Optional maximum number of items that can be selected at once (e.g. remaining container capacity). */
  maxSelect?: number | null
  /** Hint above the tiles. */
  hint?: string
  /** Hint when nothing can be selected. */
  emptyHint?: string
  /** Confirm button text; the selection count is appended. */
  actionLabel?: string
  /** Tooltip verb of an unselected tile ("Put in Sword", "Give Sword"). */
  tileVerb?: string
}>(), {
  excludeId: '',
  maxSelect: null,
  hint: 'Select the items to put inside.',
  emptyHint: 'You carry nothing you could put inside.',
  actionLabel: 'Put In',
  tileVerb: 'Put in',
})

const emit = defineEmits<{
  confirm: [itemIds: string[]]
  cancel: []
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
}>()

const selectedIds = ref<string[]>([])

const itemId = (item: any): string => String(item?.id || '').trim()

const candidates = computed(() => {
  const excluded = props.excludeId.trim().toLowerCase()
  return (props.inventoryItems || []).filter((item: any) => itemId(item) && itemId(item).toLowerCase() !== excluded)
})

const isSelected = (item: any) => selectedIds.value.includes(itemId(item))
const canSelectMore = computed(() => props.maxSelect == null || selectedIds.value.length < props.maxSelect)

const effectiveHint = computed(() => {
  if (props.maxSelect != null && props.maxSelect > 0) {
    return props.maxSelect === 1
      ? 'Select 1 item to put inside.'
      : `Select up to ${props.maxSelect} items to put inside.`
  }
  return props.hint
})

const toggle = (item: any) => {
  if (props.busy) return
  const id = itemId(item)
  if (!isSelected(item) && !canSelectMore.value) return
  selectedIds.value = isSelected(item)
    ? selectedIds.value.filter(selected => selected !== id)
    : [...selectedIds.value, id]
}

const confirm = () => {
  if (props.busy || !selectedIds.value.length) return
  emit('itemLeave')
  emit('confirm', [...selectedIds.value])
}

onBeforeUnmount(() => {
  emit('itemLeave')
})
</script>

<template>
  <template v-if="candidates.length">
    <p class="tw-prompt-hint">{{ effectiveHint }}</p>
    <div class="grid grid-cols-4 sm:grid-cols-6 gap-2 max-h-56 overflow-y-auto p-0.5">
      <PromptItemTile
        v-for="item in candidates"
        :key="itemId(item)"
        :item="item"
        :selected="isSelected(item)"
        :disabled="busy || (!isSelected(item) && !canSelectMore)"
        :title="isSelected(item) ? `Keep ${item.name || item.id}` : `${tileVerb} ${item.name || item.id}`"
        @click="toggle(item)"
        @mouseenter="emit('itemHover', { ...item, entity_type: 'ITEM' }, $event)"
        @mouseleave="emit('itemLeave')"
      >
        <span v-if="isSelected(item)" class="tw-prompt-tile-check"><Check class="w-3 h-3" stroke-width="3" /></span>
      </PromptItemTile>
    </div>
  </template>
  <p v-else class="tw-prompt-hint">{{ emptyHint }}</p>
  <div class="flex flex-wrap justify-end gap-2">
    <button type="button" class="tw-prompt-action tw-prompt-action--ghost" :disabled="busy" @click="emit('cancel')">
      <span>Back</span>
    </button>
    <button type="button" class="tw-prompt-action" :disabled="busy || !selectedIds.length" @click="confirm">
      <slot name="action-icon"><PackagePlus class="w-4 h-4" /></slot>
      <span>{{ selectedIds.length ? `${actionLabel} (${selectedIds.length})` : actionLabel }}</span>
    </button>
  </div>
</template>
