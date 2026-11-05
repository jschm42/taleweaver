<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Backpack, PackageOpen, PackagePlus, ArrowDownToLine, Lock, Check, ChevronRight } from 'lucide-vue-next'
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

const hasItems = computed(() => (props.items || []).length > 0)
const currentCount = computed(() => (props.items || []).length)
const unlockedItems = computed(() => (props.items || []).filter((item: any) => !isItemLocked(item)))
const hasUnlockedItems = computed(() => unlockedItems.value.length > 0)
const putMode = ref(false)

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

const remainingCapacity = computed<number | null>(() => {
  if (maxItems.value === null) return null
  return Math.max(0, maxItems.value - currentCount.value)
})

const isContainerFull = computed(() => remainingCapacity.value !== null && remainingCapacity.value <= 0)
const belowMinItems = computed(() => minItems.value !== null && currentCount.value < minItems.value)
const slotCount = computed<number>(() => maxItems.value ?? minItems.value ?? 0)
const emptySlotCount = computed<number>(() => Math.max(0, slotCount.value - currentCount.value))

const switchStatusText = computed<string>(() => {
  return String(
    props.containerEntity?.switch_status_text ??
    switchConfig.value.status_text ??
    ''
  ).trim()
})

const capacityBadgeText = computed(() => {
  if (minItems.value !== null && maxItems.value !== null) {
    if (minItems.value === maxItems.value) {
      return `${currentCount.value} / ${maxItems.value} required`
    }
    return `${currentCount.value} / ${maxItems.value} (min ${minItems.value})`
  }
  if (maxItems.value !== null) {
    return `${currentCount.value} / ${maxItems.value} slots`
  }
  if (minItems.value !== null) {
    return `${currentCount.value} items (min ${minItems.value})`
  }
  return ''
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
    label="Container"
    :title="title"
    :image-url="resolvedImageUrl"
    :busy="busy"
    :reveal-key="title"
    @close="emit('close')"
  >
    <template #label-icon><PackageOpen class="w-3 h-3" /></template>

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
        class="text-xs text-amber-200/90 bg-amber-500/10 border border-amber-500/25 rounded-lg px-3 py-2 mb-3 leading-snug"
      >
        {{ switchStatusText }}
      </p>
      <div :class="isContainerSwitch && switchStates.length > 0 ? 'flex flex-col md:flex-row gap-4 items-start' : 'space-y-3'">
        <!-- Container Items Area -->
        <div :class="isContainerSwitch && switchStates.length > 0 ? 'flex-1 min-w-0 w-full space-y-2' : 'space-y-2'">
          <div class="flex items-center justify-between gap-2">
            <p class="tw-prompt-hint">
              <template v-if="hasItems">
                {{ hasUnlockedItems ? 'Click an unlocked item to take it.' : 'Items inside are currently locked.' }}
              </template>
              <template v-else-if="emptySlotCount > 0">
                Click an empty slot or Put In to insert items.
              </template>
              <template v-else>This container is empty.</template>
            </p>
            <span
              v-if="capacityBadgeText"
              class="shrink-0 text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-md border"
              :class="belowMinItems ? 'border-amber-500/30 bg-amber-500/10 text-amber-300' : 'border-white/10 bg-white/5 opacity-75'"
            >
              {{ capacityBadgeText }}
            </span>
          </div>
          <template v-if="hasItems || emptySlotCount > 0">
            <div class="grid grid-cols-3 sm:grid-cols-5 gap-2 max-h-56 overflow-y-auto p-0.5">
              <button
                v-for="item in items"
                :key="itemKey(item)"
                type="button"
                :disabled="busy || isItemLocked(item)"
                class="tw-prompt-tile relative"
                :class="isItemLocked(item) ? 'border-amber-500/40 opacity-80 cursor-not-allowed' : ''"
                :title="isItemLocked(item) ? `${item.name || item.id} (Locked — cannot be taken right now)` : `Take ${item.name || item.id}`"
                @click="takeItem(item)"
                @mouseenter="emit('itemHover', { ...item, entity_type: 'ITEM' }, $event)"
                @mouseleave="emit('itemLeave')"
              >
                <span
                  v-if="isItemLocked(item)"
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
              <button
                v-for="slotIdx in emptySlotCount"
                :key="`empty-slot-${slotIdx}`"
                type="button"
                :disabled="busy || !canPut || isContainerFull"
                class="tw-prompt-tile border-dashed border-amber-500/30 bg-black/20 hover:border-amber-500/60 hover:bg-amber-500/5 transition-all"
                :class="(!canPut || isContainerFull) ? 'opacity-50 cursor-default' : 'cursor-pointer'"
                :title="canPut && !isContainerFull ? `Empty Slot ${currentCount + slotIdx} — Click to insert item` : `Empty Slot ${currentCount + slotIdx}`"
                @click="canPut && !busy && !isContainerFull ? (putMode = true) : undefined"
              >
                <PackagePlus class="w-5 h-5 text-amber-400/45" />
                <span class="tw-prompt-tile-caption opacity-55">Slot {{ currentCount + slotIdx }}</span>
              </button>
            </div>
          </template>
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

      <div class="flex flex-wrap justify-end gap-2 pt-1">
        <button
          v-if="canPut"
          type="button"
          class="tw-prompt-action tw-prompt-action--ghost"
          :disabled="busy || isContainerFull"
          :title="isContainerFull ? 'Container is full' : 'Put items inside'"
          @click="putMode = true"
        >
          <PackagePlus class="w-4 h-4" />
          <span>Put In</span>
        </button>
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
    </template>
  </InlinePromptPanel>
</template>
