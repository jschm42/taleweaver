<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import StatBar from './StatBar.vue'
import type { CharacterSheet, InventoryItem } from '@/types'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'

const props = defineProps<{
  open: boolean
  sheet: CharacterSheet | null
  isDebug?: boolean
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
}>()

type TabType = 'inventory' | 'equipment' | 'ailments'
const activeTab = ref<TabType>('inventory')
const showBio = ref(false)
const brokenImages = ref<Record<string, boolean>>({})
const stateChanged = ref(false)

const inventoryList = computed(() => props.sheet?.inventory ?? [])
const equipment = computed<Record<string, InventoryItem | null>>(() => props.sheet?.equipment ?? {})
const statusEffects = computed(() => props.sheet?.status_effects ?? [])

const equippedCount = computed(() => {
  return Object.values(equipment.value).filter(item => !!item).length
})

const coreAttributes = computed(() => {
  if (!props.sheet) return []
  return [
    { label: 'STR', name: 'Strength', value: props.sheet.strength, icon: 'ra-muscle-up', color: 'text-rose-400' },
    { label: 'DEX', name: 'Dexterity', value: props.sheet.dexterity, icon: 'ra-fast-forward', color: 'text-amber-400' },
    { label: 'INT', name: 'Intelligence', value: props.sheet.intelligence, icon: 'ra-brain', color: 'text-sky-400' },
    { label: 'WIS', name: 'Wisdom', value: props.sheet.wisdom, icon: 'ra-book', color: 'text-indigo-400' },
    { label: 'CHA', name: 'Charisma', value: props.sheet.charisma, icon: 'ra-double-team', color: 'text-fuchsia-400' },
    { label: 'AC', name: 'Armor Class', value: props.sheet.armor_class, icon: 'ra-shield', color: 'text-emerald-400' }
  ]
})

const SLOTS_LIST = [
  { key: 'Head', label: 'Head', icon: 'ra-helmet' },
  { key: 'Neck', label: 'Neck', icon: 'ra-necklace' },
  { key: 'Chest', label: 'Chest', icon: 'ra-breastplate' },
  { key: 'Arms', label: 'Arms', icon: 'ra-hand' },
  { key: 'Hands', label: 'Hands', icon: 'ra-hand' },
  { key: 'Ring_1', label: 'Ring 1', icon: 'ra-ring' },
  { key: 'Ring_2', label: 'Ring 2', icon: 'ra-ring' },
  { key: 'MainHand', label: 'Main Hand', icon: 'ra-sword' },
  { key: 'OffHand', label: 'Off Hand', icon: 'ra-shield' },
  { key: 'Legs', label: 'Legs', icon: 'ra-leg' },
  { key: 'Feet', label: 'Feet', icon: 'ra-boot-prints' }
]

// Silhouette slot coordinates (% of silhouette container)
const slotPositions: Record<string, { top: string, left: string }> = {
  'Head': { top: '10%', left: '50%' },
  'Neck': { top: '18%', left: '76%' },
  'Chest': { top: '30%', left: '50%' },
  'Arms': { top: '26%', left: '20%' },
  'Hands': { top: '46%', left: '16%' },
  'MainHand': { top: '68%', left: '16%' },
  'Ring_1': { top: '38%', left: '82%' },
  'Ring_2': { top: '54%', left: '82%' },
  'OffHand': { top: '72%', left: '82%' },
  'Legs': { top: '64%', left: '50%' },
  'Feet': { top: '86%', left: '50%' }
}

const getSlotPlaceholderIcon = (slot: string) => {
  const match = SLOTS_LIST.find(s => s.key === slot)
  return match?.icon || 'ra-help'
}

const handleImageError = (path?: string | null) => {
  if (!path) return
  brokenImages.value[path] = true
}

const showImage = (path?: string | null) => {
  return !!path && !brokenImages.value[path]
}

const isInteractable = (item: any) => {
  if (!item) return false
  const isEquippable = !!item.slot || (item.wearable_slots && item.wearable_slots.length > 0)
  return isEquippable || item.item_type === 'CONSUMABLE' || String(item.item_type || '').toUpperCase() === 'CONTAINER' || String(item.item_type || '').toUpperCase() === 'READABLE'
}

const handleInventoryClick = (item: any) => {
  if (!item) return
  const isEquippable = !!item.slot || (item.wearable_slots && item.wearable_slots.length > 0)
  
  if (isEquippable) {
    stateChanged.value = true
    emit('equip', item.name)
  } else if (item.item_type === 'CONSUMABLE') {
    stateChanged.value = true
    emit('consume', item.name)
  } else if (String(item.item_type || '').toUpperCase() === 'CONTAINER') {
    emit('openContainer', item)
  } else if (String(item.item_type || '').toUpperCase() === 'READABLE') {
    emit('readItem', item)
  }
}

const handleUnequip = (slot: string) => {
  stateChanged.value = true
  emit('unequip', slot)
}

const isPositiveEffect = (effectName: string): boolean => {
  const name = effectName.toLowerCase()
  const positiveKeywords = ['bless', 'boost', 'strength', 'regen', 'shield', 'grace', 'haste', 'focus', 'sharp', 'vitality', 'aura', 'vigor', 'protect', 'might']
  return positiveKeywords.some(kw => name.includes(kw))
}

const getStatusIcon = (effectName: string): string => {
  const name = effectName.toLowerCase()
  if (name.includes('poison') || name.includes('venom')) return 'ra-poison-cloud'
  if (name.includes('bleed') || name.includes('wound')) return 'ra-bleeding-hearts'
  if (name.includes('burn') || name.includes('fire')) return 'ra-burning-embers'
  if (name.includes('freeze') || name.includes('frost') || name.includes('chill')) return 'ra-frost-fire'
  if (name.includes('curse')) return 'ra-skull'
  if (name.includes('blind') || name.includes('dark')) return 'ra-eyeball'
  if (name.includes('stun') || name.includes('daze') || name.includes('paralyz')) return 'ra-lightning-trio'
  if (name.includes('fatigue') || name.includes('exhaust') || name.includes('tired')) return 'ra-droplet'
  if (name.includes('bless') || name.includes('holy')) return 'ra-sun'
  if (name.includes('shield') || name.includes('armor') || name.includes('protect')) return 'ra-shield'
  if (name.includes('haste') || name.includes('speed') || name.includes('quick')) return 'ra-fast-forward'
  if (name.includes('strength') || name.includes('might') || name.includes('rage')) return 'ra-muscle-up'
  return isPositiveEffect(effectName) ? 'ra-aura' : 'ra-heart-burn'
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.open) {
    if (showBio.value) {
      showBio.value = false
    } else {
      onClose()
    }
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

const onClose = () => {
  if (stateChanged.value) {
    emit('changed')
    stateChanged.value = false
  }
  showBio.value = false
  emit('close')
}
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
          class="w-full max-w-4xl h-[94vh] sm:h-[90vh] md:h-[86vh] flex flex-col bg-slate-900 border border-slate-800 rounded-2xl sm:rounded-3xl shadow-[0_0_80px_rgba(0,0,0,0.85)] relative animate-sheet-in overflow-hidden"
          v-if="sheet"
        >
          
          <!-- TOP HEADER: Character Profile & Vitals -->
          <div class="shrink-0 p-3 sm:p-4 md:p-5 border-b border-slate-800/80 bg-slate-950/50 flex flex-col gap-2.5 sm:gap-3">
            <div class="flex items-center justify-between gap-2.5 sm:gap-3">
              <!-- Left: Avatar + Identity -->
              <div class="flex items-center gap-2.5 sm:gap-4 min-w-0">
                <div 
                  class="relative shrink-0 w-11 h-11 sm:w-14 sm:h-14 rounded-xl sm:rounded-2xl bg-slate-800/80 border border-slate-700/60 overflow-hidden flex items-center justify-center shadow-lg cursor-pointer group/avatar hover:border-amber-500/50 transition-colors"
                  @click="showBio = true"
                  title="View Character Biography"
                >
                  <img 
                    v-if="sheet.profile_image && showImage(sheet.profile_image)" 
                    :src="getImageUrl(sheet.profile_image)" 
                    class="w-full h-full object-cover object-top group-hover/avatar:scale-105 transition-transform" 
                    @error="handleImageError(sheet.profile_image)" 
                  />
                  <img 
                    v-else 
                    src="@/assets/svg/upper-body-bust-silhouette.svg" 
                    class="w-7 h-7 sm:w-10 sm:h-10 object-contain filter brightness-[400%] opacity-80" 
                  />
                  <span class="absolute bottom-0 inset-x-0 bg-slate-950/80 text-[8px] font-bold text-slate-400 text-center uppercase tracking-wider py-0.5 opacity-0 group-hover/avatar:opacity-100 transition-opacity">
                    Bio
                  </span>
                </div>

                <div class="min-w-0 flex-grow">
                  <div class="flex items-center gap-1.5 sm:gap-2 flex-wrap">
                    <h3 class="text-sm sm:text-xl md:text-2xl font-black text-white uppercase tracking-tight truncate font-display">
                      {{ sheet.name || 'Unnamed' }}
                    </h3>
                    <div v-if="sheet.adventure_version" class="text-[9px] sm:text-[10px] font-mono font-bold text-slate-400 bg-slate-800/80 px-1.5 py-0.5 rounded border border-slate-700/40">
                      v{{ sheet.adventure_version }}
                    </div>
                  </div>
                  <div class="flex items-center gap-2 mt-0.5">
                    <span class="text-[11px] sm:text-xs font-black text-amber-400 uppercase tracking-widest truncate">
                      {{ sheet.role || 'Adventurer' }}
                    </span>
                    <button 
                      v-if="sheet.description"
                      class="text-[10px] text-slate-400 hover:text-amber-300 underline underline-offset-2 flex items-center gap-1 font-sans transition-colors"
                      @click="showBio = true"
                    >
                      <i class="ra ra-book text-[10px]"></i>
                      <span>Bio</span>
                    </button>
                  </div>
                </div>
              </div>

              <!-- Right: Vitals (Desktop) & Close Button -->
              <div class="flex items-center gap-3 sm:gap-4 shrink-0">
                <!-- Desktop quick stats bar -->
                <div v-if="sheet.rule_enforcement_mode !== 'chat'" class="hidden md:flex items-center gap-4 min-w-[240px]">
                  <div class="flex-grow">
                    <StatBar label="HP" :value="sheet.hp" :max="sheet.max_hp" color="crimson" size="xs" />
                    <StatBar label="STA" :value="sheet.stamina" :max="sheet.max_stamina" color="emerald" size="xs" />
                    <StatBar v-if="sheet.rule_enforcement_mode === 'rpg'" label="MP" :value="sheet.mana" :max="sheet.max_mana" color="sapphire" size="xs" />
                  </div>
                </div>

                <!-- Close Button -->
                <button
                  class="p-2 sm:p-2.5 rounded-full bg-slate-800/80 hover:bg-red-600 text-slate-400 hover:text-white transition-all shadow-md border border-slate-700/60"
                  @click="onClose"
                  title="Close Character Sheet (Esc)"
                  aria-label="Close"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>

            <!-- Mobile Vitals (compact bar) -->
            <div v-if="sheet.rule_enforcement_mode !== 'chat'" class="md:hidden grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1 border-t border-slate-800/40">
              <StatBar label="HP" :value="sheet.hp" :max="sheet.max_hp" color="crimson" size="xs" />
              <StatBar label="STA" :value="sheet.stamina" :max="sheet.max_stamina" color="emerald" size="xs" />
              <StatBar v-if="sheet.rule_enforcement_mode === 'rpg'" label="MP" :value="sheet.mana" :max="sheet.max_mana" color="sapphire" size="xs" />
            </div>
          </div>

          <!-- TAB SWITCHER -->
          <div class="shrink-0 px-2.5 sm:px-6 pt-2.5 sm:pt-4 pb-2 bg-slate-950/20 border-b border-slate-800/50">
            <div class="flex items-center gap-1 sm:gap-2.5 p-1 bg-slate-950/70 border border-slate-800/80 rounded-2xl">
              <!-- Tab 1: Inventory -->
              <button
                :class="[
                  'flex-1 flex items-center justify-center gap-1 sm:gap-2 py-1.5 sm:py-2.5 px-1.5 sm:px-4 rounded-xl font-bold uppercase tracking-wider text-[11px] sm:text-xs md:text-sm transition-all select-none',
                  activeTab === 'inventory'
                    ? 'bg-slate-800 text-amber-400 shadow-md border border-slate-700/80'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
                ]"
                @click="activeTab = 'inventory'"
              >
                <i class="ra ra-backpack text-xs sm:text-base"></i>
                <span class="hidden sm:inline truncate">Inventory</span>
                <span class="sm:hidden">Bag</span>
                <span 
                  class="text-[9px] sm:text-xs font-mono font-bold px-1 sm:px-1.5 py-0.5 rounded-md"
                  :class="activeTab === 'inventory' ? 'bg-amber-400/15 text-amber-300' : 'bg-slate-800/80 text-slate-400'"
                >
                  {{ inventoryList.length }}/24
                </span>
              </button>

              <!-- Tab 2: Equipped Items -->
              <button
                :class="[
                  'flex-1 flex items-center justify-center gap-1 sm:gap-2 py-1.5 sm:py-2.5 px-1.5 sm:px-4 rounded-xl font-bold uppercase tracking-wider text-[11px] sm:text-xs md:text-sm transition-all select-none',
                  activeTab === 'equipment'
                    ? 'bg-slate-800 text-amber-400 shadow-md border border-slate-700/80'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
                ]"
                @click="activeTab = 'equipment'"
              >
                <i class="ra ra-vest text-xs sm:text-base"></i>
                <span class="hidden sm:inline truncate">Equipped</span>
                <span class="sm:hidden">Gear</span>
                <span 
                  class="text-[9px] sm:text-xs font-mono font-bold px-1 sm:px-1.5 py-0.5 rounded-md"
                  :class="activeTab === 'equipment' ? 'bg-amber-400/15 text-amber-300' : 'bg-slate-800/80 text-slate-400'"
                >
                  {{ equippedCount }}/11
                </span>
              </button>

              <!-- Tab 3: Ailments & Buffs -->
              <button
                :class="[
                  'flex-1 flex items-center justify-center gap-1 sm:gap-2 py-1.5 sm:py-2.5 px-1.5 sm:px-4 rounded-xl font-bold uppercase tracking-wider text-[11px] sm:text-xs md:text-sm transition-all select-none',
                  activeTab === 'ailments'
                    ? 'bg-slate-800 text-amber-400 shadow-md border border-slate-700/80'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
                ]"
                @click="activeTab = 'ailments'"
              >
                <i class="ra ra-aura text-xs sm:text-base"></i>
                <span class="hidden md:inline truncate">Ailments & Buffs</span>
                <span class="md:hidden">Status</span>
                <span 
                  class="text-[9px] sm:text-xs font-mono font-bold px-1 sm:px-1.5 py-0.5 rounded-md"
                  :class="[
                    statusEffects.length > 0 
                      ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' 
                      : (activeTab === 'ailments' ? 'bg-amber-400/15 text-amber-300' : 'bg-slate-800/80 text-slate-400')
                  ]"
                >
                  {{ statusEffects.length }}
                </span>
              </button>
            </div>
          </div>

          <!-- TAB CONTENT BODY -->
          <div class="flex-grow overflow-y-auto custom-scrollbar p-3.5 sm:p-6 min-h-0">
            
            <!-- ============================================== -->
            <!-- TAB 1: INVENTORY (BACKPACK) -->
            <!-- ============================================== -->
            <div v-if="activeTab === 'inventory'" class="flex flex-col h-full">
              <div class="flex items-center justify-between gap-2 mb-3 sm:mb-4 shrink-0">
                <div class="flex items-center gap-2">
                  <h4 class="text-xs sm:text-sm font-black text-slate-400 uppercase tracking-widest">Backpack Contents</h4>
                </div>
                <div class="text-xxs sm:text-xs font-mono font-bold text-slate-500">
                  <span class="text-amber-400">{{ inventoryList.length }}</span> / 24 slots used
                </div>
              </div>

              <!-- Inventory Grid -->
              <div class="grid grid-cols-4 sm:grid-cols-6 gap-2 sm:gap-3.5">
                <div 
                  v-for="idx in 24" 
                  :key="idx"
                  class="aspect-square rounded-xl sm:rounded-2xl border-2 flex items-center justify-center transition-all relative group"
                  :class="[
                    inventoryList[idx-1] 
                      ? 'bg-slate-950 border-slate-700/60 hover:border-amber-500/70 hover:bg-slate-900/80 hover:shadow-[0_0_15px_rgba(245,158,11,0.2)]' 
                      : 'bg-slate-900/25 border-slate-800/50 border-dashed',
                    inventoryList[idx-1] ? (isInteractable(inventoryList[idx-1]) ? 'cursor-pointer active:scale-95' : 'cursor-help') : ''
                  ]"
                  @click="inventoryList[idx-1] && handleInventoryClick(inventoryList[idx-1])"
                  @mouseenter="inventoryList[idx-1] && emit('itemHover', { ...inventoryList[idx-1], entity_type: 'ITEM' }, $event)"
                  @mouseleave="emit('itemLeave')"
                  @contextmenu.prevent="inventoryList[idx-1] && emit('itemContextmenu', { ...inventoryList[idx-1], entity_type: 'ITEM' }, $event)"
                >
                  <template v-if="inventoryList[idx-1]">
                    <!-- READ/NOTE tag -->
                    <div 
                      v-if="String(inventoryList[idx-1].item_type || '').toUpperCase() === 'READABLE'" 
                      class="absolute top-1 left-1 z-20 px-1 py-0.2 rounded text-[7px] sm:text-[8px] font-black tracking-wide border leading-none"
                      :class="Boolean(inventoryList[idx-1].is_read) ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' : 'bg-amber-500/20 text-amber-200 border-amber-500/40'"
                    >
                      {{ Boolean(inventoryList[idx-1].is_read) ? 'READ' : 'NOTE' }}
                    </div>

                    <!-- Item Thumbnail -->
                    <div v-if="showImage(inventoryList[idx-1].image_url)" class="w-full h-full p-1.5 sm:p-2">
                      <img 
                        :src="getImageUrl(inventoryList[idx-1].image_url)" 
                        class="w-full h-full object-cover object-top rounded-lg transition-transform group-hover:scale-105" 
                        @error="handleImageError(inventoryList[idx-1].image_url)" 
                      />
                    </div>
                    <!-- Fallback RPG-Awesome Icon -->
                    <i 
                      v-else 
                      :class="['ra text-2xl sm:text-3xl transition-transform group-hover:scale-110', getItemIcon(inventoryList[idx-1].item_type), getTypeColor(inventoryList[idx-1].item_type)]"
                    ></i>

                    <!-- Debug ID -->
                    <div v-if="isDebug" class="absolute bottom-1 right-1 px-1 bg-black/75 rounded text-[7px] font-mono text-amber-300 opacity-70">
                      {{ inventoryList[idx-1].id || inventoryList[idx-1].key }}
                    </div>
                  </template>

                  <!-- Empty slot number -->
                  <div v-else class="text-[10px] font-mono text-slate-700/40 select-none">
                    {{ idx }}
                  </div>
                </div>
              </div>

              <!-- Quick Instruction Hint -->
              <div class="mt-4 pt-3 border-t border-slate-800/40 flex items-center justify-between text-xxs text-slate-500 flex-wrap gap-2">
                <span>💡 Click item to equip or consume.</span>
                <span>Right-click or hold for actions.</span>
              </div>
            </div>

            <!-- ============================================== -->
            <!-- TAB 2: EQUIPPED ITEMS -->
            <!-- ============================================== -->
            <div v-else-if="activeTab === 'equipment'" class="flex flex-col gap-6">
              
              <!-- Core RPG Attributes Strip -->
              <div v-if="sheet.rule_enforcement_mode === 'rpg'" class="bg-slate-950/60 border border-slate-800/80 rounded-2xl p-3 sm:p-4">
                <div class="text-xxs font-black text-slate-500 uppercase tracking-widest mb-2">Character Attributes</div>
                <div class="grid grid-cols-3 sm:grid-cols-6 gap-2 sm:gap-3">
                  <div 
                    v-for="attr in coreAttributes" 
                    :key="attr.label"
                    class="bg-slate-900/80 border border-slate-800 rounded-xl p-2 flex flex-col items-center justify-center text-center shadow-sm"
                  >
                    <div class="flex items-center gap-1.5">
                      <i :class="['ra text-xs sm:text-sm', attr.icon, attr.color]"></i>
                      <span class="text-[10px] sm:text-xs font-black text-slate-400 uppercase tracking-wider">{{ attr.label }}</span>
                    </div>
                    <span class="text-base sm:text-lg font-black text-white font-mono mt-0.5">
                      {{ attr.value !== undefined && attr.value !== null ? attr.value : '—' }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Desktop & Tablet Layout: Silhouette + Slot Detail List -->
              <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                
                <!-- Silhouette Display (Left on LG, centered) -->
                <div class="lg:col-span-7 flex flex-col items-center">
                  <div class="relative w-full max-w-sm sm:max-w-md h-[340px] sm:h-[420px] silhouette-container bg-slate-950/40 rounded-3xl border border-slate-800/60 shadow-inner flex items-center justify-center overflow-hidden">
                    <img 
                      src="@/assets/svg/full-body-human-silhouette.svg" 
                      class="h-full w-full object-contain opacity-45 filter brightness-[300%] contrast-75 drop-shadow-[0_0_20px_rgba(255,255,255,0.15)]" 
                    />

                    <!-- Equipment Slot Badges on Silhouette -->
                    <div 
                      v-for="(pos, slot) in slotPositions" 
                      :key="slot"
                      class="absolute -translate-x-1/2 -translate-y-1/2 group/slot"
                      :style="{ top: pos.top, left: pos.left }"
                      @mouseenter="equipment[slot] && emit('itemHover', { ...equipment[slot], entity_type: 'ITEM' }, $event)"
                      @mouseleave="emit('itemLeave')"
                    >
                      <div 
                        class="w-11 h-11 sm:w-14 sm:h-14 rounded-xl sm:rounded-2xl border-2 flex items-center justify-center transition-all relative shadow-xl backdrop-blur-md"
                        :class="[
                          equipment[slot] 
                            ? 'bg-slate-900 border-amber-500/70 shadow-amber-500/20 scale-105 z-10 cursor-pointer' 
                            : 'bg-slate-950/60 border-slate-800 hover:border-slate-600'
                        ]"
                        @click="equipment[slot] && handleUnequip(slot)"
                        @contextmenu.prevent="equipment[slot] && emit('itemContextmenu', { ...equipment[slot], equipped_slot: slot, entity_type: 'ITEM' }, $event)"
                      >
                        <!-- Tooltip with slot name -->
                        <div class="absolute -top-7 left-1/2 -translate-x-1/2 text-xxs font-black uppercase tracking-widest text-slate-300 opacity-0 group-hover/slot:opacity-100 transition-opacity bg-slate-800/95 px-2 py-0.5 rounded border border-slate-700 z-20 shadow-xl whitespace-nowrap pointer-events-none">
                          {{ slot.replace('_', ' ') }}
                        </div>

                        <!-- Equipped Item Display -->
                        <template v-if="equipment[slot]">
                          <div v-if="showImage(equipment[slot]!.image_url)" class="w-full h-full p-1">
                            <img 
                              :src="getImageUrl(equipment[slot]!.image_url)" 
                              class="w-full h-full object-cover object-top rounded-lg" 
                              @error="handleImageError(equipment[slot]!.image_url)" 
                            />
                          </div>
                          <i v-else :class="['ra text-sm sm:text-xl', getItemIcon(equipment[slot]!.item_type), getTypeColor(equipment[slot]!.item_type)]"></i>
                        </template>

                        <!-- Empty Slot Placeholder -->
                        <div v-else class="opacity-20 group-hover/slot:opacity-40 transition-opacity">
                          <i :class="['ra text-xs sm:text-base text-slate-400', getSlotPlaceholderIcon(slot)]"></i>
                        </div>
                      </div>
                    </div>
                  </div>

                  <span class="text-xxs text-slate-500 mt-2">
                    Click equipped slot to unequip · Right-click for options
                  </span>
                </div>

                <!-- Equipped Items List (Right on LG, full list for easy mobile/desktop access) -->
                <div class="lg:col-span-5 flex flex-col gap-2">
                  <div class="flex items-center justify-between mb-1">
                    <h5 class="text-xs font-black text-slate-400 uppercase tracking-widest">Gear Overview</h5>
                    <span class="text-xxs text-amber-400 font-mono">{{ equippedCount }} equipped</span>
                  </div>

                  <div class="space-y-1.5 max-h-[420px] overflow-y-auto custom-scrollbar pr-1">
                    <div 
                      v-for="slot in SLOTS_LIST" 
                      :key="slot.key"
                      class="flex items-center justify-between p-2 rounded-xl border transition-colors"
                      :class="[
                        equipment[slot.key]
                          ? 'bg-slate-950/80 border-slate-700/60 hover:border-amber-500/50'
                          : 'bg-slate-900/30 border-slate-800/40 opacity-50'
                      ]"
                    >
                      <div class="flex items-center gap-2.5 min-w-0">
                        <div class="w-8 h-8 rounded-lg bg-slate-800/80 border border-slate-700/60 flex items-center justify-center shrink-0">
                          <template v-if="equipment[slot.key]">
                            <img 
                              v-if="showImage(equipment[slot.key]!.image_url)" 
                              :src="getImageUrl(equipment[slot.key]!.image_url)" 
                              class="w-full h-full object-cover rounded-md" 
                              @error="handleImageError(equipment[slot.key]!.image_url)" 
                            />
                            <i v-else :class="['ra text-sm', getItemIcon(equipment[slot.key]!.item_type), getTypeColor(equipment[slot.key]!.item_type)]"></i>
                          </template>
                          <i v-else :class="['ra text-xs text-slate-500', slot.icon]"></i>
                        </div>

                        <div class="min-w-0">
                          <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{{ slot.label }}</div>
                          <div class="text-xs font-bold truncate" :class="equipment[slot.key] ? 'text-white' : 'text-slate-600'">
                            {{ equipment[slot.key]?.name || 'Empty' }}
                          </div>
                        </div>
                      </div>

                      <button
                        v-if="equipment[slot.key]"
                        class="px-2 py-1 rounded-lg bg-slate-800 hover:bg-red-900/50 border border-slate-700 hover:border-red-500/50 text-[10px] font-bold text-slate-300 hover:text-red-300 transition-colors shrink-0"
                        @click="handleUnequip(slot.key)"
                        title="Unequip this item"
                      >
                        Unequip
                      </button>
                    </div>
                  </div>
                </div>

              </div>
            </div>

            <!-- ============================================== -->
            <!-- TAB 3: AILMENTS & BUFFS -->
            <!-- ============================================== -->
            <div v-else-if="activeTab === 'ailments'" class="flex flex-col h-full">
              
              <!-- When No Effects: Perfect Condition Banner -->
              <div 
                v-if="statusEffects.length === 0" 
                class="flex-grow flex flex-col items-center justify-center p-8 text-center bg-slate-950/40 rounded-3xl border border-slate-800/60 my-auto"
              >
                <div class="w-16 h-16 sm:w-20 sm:h-20 rounded-3xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mb-4 shadow-[0_0_30px_rgba(16,185,129,0.15)]">
                  <i class="ra ra-shield text-3xl sm:text-4xl text-emerald-400"></i>
                </div>
                <h4 class="text-lg sm:text-xl font-black text-white uppercase tracking-tight mb-2 font-display">
                  Peak Condition
                </h4>
                <p class="text-xs sm:text-sm text-slate-400 max-w-md leading-relaxed font-sans">
                  Your character is free of any ailments, injuries, curses, or lingering debuffs. All vital systems are functioning normally.
                </p>
                <div class="mt-4 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xxs font-bold uppercase tracking-wider flex items-center gap-1.5">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  Active Condition: Optimal
                </div>
              </div>

              <!-- When Effects are Active: Cards Grid -->
              <div v-else class="space-y-3">
                <div class="flex items-center justify-between mb-2">
                  <h4 class="text-xs sm:text-sm font-black text-slate-400 uppercase tracking-widest">Active Effects</h4>
                  <span class="text-xxs font-mono font-bold text-amber-400">{{ statusEffects.length }} active</span>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div 
                    v-for="effect in statusEffects" 
                    :key="effect"
                    class="p-4 rounded-2xl border transition-all flex items-start gap-3.5 shadow-lg"
                    :class="[
                      isPositiveEffect(effect)
                        ? 'bg-emerald-950/20 border-emerald-500/40 shadow-emerald-900/10'
                        : 'bg-rose-950/20 border-rose-500/40 shadow-rose-900/10'
                    ]"
                  >
                    <!-- Effect Icon -->
                    <div 
                      class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border"
                      :class="[
                        isPositiveEffect(effect)
                          ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
                          : 'bg-rose-500/15 border-rose-500/30 text-rose-400'
                      ]"
                    >
                      <i :class="['ra text-xl', getStatusIcon(effect)]"></i>
                    </div>

                    <!-- Effect Details -->
                    <div class="min-w-0 flex-grow">
                      <div class="flex items-center justify-between gap-2">
                        <span class="text-sm font-bold text-white capitalize truncate">{{ effect }}</span>
                        <span 
                          class="text-[9px] font-black uppercase tracking-wider px-1.5 py-0.5 rounded border shrink-0"
                          :class="[
                            isPositiveEffect(effect)
                              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                              : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                          ]"
                        >
                          {{ isPositiveEffect(effect) ? 'Buff' : 'Ailment' }}
                        </span>
                      </div>
                      <div class="flex items-center gap-2 mt-1.5">
                        <span class="w-1.5 h-1.5 rounded-full" :class="isPositiveEffect(effect) ? 'bg-emerald-400' : 'bg-rose-400'"></span>
                        <span class="text-[11px] text-slate-400 italic">Currently active effect</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

            </div>

          </div>

          <!-- CHARACTER BIO MODAL / POPUP OVERLAY -->
          <Transition name="fade">
            <div 
              v-if="showBio" 
              class="absolute inset-0 z-40 bg-slate-950/95 backdrop-blur-md p-4 sm:p-6 flex flex-col overflow-hidden"
            >
              <div class="flex items-center justify-between pb-3 border-b border-slate-800 shrink-0">
                <div class="flex items-center gap-2.5">
                  <i class="ra ra-book text-amber-400 text-lg"></i>
                  <h4 class="text-base sm:text-xl font-black text-white uppercase tracking-tight font-display">
                    Character Lore & Biography
                  </h4>
                </div>
                <button 
                  class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                  @click="showBio = false"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                  </svg>
                </button>
              </div>

              <div class="flex-grow overflow-y-auto custom-scrollbar py-4 space-y-4">
                <div class="flex items-start gap-4">
                  <div class="w-20 h-20 sm:w-24 sm:h-24 rounded-2xl bg-slate-900 border border-slate-800 overflow-hidden shrink-0 shadow-lg">
                    <img 
                      v-if="sheet.profile_image && showImage(sheet.profile_image)" 
                      :src="getImageUrl(sheet.profile_image)" 
                      class="w-full h-full object-cover object-top" 
                    />
                    <img 
                      v-else 
                      src="@/assets/svg/upper-body-bust-silhouette.svg" 
                      class="w-full h-full object-contain p-2 filter brightness-[400%] opacity-80" 
                    />
                  </div>
                  <div>
                    <h5 class="text-lg font-black text-white uppercase font-display">{{ sheet.name }}</h5>
                    <div class="text-xs font-bold text-amber-400 uppercase tracking-widest mt-0.5">{{ sheet.role || 'Adventurer' }}</div>
                    <div v-if="sheet.adventure_title" class="text-xxs text-slate-400 mt-1">Adventure: <span class="text-slate-200">{{ sheet.adventure_title }}</span></div>
                  </div>
                </div>

                <div class="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-4">
                  <div class="text-xxs font-black text-amber-500 uppercase tracking-widest mb-2">Backstory</div>
                  <p class="text-xs sm:text-sm text-slate-300 leading-relaxed font-serif whitespace-pre-line italic">
                    {{ sheet.description || 'No detailed biography or historical records found for this adventurer.' }}
                  </p>
                </div>
              </div>

              <div class="pt-3 border-t border-slate-800 flex justify-end shrink-0">
                <button 
                  class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-bold uppercase tracking-wider text-white transition-colors"
                  @click="showBio = false"
                >
                  Close Lore
                </button>
              </div>
            </div>
          </Transition>

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
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 4px; }
.ra { font-family: 'rpgawesome' !important; display: inline-block; line-height: 1; text-align: center; }
</style>
