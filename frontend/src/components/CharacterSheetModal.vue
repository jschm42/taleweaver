<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import StatBar from './StatBar.vue'
import type { CharacterSheet } from '@/types'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'

const props = defineProps<{
  open: boolean
  sheet: CharacterSheet | null
}>()

const emit = defineEmits<{
  close: []
  itemClick: [name: string]
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
}>()

const sortedStats = computed(() => {
  if (!props.sheet?.stats) return []
  return Object.entries(props.sheet.stats).sort(([a], [b]) => a.localeCompare(b))
})

const inventoryList = computed(() => props.sheet?.inventory ?? [])
const equipment = computed(() => props.sheet?.equipment ?? {})
const statusEffects = computed(() => props.sheet?.status_effects ?? [])

const coreAttributes = computed(() => {
  if (!props.sheet) return []
  return [
    { label: 'STR', value: props.sheet.strength, icon: 'ra-muscle-up' },
    { label: 'DEX', value: props.sheet.dexterity, icon: 'ra-fast-forward' },
    { label: 'INT', value: props.sheet.intelligence, icon: 'ra-brain' },
    { label: 'WIS', value: props.sheet.wisdom, icon: 'ra-book' },
    { label: 'CHA', value: props.sheet.charisma, icon: 'ra-double-team' },
    { label: 'AC', value: props.sheet.armor_class, icon: 'ra-shield' }
  ]
})

const getSlotPlaceholderIcon = (slot: string) => {
  const map: Record<string, string> = {
    Head: 'ra-helmet',
    Chest: 'ra-chestplate',
    Arms: 'ra-bracers',
    Hands: 'ra-gloves',
    Legs: 'ra-leggings',
    Feet: 'ra-boots',
    Ring_1: 'ra-ring',
    Ring_2: 'ra-ring',
    Amulet: 'ra-necklace'
  }
  return map[slot] || 'ra-plain-dagger'
}

// Three-column layout within the silhouette area
const slotPositions: Record<string, { top: string, left: string }> = {
  // LEFT: Accessories
  Amulet: { top: '15%', left: '10%' },
  Ring_1: { top: '45%', left: '10%' },
  Ring_2: { top: '75%', left: '10%' },
  
  // RIGHT COL 1
  Head: { top: '15%', left: '76%' },
  Chest: { top: '45%', left: '76%' },
  Arms: { top: '75%', left: '76%' },
  
  // RIGHT COL 2
  Hands: { top: '15%', left: '92%' },
  Legs: { top: '45%', left: '92%' },
  Feet: { top: '75%', left: '92%' },
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.open) {
    emit('close')
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

const brokenImages = ref<Record<string, boolean>>({})

const handleImageError = (path?: string | null) => {
  if (!path) return
  brokenImages.value[path] = true
}

const showImage = (path?: string | null) => {
  return !!path && !brokenImages.value[path]
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-50 bg-slate-950/95 backdrop-blur-md flex items-center justify-center p-4"
        @click.self="emit('close')"
      >
        <div class="w-full max-w-7xl h-[95vh] md:h-[90vh] flex flex-col bg-slate-900 border border-slate-800 rounded-3xl shadow-[0_0_100px_rgba(0,0,0,0.9)] relative animate-sheet-in overflow-hidden">
          
          <!-- Close Button -->
          <button
            class="absolute top-6 right-6 z-30 p-2.5 rounded-full bg-slate-800/80 hover:bg-red-600 text-slate-400 hover:text-white transition-all shadow-xl backdrop-blur-sm border border-slate-700/50"
            @click="emit('close')"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>

          <!-- Main Content Split -->
          <div class="flex-grow flex flex-col md:flex-row min-h-0" v-if="sheet">
            
            <!-- LEFT COLUMN -->
            <div class="w-full md:w-1/2 flex flex-col min-h-0 border-r border-slate-800/50 bg-slate-950/40">
              <div class="flex-grow overflow-y-auto custom-scrollbar p-4 md:p-8 flex flex-col">
                <!-- Identity Header -->
                <div class="flex items-center gap-4 md:gap-6 mb-4 md:mb-8 shrink-0">
                  <div class="relative group/avatar">
                    <div class="w-20 h-20 rounded-2xl bg-slate-800/40 border border-slate-700/50 overflow-hidden flex items-center justify-center shadow-2xl">
                      <img v-if="sheet.profile_image && showImage(sheet.profile_image)" :src="getImageUrl(sheet.profile_image)" class="w-full h-full object-cover" @error="handleImageError(sheet.profile_image)" />
                      <img v-else src="@/assets/svg/upper-body-bust-silhouette.svg" class="w-16 h-16 object-contain opacity-100 filter brightness-[800%] contrast-150 drop-shadow-[0_0_15px_rgba(255,255,255,0.4)]" />
                    </div>
                    <!-- Avatar Bio Hover Popup -->
                    <div class="absolute top-0 left-full ml-4 w-64 p-4 bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl opacity-0 invisible group-hover/avatar:opacity-100 group-hover/avatar:visible transition-all z-50 pointer-events-none">
                      <div class="text-[10px] font-black text-amber-500 uppercase tracking-widest mb-2">Biography</div>
                      <p class="text-[11px] text-slate-300 leading-relaxed italic font-serif opacity-90 whitespace-pre-line">{{ sheet.description || 'No detailed records found.' }}</p>
                    </div>
                  </div>
                  <div class="identity-header">
                    <h3 class="text-xl md:text-3xl font-black text-white uppercase tracking-tighter leading-none">{{ sheet.name || 'Unnamed' }}</h3>
                    <div class="text-[10px] font-black text-amber-500 uppercase tracking-[0.4em] mt-2">{{ sheet.role || 'Adventurer' }}</div>
                  </div>
                </div>

                <!-- Silhouette Container -->
                <div class="relative w-full h-[280px] sm:h-[350px] lg:h-[420px] silhouette-container mb-6 md:mb-10 bg-slate-900/10 rounded-3xl border border-slate-800/10 shadow-inner flex items-center justify-center overflow-hidden shrink-0">
                  <img 
                    src="@/assets/svg/full-body-human-silhouette.svg" 
                    class="h-full w-full object-contain opacity-50 filter brightness-[300%] contrast-75 drop-shadow-[0_0_20px_rgba(255,255,255,0.2)]"
                  />
                  <!-- Equipment Slots -->
                  <div 
                    v-for="(pos, slot) in slotPositions" 
                    :key="slot"
                    class="absolute -translate-x-1/2 -translate-y-1/2 group/slot"
                    :style="{ top: pos.top, left: pos.left }"
                    @mouseenter="equipment[slot] && emit('itemHover', { ...equipment[slot], entity_type: 'ITEM' }, $event)"
                    @mouseleave="emit('itemLeave')"
                  >
                    <div 
                      class="w-14 h-14 md:w-16 md:h-16 rounded-2xl border-2 flex items-center justify-center transition-all relative shadow-xl backdrop-blur-md"
                      :class="equipment[slot] ? 'bg-slate-900 border-amber-500/50 shadow-amber-500/20 scale-110 z-10' : 'bg-slate-950/40 border-slate-800 hover:border-slate-600'"
                    >
                      <!-- Slot Label Tooltip -->
                      <div class="absolute -top-7 left-1/2 -translate-x-1/2 text-[8px] font-black uppercase tracking-widest text-slate-400 opacity-0 group-hover/slot:opacity-100 transition-opacity bg-slate-800 px-2 py-0.5 rounded border border-slate-700 z-20 shadow-xl whitespace-nowrap pointer-events-none">
                        {{ slot.replace('_', ' ') }}
                      </div>

                      <template v-if="equipment[slot]">
                        <div v-if="showImage(equipment[slot].image_url)" class="w-full h-full p-1">
                          <img :src="getImageUrl(equipment[slot].image_url)" class="w-full h-full object-cover rounded-lg" @error="handleImageError(equipment[slot].image_url)" />
                        </div>
                        <i v-else :class="['ra text-lg md:text-xl', getItemIcon(equipment[slot].item_type), getTypeColor(equipment[slot].item_type)]"></i>
                      </template>
                      <div v-else class="opacity-10 group-hover/slot:opacity-30 transition-opacity">
                        <i :class="['ra text-sm md:text-lg', getSlotPlaceholderIcon(slot)]"></i>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Bottom Info (Stats) -->
                <div class="pt-6 border-t border-slate-800/50">
                  <div class="flex flex-col lg:flex-row gap-8 lg:items-start">
                    <!-- Status Bars -->
                    <div class="flex-grow space-y-4">
                      <StatBar label="Health" :value="sheet.hp" color="crimson" />
                      <StatBar label="Stamina" :value="sheet.stamina" color="emerald" />
                      <StatBar label="Mana" :value="sheet.mana" color="sapphire" />
                    </div>
                    
                    <!-- Core Attributes (Vertical List) -->
                    <div class="grid grid-cols-1 gap-y-3 shrink-0 py-1 border-l border-slate-800/30 pl-8">
                      <div v-for="attr in coreAttributes" :key="attr.label" class="flex items-center justify-between gap-6">
                        <span class="text-sm font-black text-slate-500 uppercase tracking-widest">{{ attr.label }}</span>
                        <span class="text-sm font-black text-white font-mono">{{ attr.value !== undefined && attr.value !== null ? attr.value : 'N/A' }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- Secondary Stats List (e.g. from mods) -->
                  <div v-if="sortedStats.length > 0" class="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-x-10 gap-y-2 border-t border-slate-800/20 pt-4">
                    <div v-for="[key, value] in sortedStats" :key="key" class="flex items-center justify-between border-b border-slate-800/10 pb-1.5">
                      <span class="text-[9px] text-slate-500 uppercase font-bold tracking-widest">{{ key }}</span>
                      <span class="text-sm font-black text-white font-mono">{{ value }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- RIGHT COLUMN -->
            <div class="w-full md:w-1/2 flex flex-col min-h-0 bg-slate-900/20">
              <div class="flex-grow overflow-hidden flex flex-col p-4 md:p-8">
                <!-- Inventory (Scrollable) -->
                <div class="flex-grow flex flex-col min-h-0 mb-8">
                  <div class="flex items-center justify-between mb-8">
                    <div class="flex items-center gap-4">
                      <h4 class="text-lg font-black text-white uppercase tracking-widest">Backpack</h4>
                    </div>
                    <span class="text-[10px] font-black text-slate-500 uppercase tracking-widest">{{ inventoryList.length }} / 24</span>
                  </div>
                  <div class="flex-grow overflow-y-auto custom-scrollbar pr-2">
                    <div class="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-4 xl:grid-cols-6 gap-3 md:gap-4">
                      <div 
                        v-for="idx in 24" 
                        :key="idx"
                        class="aspect-square rounded-2xl border-2 flex items-center justify-center transition-all relative group cursor-pointer"
                        :class="inventoryList[idx-1] ? 'bg-slate-950 border-slate-700/50 hover:border-emerald-500/50 hover:bg-slate-900/60' : 'bg-slate-800/20 border-slate-800/60 border-dashed'"
                        @click="inventoryList[idx-1] && emit('itemClick', inventoryList[idx-1].name)"
                        @mouseenter="inventoryList[idx-1] && emit('itemHover', { ...inventoryList[idx-1], entity_type: 'ITEM' }, $event)"
                        @mouseleave="emit('itemLeave')"
                      >
                        <template v-if="inventoryList[idx-1]">
                          <div v-if="showImage(inventoryList[idx-1].image_url)" class="w-full h-full p-2">
                            <img :src="getImageUrl(inventoryList[idx-1].image_url)" class="w-full h-full object-cover rounded-lg transition-transform group-hover:scale-110" @error="handleImageError(inventoryList[idx-1].image_url)" />
                          </div>
                          <i v-else :class="['ra text-3xl', getItemIcon(inventoryList[idx-1].item_type), getTypeColor(inventoryList[idx-1].item_type)]"></i>
                        </template>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Status -->
                <div class="shrink-0">
                  <div class="flex items-center gap-4 mb-4">
                    <h4 class="text-sm md:text-lg font-black text-white uppercase tracking-widest">Ailments & Buffs</h4>
                  </div>
                  <div class="bg-slate-950 border border-slate-800 rounded-3xl overflow-hidden shadow-2xl">
                    <table class="w-full text-left text-xs">
                      <thead class="bg-slate-900 text-slate-500 uppercase font-black tracking-widest">
                        <tr><th class="px-6 py-4">Status</th><th class="px-6 py-4 text-right">State</th></tr>
                      </thead>
                      <tbody class="divide-y divide-slate-800/50">
                        <tr v-for="effect in statusEffects" :key="effect" class="group hover:bg-slate-800/20 transition-colors">
                          <td class="px-6 py-5 font-bold text-orange-400 uppercase">{{ effect }}</td>
                          <td class="px-6 py-5 text-slate-500 italic text-right">Active</td>
                        </tr>
                        <tr v-if="!statusEffects.length">
                          <td colspan="2" class="px-6 py-12 text-center text-slate-700 font-bold uppercase tracking-widest opacity-20">Perfect Condition</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.4s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
@keyframes sheetIn { from { opacity: 0; transform: scale(0.9) translateY(40px); } to { opacity: 1; transform: scale(1) translateY(0); } }
.animate-sheet-in { animation: sheetIn 0.5s cubic-bezier(0.16, 1, 0.3, 1); }
.custom-scrollbar::-webkit-scrollbar { width: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }
.ra { font-family: 'rpgawesome' !important; display: inline-block; line-height: 1; text-align: center; }

@media (max-height: 850px) {
  .silhouette-container {
    height: 300px !important;
    margin-bottom: 1.5rem !important;
  }
  .bio-container {
    min-height: 100px !important;
  }
  .identity-header h3 {
    font-size: 1.25rem !important;
  }
}
</style>
