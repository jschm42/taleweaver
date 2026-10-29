<script setup lang="ts">
/**
 * SheetEquipmentPanel — Core attributes and equipment slots on a body silhouette.
 */
import { computed } from 'vue'
import type { CharacterSheet, InventoryItem } from '@/types'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'
import { useBrokenImages } from './sheetItems'

const props = defineProps<{
  sheet: CharacterSheet
}>()

const emit = defineEmits<{
  unequip: [slot: string]
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
  itemContextmenu: [item: any, event: MouseEvent]
}>()

const { showImage, handleImageError } = useBrokenImages()

const equipment = computed<Record<string, InventoryItem | null>>(() => props.sheet.equipment ?? {})

const coreAttributes = computed(() => [
  { label: 'STR', value: props.sheet.strength, icon: 'ra-muscle-up', color: 'text-rose-400' },
  { label: 'DEX', value: props.sheet.dexterity, icon: 'ra-player-dodge', color: 'text-amber-400' },
  { label: 'INT', value: props.sheet.intelligence, icon: 'ra-crystal-ball', color: 'text-sky-400' },
  { label: 'WIS', value: props.sheet.wisdom, icon: 'ra-book', color: 'text-indigo-400' },
  { label: 'CHA', value: props.sheet.charisma, icon: 'ra-double-team', color: 'text-fuchsia-400' },
  { label: 'AC', value: props.sheet.armor_class, icon: 'ra-shield', color: 'text-emerald-400' },
])

// Slot badge position (% of the silhouette container) and its empty-slot icon.
const SLOTS: Record<string, { top: string; left: string; icon: string }> = {
  Head: { top: '10%', left: '50%', icon: 'ra-knight-helmet' },
  Neck: { top: '18%', left: '76%', icon: 'ra-gem-pendant' },
  Chest: { top: '30%', left: '50%', icon: 'ra-vest' },
  Arms: { top: '26%', left: '20%', icon: 'ra-muscle-up' },
  Hands: { top: '46%', left: '16%', icon: 'ra-hand' },
  MainHand: { top: '68%', left: '16%', icon: 'ra-sword' },
  Ring_1: { top: '38%', left: '82%', icon: 'ra-diamond' },
  Ring_2: { top: '54%', left: '82%', icon: 'ra-diamond' },
  OffHand: { top: '72%', left: '82%', icon: 'ra-shield' },
  Legs: { top: '64%', left: '50%', icon: 'ra-player' },
  Feet: { top: '86%', left: '50%', icon: 'ra-boot-stomp' },
}

const hoverSlot = (slot: string, event: MouseEvent) => {
  const item = equipment.value[slot]
  if (item) emit('itemHover', { ...item, entity_type: 'ITEM' }, event)
}

const contextSlot = (slot: string, event: MouseEvent) => {
  const item = equipment.value[slot]
  if (item) emit('itemContextmenu', { ...item, equipped_slot: slot, entity_type: 'ITEM' }, event)
}
</script>

<template>
  <div class="flex flex-col gap-6">
    <!-- Core RPG Attributes Strip -->
    <div v-if="props.sheet.rule_enforcement_mode === 'rpg'" class="tw-dialog-slot !border-solid p-3 sm:p-4">
      <div class="tw-panel-title tw-muted mb-2">Character Attributes</div>
      <div class="grid grid-cols-3 sm:grid-cols-6 gap-2 sm:gap-3">
        <div
          v-for="attr in coreAttributes"
          :key="attr.label"
          class="tw-card p-2 flex flex-col items-center justify-center text-center"
        >
          <div class="flex items-center gap-1.5">
            <i :class="['ra text-xs sm:text-sm', attr.icon, attr.color]"></i>
            <span class="tw-muted text-[10px] sm:text-xs font-black uppercase tracking-wider">{{ attr.label }}</span>
          </div>
          <span class="text-base sm:text-lg font-black font-mono mt-0.5">
            {{ attr.value ?? '—' }}
          </span>
        </div>
      </div>
    </div>

    <!-- Silhouette with slot badges -->
    <div class="flex flex-col items-center justify-center my-auto">
      <div class="tw-dialog-slot !border-solid relative w-full max-w-md sm:max-w-lg h-[360px] sm:h-[440px] flex items-center justify-center overflow-hidden">
        <img
          src="@/assets/svg/full-body-human-silhouette.svg"
          alt=""
          class="tw-dialog-silhouette h-full w-full object-contain"
        />

        <div
          v-for="(slotInfo, slot) in SLOTS"
          :key="slot"
          class="absolute -translate-x-1/2 -translate-y-1/2 group/slot"
          :style="{ top: slotInfo.top, left: slotInfo.left }"
          @mouseenter="hoverSlot(slot, $event)"
          @mouseleave="emit('itemLeave')"
        >
          <!-- Slot name tooltip -->
          <div class="slot-label absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 whitespace-nowrap rounded px-2 py-0.5 text-xxs font-bold uppercase tracking-wider opacity-0 group-hover/slot:opacity-100 transition-opacity z-20 pointer-events-none">
            {{ slot.replace('_', ' ') }}
          </div>

          <div
            class="tw-card w-12 h-12 sm:w-14 sm:h-14 border-2 flex items-center justify-center overflow-hidden transition-all shadow-xl"
            :class="equipment[slot] ? 'tw-dialog-slot-filled scale-105 z-10 cursor-pointer' : 'opacity-70'"
            @click="equipment[slot] && emit('unequip', slot)"
            @contextmenu.prevent="contextSlot(slot, $event)"
          >
            <template v-if="equipment[slot]">
              <div v-if="showImage(equipment[slot]!.image_url)" class="w-full h-full p-1">
                <img
                  :src="getImageUrl(equipment[slot]!.image_url)"
                  class="w-full h-full object-cover object-top rounded-lg"
                  @error="handleImageError(equipment[slot]!.image_url)"
                />
              </div>
              <i v-else :class="['ra text-base sm:text-xl', getItemIcon(equipment[slot]!.item_type), getTypeColor(equipment[slot]!.item_type)]"></i>
            </template>

            <i v-else :class="['ra text-sm sm:text-base tw-muted opacity-50 group-hover/slot:opacity-80 transition-opacity', slotInfo.icon]"></i>
          </div>
        </div>
      </div>

      <span class="tw-muted text-xxs mt-3">
        Click equipped slot to unequip · Right-click for options
      </span>
    </div>
  </div>
</template>

<style scoped>
.ra { font-family: 'rpgawesome' !important; display: inline-block; line-height: 1; text-align: center; }
.slot-label {
  background: var(--tw-tab-active-bg);
  color: var(--tw-tab-active-ink);
  border: 1px solid var(--tw-tab-active-border);
}
</style>
