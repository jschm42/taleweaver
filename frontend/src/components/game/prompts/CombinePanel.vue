<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Combine, X } from 'lucide-vue-next'
import InlinePromptPanel from './InlinePromptPanel.vue'
import PromptItemTile from './PromptItemTile.vue'

/**
 * Combine workbench, shown inline at the end of the story feed. The player puts items from the
 * inventory or the scene on it and presses Combine; the engine then checks deterministically
 * whether they are exactly the ingredients of a CONSTRUCTABLE recipe (`/craft A | B`).
 */
const props = defineProps<{
  open: boolean
  /** Item the panel was opened from; it starts on the workbench. */
  seedItem: any
  inventoryItems: any[]
  sceneItems: any[]
  busy?: boolean
}>()

const emit = defineEmits<{
  close: []
  combine: [itemIds: string[]]
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
}>()

const MIN_INGREDIENTS = 2

const selectedIds = ref<string[]>([])

const itemId = (item: any): string => String(item?.id || '').trim()

const inventoryCandidates = computed(() => (props.inventoryItems || []).filter((item: any) => itemId(item)))
const sceneCandidates = computed(() => {
  const carried = new Set(inventoryCandidates.value.map(itemId))
  return (props.sceneItems || []).filter((item: any) => itemId(item) && !carried.has(itemId(item)))
})
const candidatesById = computed(() => {
  const all = [...inventoryCandidates.value, ...sceneCandidates.value]
  return new Map(all.map((item: any) => [itemId(item), item]))
})

const selectedItems = computed(() => selectedIds.value.map(id => candidatesById.value.get(id)).filter(Boolean))
const isSelected = (item: any) => selectedIds.value.includes(itemId(item))
const canCombine = computed(() => selectedItems.value.length >= MIN_INGREDIENTS && !props.busy)

const toggle = (item: any) => {
  if (props.busy) return
  const id = itemId(item)
  selectedIds.value = isSelected(item)
    ? selectedIds.value.filter(selected => selected !== id)
    : [...selectedIds.value, id]
}

/** Set while a Combine attempt is out; a miss leaves the ingredients in place. */
const combinePending = ref(false)

const combine = () => {
  if (!canCombine.value) return
  emit('itemLeave')
  combinePending.value = true
  emit('combine', [...selectedIds.value])
}

const onRevealed = () => {
  combinePending.value = false
  const seed = itemId(props.seedItem)
  selectedIds.value = seed ? [seed] : []
}

// Used-up ingredients vanish from inventory and scene: after a Combine that means it worked,
// so the workbench closes. Otherwise they just drop off the workbench.
watch(candidatesById, (candidates) => {
  const remaining = selectedIds.value.filter(id => candidates.has(id))
  const consumed = remaining.length < selectedIds.value.length
  selectedIds.value = remaining
  if (!consumed || !combinePending.value) return
  combinePending.value = false
  emit('itemLeave')
  emit('close')
})
</script>

<template>
  <InlinePromptPanel
    :open="open"
    label="Combine"
    title="Workbench"
    description="Put items from your inventory or your surroundings together and try to combine them."
    :busy="busy"
    :reveal-key="itemId(seedItem)"
    @close="emit('close')"
    @revealed="onRevealed"
  >
    <template #label-icon><Combine class="w-3 h-3" /></template>

    <!-- Workbench slots -->
    <div class="tw-prompt-bench">
      <PromptItemTile
        v-for="item in selectedItems"
        :key="itemId(item)"
        :item="item"
        selected
        large
        :disabled="busy"
        :title="`Remove ${item.name || item.id}`"
        @click="toggle(item)"
        @mouseenter="emit('itemHover', { ...item, entity_type: 'ITEM' }, $event)"
        @mouseleave="emit('itemLeave')"
      >
        <span class="tw-prompt-tile-check"><X class="w-3 h-3" stroke-width="3" /></span>
      </PromptItemTile>
      <span v-for="n in Math.max(0, MIN_INGREDIENTS - selectedItems.length)" :key="`empty-${n}`" class="tw-prompt-slot">+</span>
    </div>

    <!-- Candidates: inventory first, then the scene -->
    <div v-for="group in [{ label: 'Inventory', items: inventoryCandidates }, { label: 'Here', items: sceneCandidates }]" :key="group.label">
      <template v-if="group.items.length">
        <p class="tw-prompt-group">{{ group.label }}</p>
        <div class="grid grid-cols-5 sm:grid-cols-8 gap-2 max-h-44 overflow-y-auto p-0.5">
          <PromptItemTile
            v-for="item in group.items"
            :key="itemId(item)"
            :item="item"
            :dimmed="isSelected(item)"
            :disabled="busy"
            :title="isSelected(item) ? `Remove ${item.name || item.id}` : `Add ${item.name || item.id}`"
            @click="toggle(item)"
            @mouseenter="emit('itemHover', { ...item, entity_type: 'ITEM' }, $event)"
            @mouseleave="emit('itemLeave')"
          />
        </div>
      </template>
    </div>

    <div class="flex items-center justify-between gap-3">
      <p class="tw-prompt-hint">
        {{ selectedItems.length < MIN_INGREDIENTS ? `Choose at least ${MIN_INGREDIENTS} items.` : `${selectedItems.length} items on the workbench.` }}
      </p>
      <button type="button" class="tw-prompt-action shrink-0" :disabled="!canCombine" @click="combine">
        <i v-if="busy" class="ra ra-hourglass animate-spin"></i>
        <Combine v-else class="w-4 h-4" />
        <span>Combine</span>
      </button>
    </div>
  </InlinePromptPanel>
</template>
