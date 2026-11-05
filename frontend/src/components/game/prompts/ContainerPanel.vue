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
const unlockedItems = computed(() => (props.items || []).filter((item: any) => !isItemLocked(item)))
const hasUnlockedItems = computed(() => unlockedItems.value.length > 0)
const putMode = ref(false)

const isContainerSwitch = computed(() => {
  const itemType = String(props.containerEntity?.item_type || '').toUpperCase()
  if (itemType === 'CONTAINER_SWITCH') return true
  const meta = parseMetadata(props.containerEntity?.metadata_json)
  return Boolean(meta.switch && Array.isArray(meta.switch.states) && meta.switch.states.length > 0)
})

const switchConfig = computed(() => {
  const meta = parseMetadata(props.containerEntity?.metadata_json)
  return (meta.switch && typeof meta.switch === 'object') ? meta.switch : {}
})

const switchStates = computed<string[]>(() => {
  const raw = switchConfig.value.states || props.containerEntity?.switch_states
  return Array.isArray(raw) ? raw.map((s: any) => String(s || '').trim()).filter(Boolean) : []
})

const currentSwitchState = computed(() => {
  return String(
    props.containerEntity?.switch_state ||
    switchConfig.value.initial_state ||
    props.containerEntity?.switch_initial_state ||
    (switchStates.value[0] ?? '')
  ).trim().toUpperCase()
})

const isCurrentSwitchState = (state: string): boolean => state.toUpperCase() === currentSwitchState.value

function selectSwitchState(state: string): void {
  if (props.busy || isCurrentSwitchState(state)) return
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
    :label="isContainerSwitch ? 'Container · Switch' : 'Container'"
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
      :busy="busy"
      @confirm="(ids) => emit('putItems', ids)"
      @cancel="putMode = false"
      @item-hover="(item, event) => emit('itemHover', item, event)"
      @item-leave="emit('itemLeave')"
    />

    <template v-else>
      <div :class="isContainerSwitch && switchStates.length > 0 ? 'grid grid-cols-1 md:grid-cols-3 gap-3 items-start' : 'space-y-3'">
        <!-- Container Items Area -->
        <div :class="isContainerSwitch && switchStates.length > 0 ? 'md:col-span-2 space-y-2' : 'space-y-2'">
          <template v-if="hasItems">
            <p class="tw-prompt-hint">
              {{ hasUnlockedItems ? 'Click an unlocked item to take it.' : 'Items inside are currently locked.' }}
            </p>
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
            </div>
          </template>
          <p v-else class="tw-prompt-hint">This container is empty.</p>
        </div>

        <!-- Integrated Switch Control (for CONTAINER_SWITCH) -->
        <div
          v-if="isContainerSwitch && switchStates.length > 0"
          class="p-2.5 rounded-xl bg-slate-950/60 border border-white/10 space-y-2"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="text-[10px] font-black uppercase tracking-widest text-amber-300 flex items-center gap-1.5">
              <i class="ra ra-lever text-xs"></i> Switch
            </span>
            <span class="px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider border border-emerald-500/40 bg-emerald-500/15 text-emerald-300">
              {{ stateLabel(containerEntity, currentSwitchState) }}
            </span>
          </div>
          <div class="grid gap-1.5">
            <button
              v-for="state in switchStates"
              :key="state"
              type="button"
              :disabled="busy || isCurrentSwitchState(state)"
              class="tw-choice-option !py-1.5 !px-2.5 !text-xs"
              :class="{ 'is-current': isCurrentSwitchState(state) }"
              @click="selectSwitchState(state)"
            >
              <span class="tw-choice-number !w-4 !h-4">
                <Check v-if="isCurrentSwitchState(state)" class="w-2.5 h-2.5" stroke-width="3" />
                <ChevronRight v-else class="w-2.5 h-2.5" stroke-width="3" />
              </span>
              <span class="flex-1 tracking-wider text-left truncate">{{ stateLabel(containerEntity, state) }}</span>
            </button>
          </div>
        </div>
      </div>

      <div class="flex flex-wrap justify-end gap-2 pt-1">
        <button v-if="canPut" type="button" class="tw-prompt-action tw-prompt-action--ghost" :disabled="busy" @click="putMode = true">
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
