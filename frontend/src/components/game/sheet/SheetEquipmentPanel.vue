<script setup lang="ts">
/**
 * SheetEquipmentPanel — Core attributes and equipment slots on a body silhouette,
 * with an interactive equipment slot picker modal for equipping and unequipping.
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import type { InventoryItem } from '@/types'
import type { EquipmentSheet } from './types'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'
import { useBrokenImages } from './sheetItems'

const props = defineProps<{
  sheet: EquipmentSheet
}>()

const emit = defineEmits<{
  equip: [name: string, slot?: string]
  unequip: [slot: string]
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
  itemContextmenu: [item: any, event: MouseEvent]
}>()

const { showImage, handleImageError } = useBrokenImages()

const selectedSlot = ref<string | null>(null)

const equipment = computed<Record<string, InventoryItem | null>>(() => props.sheet.equipment ?? {})
const inventory = computed<InventoryItem[]>(() => props.sheet.inventory ?? [])

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

function isItemMatchingSlot(item: any, slot: string): boolean {
  if (!item) return false
  const norm = (s: string) => String(s || '').toLowerCase().replace(/_/g, '')
  const targetNorm = norm(slot)

  // 1. Wearable slots list or string
  const wearables: string[] = Array.isArray(item.wearable_slots)
    ? item.wearable_slots
    : typeof item.wearable_slots === 'string'
      ? [item.wearable_slots]
      : []

  for (const w of wearables) {
    const wNorm = norm(w)
    if (wNorm === targetNorm) return true
    if (targetNorm.startsWith('ring') && wNorm.startsWith('ring')) return true
    if (targetNorm === 'hands' && (wNorm === 'hand' || wNorm === 'hands')) return true
  }

  // 2. Explicit slot field
  if (item.slot) {
    const sNorm = norm(item.slot)
    if (sNorm === targetNorm) return true
    if (targetNorm.startsWith('ring') && sNorm.startsWith('ring')) return true
    if (targetNorm === 'hands' && (sNorm === 'hand' || sNorm === 'hands')) return true
  }

  // 3. Weapons fit MainHand or OffHand
  const itemType = String(item.item_type || item.metadata_json?.item_type || '').toUpperCase()
  if (itemType === 'WEAPON') {
    if (slot === 'MainHand' || slot === 'OffHand') return true
  }

  // 4. Tools/Shields into OffHand
  if (slot === 'OffHand') {
    const name = String(item.name || '').toLowerCase()
    if (name.includes('shield') || name.includes('buckler') || name.includes('torch')) return true
  }

  return false
}

const matchingInventoryItems = computed(() => {
  if (!selectedSlot.value) return []
  return inventory.value.filter((item) => isItemMatchingSlot(item, selectedSlot.value!))
})

function getItemStatsBadges(item: any): string[] {
  const badges: string[] = []
  if (item.damage_dice) badges.push(`${item.damage_dice} dmg`)
  const mods: Record<string, string> = {
    stat_modifier_strength: 'STR',
    stat_modifier_dexterity: 'DEX',
    stat_modifier_intelligence: 'INT',
    stat_modifier_wisdom: 'WIS',
    stat_modifier_charisma: 'CHA',
    stat_modifier_armor_class: 'AC',
  }
  for (const [key, label] of Object.entries(mods)) {
    const val = Number(item[key])
    if (val) badges.push(`${val > 0 ? '+' : ''}${val} ${label}`)
  }
  if (item.hp_change) badges.push(`${item.hp_change > 0 ? '+' : ''}${item.hp_change} HP`)
  return badges
}

const onEquipClick = (itemName: string, slot: string) => {
  emit('equip', itemName, slot)
  selectedSlot.value = null
}

const onUnequipClick = (slot: string) => {
  emit('unequip', slot)
  selectedSlot.value = null
}

const hoverSlot = (slot: string, event: MouseEvent) => {
  const item = equipment.value[slot]
  if (item) emit('itemHover', { ...item, entity_type: 'ITEM' }, event)
}

const contextSlot = (slot: string, event: MouseEvent) => {
  const item = equipment.value[slot]
  if (item) emit('itemContextmenu', { ...item, equipped_slot: slot, entity_type: 'ITEM' }, event)
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && selectedSlot.value) {
    selectedSlot.value = null
    e.stopPropagation()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div class="flex flex-col gap-6 relative">
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
            class="tw-card w-12 h-12 sm:w-14 sm:h-14 border-2 flex items-center justify-center overflow-hidden transition-all shadow-xl cursor-pointer"
            :class="equipment[slot] ? 'tw-dialog-slot-filled scale-105 z-10' : 'opacity-70 hover:opacity-100 hover:border-amber-400/60'"
            @click="selectedSlot = slot"
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
        Click slot to equip or unequip items · Right-click for options
      </span>
    </div>

    <!-- Equipment Slot Picker Modal -->
    <div
      v-if="selectedSlot"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      @click.self="selectedSlot = null"
    >
      <div
        class="tw-dialog w-full max-w-lg max-h-[85vh] flex flex-col p-4 sm:p-5 shadow-2xl relative"
        role="dialog"
        aria-modal="true"
      >
        <!-- Header -->
        <div class="flex items-center justify-between pb-3 border-b border-white/10 mb-4">
          <div class="flex items-center gap-2.5">
            <div class="w-9 h-9 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <i :class="['ra text-lg', SLOTS[selectedSlot]?.icon || 'ra-vest']"></i>
            </div>
            <div>
              <h3 class="text-sm sm:text-base font-bold text-white tracking-wide">
                {{ selectedSlot.replace('_', ' ') }} Equipment
              </h3>
              <p class="text-xxs tw-muted">
                {{ equipment[selectedSlot] ? 'Change or remove equipped item' : 'Choose an item from your backpack' }}
              </p>
            </div>
          </div>
          <button
            type="button"
            class="tw-dialog-icon-button p-1.5"
            title="Close (Esc)"
            @click="selectedSlot = null"
          >
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>

        <!-- Currently Equipped Item (if any) -->
        <div v-if="equipment[selectedSlot]" class="mb-4">
          <div class="text-[10px] font-bold uppercase tracking-wider text-amber-400/90 mb-1.5 flex items-center gap-1">
            <i class="ra ra-vest text-xs"></i>
            Currently Equipped
          </div>
          <div class="tw-card p-3 flex items-center justify-between gap-3 border-amber-500/30 bg-amber-500/5">
            <div class="flex items-center gap-3 min-w-0">
              <div class="w-12 h-12 rounded-lg border border-white/10 overflow-hidden shrink-0 flex items-center justify-center bg-black/40">
                <img
                  v-if="showImage(equipment[selectedSlot]!.image_url)"
                  :src="getImageUrl(equipment[selectedSlot]!.image_url)"
                  class="w-full h-full object-cover"
                  @error="handleImageError(equipment[selectedSlot]!.image_url)"
                />
                <i v-else :class="['ra text-xl', getItemIcon(equipment[selectedSlot]!.item_type), getTypeColor(equipment[selectedSlot]!.item_type)]"></i>
              </div>
              <div class="min-w-0">
                <div class="text-xs font-bold text-white truncate">{{ equipment[selectedSlot]!.name }}</div>
                <div class="flex flex-wrap gap-1 mt-1">
                  <span
                    v-for="badge in getItemStatsBadges(equipment[selectedSlot]!)"
                    :key="badge"
                    class="text-[9px] px-1.5 py-0.5 rounded bg-black/40 border border-white/10 text-amber-300 font-mono"
                  >
                    {{ badge }}
                  </span>
                </div>
              </div>
            </div>
            <button
              type="button"
              class="tw-dialog-button tw-dialog-button--ghost shrink-0 text-rose-300 hover:text-rose-200 hover:border-rose-400"
              @click="onUnequipClick(selectedSlot)"
            >
              Unequip
            </button>
          </div>
        </div>

        <!-- Available Inventory Items -->
        <div class="flex-grow flex flex-col min-h-0">
          <div class="text-[10px] font-bold uppercase tracking-wider tw-muted mb-2 flex items-center justify-between">
            <span class="flex items-center gap-1">
              <i class="ra ra-backpack text-xs"></i>
              Available in Backpack
            </span>
            <span class="text-xxs">({{ matchingInventoryItems.length }})</span>
          </div>

          <div v-if="matchingInventoryItems.length > 0" class="overflow-y-auto custom-scrollbar flex flex-col gap-2 pr-1 max-h-[38vh]">
            <div
              v-for="item in matchingInventoryItems"
              :key="item.id || item.name"
              class="tw-card p-2.5 flex items-center justify-between gap-3 hover:border-amber-400/50 cursor-pointer transition-all hover:bg-white/5 group"
              @click="onEquipClick(item.name, selectedSlot)"
            >
              <div class="flex items-center gap-3 min-w-0">
                <div class="w-11 h-11 rounded-lg border border-white/10 overflow-hidden shrink-0 flex items-center justify-center bg-black/40">
                  <img
                    v-if="showImage(item.image_url)"
                    :src="getImageUrl(item.image_url)"
                    class="w-full h-full object-cover"
                    @error="handleImageError(item.image_url)"
                  />
                  <i v-else :class="['ra text-lg', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
                </div>
                <div class="min-w-0">
                  <div class="text-xs font-bold text-white group-hover:text-amber-300 transition-colors truncate">
                    {{ item.name }}
                  </div>
                  <div class="flex flex-wrap gap-1 mt-0.5">
                    <span
                      v-for="badge in getItemStatsBadges(item)"
                      :key="badge"
                      class="text-[9px] px-1.5 py-0.5 rounded bg-black/40 border border-white/10 text-slate-300 font-mono"
                    >
                      {{ badge }}
                    </span>
                  </div>
                </div>
              </div>
              <button
                type="button"
                class="tw-dialog-button shrink-0 py-1 px-3 text-[10px]"
              >
                Equip
              </button>
            </div>
          </div>

          <div v-else class="flex flex-col items-center justify-center p-6 text-center my-auto">
            <i :class="['ra text-2xl tw-muted opacity-40 mb-2', SLOTS[selectedSlot]?.icon || 'ra-vest']"></i>
            <p class="text-xs font-semibold text-slate-400">No matching items in your backpack.</p>
            <p class="text-xxs tw-muted mt-1">Find or craft items matching the {{ selectedSlot.replace('_', ' ') }} slot.</p>
          </div>
        </div>
      </div>
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
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.1); }
.custom-scrollbar::-webkit-scrollbar-thumb { background: color-mix(in srgb, var(--tw-panel-ink) 25%, transparent); border-radius: 4px; }
</style>
