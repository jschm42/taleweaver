<script setup lang="ts">
/**
 * CharacterSheetModal — The hero dialog: identity, vitals and tabs for the hero profile,
 * inventory, equipment, status effects and special attacks. Styled by the session's
 * dialog skin (it is teleported out of the immersive root, so it carries its own .tw-skin).
 */
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import StatBar from './StatBar.vue'
import SheetSpecialsPanel from './SheetSpecialsPanel.vue'
import SheetHeroPanel from './sheet/SheetHeroPanel.vue'
import SheetInventoryPanel from './sheet/SheetInventoryPanel.vue'
import SheetEquipmentPanel from './sheet/SheetEquipmentPanel.vue'
import SheetStatusPanel from './sheet/SheetStatusPanel.vue'
import { isEquippable, isReadableItem } from './sheet/sheetItems'
import type { SheetTabId } from './sheet/types'
import type { CharacterSheet } from '@/types'
import { useSheetSkin } from '@/skins/useSheetSkin'

const props = defineProps<{
  open: boolean
  sheet: CharacterSheet | null
  isDebug?: boolean
  /** Tab shown when the dialog opens; without it the last viewed tab stays active. */
  initialTab?: SheetTabId | null
}>()

const emit = defineEmits<{
  close: []
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
  equip: [name: string]
  unequip: [slot: string]
  consume: [name: string]
  openContainer: [item: any]
  readItem: [item: any]
  changed: []
  itemContextmenu: [item: any, event: MouseEvent]
  inspectItem: [item: any]
  flipSwitch: [item: any]
}>()

type TabType = SheetTabId

type TabDefinition = {
  id: TabType
  icon: string
  label: string
  shortLabel: string
  count: string
  alert?: boolean
}

const activeTab = ref<TabType>('hero')

watch(
  () => props.open,
  (open) => {
    if (!open || !props.initialTab) return
    activeTab.value = props.initialTab
  }
)
const stateChanged = ref(false)

const { activeSkin, skinStyle } = useSheetSkin(() => props.sheet)

const inventoryList = computed(() => props.sheet?.inventory ?? [])
const statusEffects = computed(() => props.sheet?.status_effects ?? [])
const showVitals = computed(() => props.sheet?.rule_enforcement_mode !== 'chat')
const showMana = computed(() => props.sheet?.rule_enforcement_mode === 'rpg')

const equippedCount = computed(() => Object.values(props.sheet?.equipment ?? {}).filter((item) => !!item).length)

const unlockedSpecialCount = computed(() => {
  const unlocked = new Set(props.sheet?.unlocked_actions ?? [])
  return (props.sheet?.special_actions ?? []).filter((a) => unlocked.has(a.id)).length
})

const tabs = computed<TabDefinition[]>(() => [
  { id: 'hero', icon: 'ra-player', label: 'Hero', shortLabel: 'Hero', count: '' },
  { id: 'inventory', icon: 'ra-backpack', label: 'Inventory', shortLabel: 'Bag', count: `${inventoryList.value.length}/24` },
  { id: 'equipment', icon: 'ra-vest', label: 'Equipped', shortLabel: 'Gear', count: `${equippedCount.value}/11` },
  {
    id: 'ailments',
    icon: 'ra-aura',
    label: 'Ailments & Buffs',
    shortLabel: 'Status',
    count: String(statusEffects.value.length),
    alert: statusEffects.value.length > 0,
  },
  { id: 'specials', icon: 'ra-crystal-wand', label: 'Specials', shortLabel: 'Skills', count: String(unlockedSpecialCount.value) },
])

const handleInventoryClick = (item: any) => {
  if (isReadableItem(item)) {
    emit('readItem', item)
    return
  }
  const itemType = String(item.item_type || '').toUpperCase()
  if (itemType === 'CONTAINER') {
    emit('openContainer', item)
    return
  }
  // A carried switch (e.g. a remote) opens the same state picker as in the scene.
  if (itemType === 'SWITCH') {
    emit('flipSwitch', item)
    return
  }
  if (itemType === 'CONSUMABLE') {
    stateChanged.value = true
    emit('consume', item.name)
    return
  }
  if (isEquippable(item)) {
    stateChanged.value = true
    emit('equip', item.name)
    return
  }
  // Everything else is looked at, which also fires the item's on_interact triggers.
  emit('inspectItem', item)
}

const handleUnequip = (slot: string) => {
  stateChanged.value = true
  emit('unequip', slot)
}

const onClose = () => {
  if (stateChanged.value) {
    emit('changed')
    stateChanged.value = false
  }
  emit('close')
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.open) {
    onClose()
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[150] bg-slate-950/90 backdrop-blur-md flex items-center justify-center p-2 sm:p-4"
        @click.self="onClose"
      >
        <div
          v-if="sheet"
          class="tw-skin tw-dialog w-full max-w-4xl h-[94vh] sm:h-[90vh] md:h-[86vh] flex flex-col relative animate-sheet-in overflow-hidden"
          :data-skin="activeSkin"
          :style="skinStyle"
          role="dialog"
          aria-modal="true"
          :aria-label="`Character sheet: ${sheet.name || 'Unnamed'}`"
        >
          <!-- TOP HEADER: Identity & Vitals -->
          <div class="tw-dialog-header shrink-0 p-3 sm:p-4 md:p-5 flex flex-col gap-2.5 sm:gap-3">
            <div class="flex items-center justify-between gap-2.5 sm:gap-3">
              <button
                type="button"
                class="min-w-0 text-left"
                title="View hero profile"
                @click="activeTab = 'hero'"
              >
                <span class="min-w-0 flex flex-col">
                  <span class="flex items-center gap-1.5 sm:gap-2 flex-wrap">
                    <span class="tw-dialog-title text-base sm:text-xl md:text-2xl truncate">
                      {{ sheet.name || 'Unnamed' }}
                    </span>
                    <span v-if="sheet.adventure_version" class="tw-dialog-chip">v{{ sheet.adventure_version }}</span>
                  </span>
                  <span class="tw-dialog-eyebrow text-[11px] sm:text-xs mt-0.5 truncate">
                    {{ sheet.role || 'Adventurer' }}
                  </span>
                </span>
              </button>

              <div class="flex items-center gap-3 sm:gap-4 shrink-0">
                <div v-if="showVitals" class="hidden md:block min-w-[240px]">
                  <StatBar label="HP" :value="sheet.hp" :max="sheet.max_hp" color="crimson" size="xs" />
                  <StatBar label="STA" :value="sheet.stamina" :max="sheet.max_stamina" color="emerald" size="xs" />
                  <StatBar v-if="showMana" label="MP" :value="sheet.mana" :max="sheet.max_mana" color="sapphire" size="xs" />
                </div>

                <button
                  type="button"
                  class="tw-dialog-icon-button p-2 sm:p-2.5"
                  title="Close Character Sheet (Esc)"
                  aria-label="Close"
                  @click="onClose"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>

            <!-- Mobile Vitals -->
            <div v-if="showVitals" class="tw-dialog-divider md:hidden grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1 border-t">
              <StatBar label="HP" :value="sheet.hp" :max="sheet.max_hp" color="crimson" size="xs" />
              <StatBar label="STA" :value="sheet.stamina" :max="sheet.max_stamina" color="emerald" size="xs" />
              <StatBar v-if="showMana" label="MP" :value="sheet.mana" :max="sheet.max_mana" color="sapphire" size="xs" />
            </div>
          </div>

          <!-- TAB SWITCHER -->
          <div class="tw-dialog-divider shrink-0 px-2.5 sm:px-6 pt-2.5 sm:pt-4 pb-2.5 border-b">
            <div class="flex items-center gap-1 sm:gap-2" role="tablist">
              <button
                v-for="tab in tabs"
                :key="tab.id"
                type="button"
                role="tab"
                :aria-selected="activeTab === tab.id"
                class="tw-tab !px-1.5 sm:!px-3"
                :class="{ 'tw-tab--active': activeTab === tab.id }"
                @click="activeTab = tab.id"
              >
                <i :class="['ra text-xs sm:text-base', tab.icon]"></i>
                <span class="hidden md:inline truncate">{{ tab.label }}</span>
                <span class="md:hidden truncate">{{ tab.shortLabel }}</span>
                <span v-if="tab.count" class="tw-tab-count hidden sm:inline-block">{{ tab.count }}</span>
                <span v-if="tab.alert" class="tw-tab-dot"></span>
              </button>
            </div>
          </div>

          <!-- TAB CONTENT BODY -->
          <div class="flex-grow overflow-y-auto custom-scrollbar p-3.5 sm:p-6 min-h-0">
            <SheetHeroPanel v-if="activeTab === 'hero'" :sheet="sheet" />

            <SheetInventoryPanel
              v-else-if="activeTab === 'inventory'"
              :items="inventoryList"
              :is-debug="isDebug"
              @activate="handleInventoryClick"
              @item-hover="(item, event) => emit('itemHover', item, event)"
              @item-leave="emit('itemLeave')"
              @item-contextmenu="(item, event) => emit('itemContextmenu', item, event)"
            />

            <SheetEquipmentPanel
              v-else-if="activeTab === 'equipment'"
              :sheet="sheet"
              @unequip="handleUnequip"
              @item-hover="(item, event) => emit('itemHover', item, event)"
              @item-leave="emit('itemLeave')"
              @item-contextmenu="(item, event) => emit('itemContextmenu', item, event)"
            />

            <SheetStatusPanel v-else-if="activeTab === 'ailments'" :effects="statusEffects" />

            <SheetSpecialsPanel v-else-if="activeTab === 'specials'" :sheet="sheet" :is-debug="isDebug" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
@keyframes sheetIn {
  from { opacity: 0; transform: scale(0.95) translateY(20px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
.animate-sheet-in { animation: sheetIn 0.35s cubic-bezier(0.16, 1, 0.3, 1); }
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.1); }
.custom-scrollbar::-webkit-scrollbar-thumb { background: color-mix(in srgb, var(--tw-panel-ink) 25%, transparent); border-radius: 4px; }
.ra { font-family: 'rpgawesome' !important; display: inline-block; line-height: 1; text-align: center; }
</style>
