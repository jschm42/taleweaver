<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Backpack, PackagePlus, ArrowDownToLine, Lock, Check, ChevronRight } from 'lucide-vue-next'
import { getItemIcon, getTypeColor, getImageUrl, hasRenderableImagePath } from '@/utils/game_icons'
import InlinePromptPanel from './InlinePromptPanel.vue'
import InventoryPicker from './InventoryPicker.vue'
import { parseMetadata } from './promptUtils'
import { stateLabel } from '../immersive/switchState'

/**
 * Contents of an opened container, shown inline at the end of the story feed. With "Put In" the
 * panel switches to the player's inventory, so items can be stored in the container.
 * For CONTAINER_SWITCH items, the switch control is rendered integrated next to the container items.
 */
const props = defineProps<{
  open: boolean
  title: string
  items: any[]
  imageUrl?: string | null
  busy?: boolean
  containerId?: string
  containerEntity?: any
  inventoryItems?: any[]
  /** Only containers standing in the scene accept items. */
  canPut?: boolean
}>()

const emit = defineEmits<{
  close: []
  takeAll: []
  takeItem: [item: any]
  dropToScene: []
  putItems: [itemIds: string[]]
  selectSwitchState: [targetState: string]
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
}>()

const isItemLocked = (item: any): boolean => {
  if (!item) return false
  if (typeof item.locked === 'boolean') return item.locked
  return Boolean(item.metadata_json?.locked === true)
}

const lockedItems = computed(() => (props.items || []).filter((item: any) => isItemLocked(item)))
const unlockedItems = computed(() => (props.items || []).filter((item: any) => !isItemLocked(item)))
const hasLockedItems = computed(() => lockedItems.value.length > 0)
const hasUnlockedItems = computed(() => unlockedItems.value.length > 0)
const hasItems = computed(() => (props.items || []).length > 0)
const currentCount = computed(() => (props.items || []).length)
const putMode = ref(false)

// Tracks item IDs that are or were locked in this container to preserve their slot assignments
const assignedLockedItemIds = ref<Set<string>>(new Set())

watch(
  () => props.items,
  (newItems) => {
    for (const item of newItems || []) {
      if (isItemLocked(item)) {
        const id = String(item.id || item.name || '').trim()
        if (id) assignedLockedItemIds.value.add(id)
      }
    }
  },
  { immediate: true, deep: true }
)

watch(
  () => props.containerId,
  () => {
    assignedLockedItemIds.value.clear()
    for (const item of props.items || []) {
      if (isItemLocked(item)) {
        const id = String(item.id || item.name || '').trim()
        if (id) assignedLockedItemIds.value.add(id)
      }
    }
  }
)

const lockedSlotCount = computed(() => Math.max(lockedItems.value.length, assignedLockedItemIds.value.size))

const containerMeta = computed(() => parseMetadata(props.containerEntity?.metadata_json))

const minItems = computed<number | null>(() => {
  const raw = props.containerEntity?.min_items ?? containerMeta.value.min_items
  const num = Number(raw)
  return Number.isFinite(num) && num > 0 ? Math.floor(num) : null
})

const maxItems = computed<number | null>(() => {
  const raw = props.containerEntity?.max_items ?? containerMeta.value.max_items
  const num = Number(raw)
  return Number.isFinite(num) && num > 0 ? Math.floor(num) : null
})

// Input slot capacity only covers slots not assigned to locked items
const inputSlotCapacity = computed<number | null>(() => {
  if (maxItems.value === null) return null
  return Math.max(0, maxItems.value - lockedSlotCount.value)
})

const emptyInputSlotCount = computed<number>(() => {
  if (inputSlotCapacity.value === null) {
    if (minItems.value !== null) {
      return Math.max(0, (minItems.value - lockedSlotCount.value) - unlockedItems.value.length)
    }
    return 0
  }
  return Math.max(0, inputSlotCapacity.value - unlockedItems.value.length)
})

const remainingCapacity = computed<number | null>(() => {
  if (inputSlotCapacity.value === null) return null
  return Math.max(0, inputSlotCapacity.value - unlockedItems.value.length)
})

const isContainerFull = computed(() => remainingCapacity.value !== null && remainingCapacity.value <= 0)
const belowMinItems = computed(() => minItems.value !== null && currentCount.value < minItems.value)

const inputSlotNumber = (slotIdx: number): number => {
  return lockedSlotCount.value + unlockedItems.value.length + slotIdx
}

const switchStatusText = computed<string>(() => {
  return String(
    props.containerEntity?.switch_status_text ??
    switchConfig.value.status_text ??
    ''
  ).trim()
})

const isContainerSwitch = computed(() => {
  const itemType = String(props.containerEntity?.item_type || '').toUpperCase()
  if (itemType === 'CONTAINER_SWITCH') return true
  return Boolean(containerMeta.value.switch && Array.isArray(containerMeta.value.switch.states) && containerMeta.value.switch.states.length > 0)
})

const switchConfig = computed(() => {
  return (containerMeta.value.switch && typeof containerMeta.value.switch === 'object') ? containerMeta.value.switch : {}
})

const switchStates = computed<string[]>(() => {
  const raw = switchConfig.value.states || props.containerEntity?.switch_states
  return Array.isArray(raw) ? raw.map((s: any) => String(s || '').trim()).filter(Boolean) : []
})

const initialSwitchState = computed(() => {
  return String(
    switchConfig.value.initial_state ||
    props.containerEntity?.switch_initial_state ||
    (switchStates.value[0] ?? '')
  ).trim().toUpperCase()
})

const currentSwitchState = computed(() => {
  return String(
    props.containerEntity?.switch_state ||
    initialSwitchState.value
  ).trim().toUpperCase()
})

const isCurrentSwitchState = (state: string): boolean => state.toUpperCase() === currentSwitchState.value

const disabledSwitchStates = computed<Set<string>>(() => {
  const raw =
    props.containerEntity?.disabled_switch_states ??
    switchConfig.value.disabled_states ??
    props.containerEntity?.switch_disabled_states ??
    []
  return new Set(
    Array.isArray(raw) ? raw.map((s: any) => String(s || '').trim().toUpperCase()).filter(Boolean) : []
  )
})

const isStateDisabled = (state: string): boolean => {
  const normalized = state.toUpperCase()
  if (disabledSwitchStates.value.has(normalized)) return true
  if (belowMinItems.value && normalized !== initialSwitchState.value) return true
  return false
}

function selectSwitchState(state: string): void {
  if (props.busy || isCurrentSwitchState(state) || isStateDisabled(state)) return
  emit('selectSwitchState', state.toUpperCase())
}

watch(() => [props.open, props.title], () => { putMode.value = false })

watch(() => props.items, () => {
  emit('itemLeave')
}, { deep: true })

watch(() => props.open, (isOpen) => {
  if (!isOpen) {
    emit('itemLeave')
  }
})

onBeforeUnmount(() => {
  emit('itemLeave')
})
const resolvedImageUrl = computed(() => getImageUrl(props.imageUrl) || null)

const brokenImages = ref<Record<string, boolean>>({})

function itemKey(item: any): string {
  return String(item.id || item.name || 'unknown-item')
}

function onItemImageError(item: any): void {
  brokenImages.value[itemKey(item)] = true
}

function canShowImage(item: any): boolean {
  return hasRenderableImagePath(item.image_url) && !brokenImages.value[itemKey(item)]
}

function takeItem(item: any): void {
  if (props.busy || isItemLocked(item)) return
  emit('itemLeave')
  emit('takeItem', item)
}
</script>

<template>
  <InlinePromptPanel
    :open="open"
    :title="title"
    :image-url="resolvedImageUrl"
    :busy="busy"
    :reveal-key="title"
    @close="emit('close')"
  >

    <InventoryPicker
      v-if="putMode"
      :inventory-items="inventoryItems || []"
      :exclude-id="containerId || ''"
      :max-select="remainingCapacity"
      :busy="busy"
      @confirm="(ids) => { putMode = false; emit('putItems', ids) }"
      @cancel="putMode = false"
      @item-hover="(item, event) => emit('itemHover', item, event)"
      @item-leave="emit('itemLeave')"
    />

    <template v-else>
      <p
        v-if="switchStatusText"
        class="text-sm italic text-amber-100/90 leading-snug mb-3"
      >
        {{ switchStatusText }}
      </p>
      <div :class="isContainerSwitch && switchStates.length > 0 ? 'flex flex-col md:flex-row gap-4 items-start' : 'space-y-3'">
        <!-- Container Items Area -->
        <div :class="isContainerSwitch && switchStates.length > 0 ? 'flex-1 min-w-0 w-full space-y-3' : 'space-y-3'">
          <!-- Locked Items Row -->
          <div v-if="hasLockedItems" class="space-y-1.5 pb-1">
            <span class="text-[11px] font-semibold uppercase tracking-wider text-amber-500/80">
              Locked Items
            </span>
            <div class="grid grid-cols-3 sm:grid-cols-5 gap-2 max-h-40 overflow-y-auto p-0.5">
              <button
                v-for="item in lockedItems"
                :key="itemKey(item)"
                type="button"
                :disabled="busy || true"
                class="tw-prompt-tile relative border-amber-500/40 opacity-80 cursor-not-allowed"
                :title="`${item.name || item.id} (Locked — cannot be taken right now)`"
                @mouseenter="emit('itemHover', { ...item, entity_type: 'ITEM' }, $event)"
                @mouseleave="emit('itemLeave')"
              >
                <span
                  class="absolute top-1 right-1 z-10 p-1 rounded-md bg-amber-500/25 border border-amber-500/50 text-amber-300 shadow"
                  title="Locked"
                >
                  <Lock class="w-3 h-3" />
                </span>
                <img
                  v-if="canShowImage(item)"
                  :src="getImageUrl(item.image_url)"
                  class="w-full h-full object-cover object-top"
                  :alt="item.name || 'container item'"
                  @error="onItemImageError(item)"
                />
                <i v-else :class="['ra text-2xl', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
                <span class="tw-prompt-tile-caption">{{ item.name || item.id }}</span>
              </button>
            </div>
          </div>

          <!-- Interactive Slots Row (Unlocked Items & Input Slots) -->
          <div class="space-y-1.5">
            <p class="tw-prompt-hint">
              <template v-if="hasUnlockedItems">
                Click an unlocked item to take it.
              </template>
              <template v-else-if="emptyInputSlotCount > 0">
                Click an empty slot or Put In to insert items.
              </template>
              <template v-else-if="!hasLockedItems">
                This container is empty.
              </template>
            </p>
            <template v-if="hasUnlockedItems || emptyInputSlotCount > 0">
              <div class="grid grid-cols-3 sm:grid-cols-5 gap-2 max-h-56 overflow-y-auto p-0.5">
                <button
                  v-for="item in unlockedItems"
                  :key="itemKey(item)"
                  type="button"
                  :disabled="busy"
                  class="tw-prompt-tile relative"
                  :title="`Take ${item.name || item.id}`"
                  @click="takeItem(item)"
                  @mouseenter="emit('itemHover', { ...item, entity_type: 'ITEM' }, $event)"
                  @mouseleave="emit('itemLeave')"
                >
                  <img
                    v-if="canShowImage(item)"
                    :src="getImageUrl(item.image_url)"
                    class="w-full h-full object-cover object-top"
                    :alt="item.name || 'container item'"
                    @error="onItemImageError(item)"
                  />
                  <i v-else :class="['ra text-2xl', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
                  <span class="tw-prompt-tile-caption">{{ item.name || item.id }}</span>
                </button>
                <button
                  v-for="slotIdx in emptyInputSlotCount"
                  :key="`empty-slot-${slotIdx}`"
                  type="button"
                  :disabled="busy || !canPut || isContainerFull"
                  class="tw-prompt-tile border-dashed border-amber-500/30 bg-black/20 hover:border-amber-500/60 hover:bg-amber-500/5 transition-all"
                  :class="(!canPut || isContainerFull) ? 'opacity-50 cursor-default' : 'cursor-pointer'"
                  :title="canPut && !isContainerFull ? `Empty Slot ${inputSlotNumber(slotIdx)} — Click to insert item` : `Empty Slot ${inputSlotNumber(slotIdx)}`"
                  @click="canPut && !busy && !isContainerFull ? (putMode = true) : undefined"
                  @mouseenter="emit('itemLeave')"
                  @mouseleave="emit('itemLeave')"
                >
                  <PackagePlus class="w-5 h-5 text-amber-400/45" />
                  <span class="tw-prompt-tile-caption opacity-55">Slot {{ inputSlotNumber(slotIdx) }}</span>
                </button>
              </div>
            </template>
          </div>
        </div>

        <!-- Integrated Switch Control (for CONTAINER_SWITCH) -->
        <div
          v-if="isContainerSwitch && switchStates.length > 0"
          class="w-full md:w-52 shrink-0 grid gap-2 md:pr-2"
        >
          <button
            v-for="state in switchStates"
            :key="state"
            type="button"
            :disabled="busy || isCurrentSwitchState(state) || isStateDisabled(state)"
            class="tw-choice-option"
            :class="{
              'is-current': isCurrentSwitchState(state),
              'opacity-45 cursor-not-allowed': isStateDisabled(state) && !isCurrentSwitchState(state),
            }"
            :title="isStateDisabled(state) ? `${stateLabel(containerEntity, state)} (Locked)` : stateLabel(containerEntity, state)"
            @click="selectSwitchState(state)"
          >
            <span class="tw-choice-number">
              <Check v-if="isCurrentSwitchState(state)" class="w-3 h-3" stroke-width="3" />
              <Lock v-else-if="isStateDisabled(state)" class="w-3 h-3" />
              <ChevronRight v-else class="w-3 h-3" stroke-width="3" />
            </span>
            <span class="flex-1 tracking-wider text-left truncate">{{ stateLabel(containerEntity, state) }}</span>
          </button>
        </div>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-3 pt-2">
        <div>
          <button
            v-if="canPut"
            type="button"
            class="tw-prompt-action tw-prompt-action--ghost !text-xs sm:!text-sm !py-2.5 !px-5 font-bold tracking-wider"
            :disabled="busy || isContainerFull"
            :title="isContainerFull ? 'Container is full' : 'Put items inside'"
            @click="putMode = true"
          >
            <span>Put In</span>
          </button>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <button
            v-if="hasUnlockedItems"
            type="button"
            class="tw-prompt-action tw-prompt-action--ghost"
            :disabled="busy"
            @click="emit('dropToScene')"
          >
            <ArrowDownToLine class="w-4 h-4" />
            <span>Drop To Scene</span>
          </button>
          <button
            v-if="hasUnlockedItems"
            type="button"
            class="tw-prompt-action"
            :disabled="busy"
            @click="emit('takeAll')"
          >
            <Backpack class="w-4 h-4" />
            <span>Take All</span>
          </button>
        </div>
      </div>
    </template>
  </InlinePromptPanel>
</template>
