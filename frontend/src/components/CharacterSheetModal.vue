<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import StatBar from './StatBar.vue'
import type { CharacterSheet } from '@/types'

const props = defineProps<{
  open: boolean
  sheet: CharacterSheet | null
}>()

const emit = defineEmits<{
  close: []
}>()

const sortedStats = computed(() => {
  if (!props.sheet?.stats) return []
  return Object.entries(props.sheet.stats).sort(([a], [b]) => a.localeCompare(b))
})

const inventoryList = computed(() => props.sheet?.inventory ?? [])
const equipmentEntries = computed(() => Object.entries(props.sheet?.equipment ?? {}))
const statusEffects = computed(() => props.sheet?.status_effects ?? [])

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.open) {
    emit('close')
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

const getItemIcon = (type?: string) => {
  switch (type?.toUpperCase()) {
    case 'CONSUMABLE': return 'ra-bottle-vapors'
    case 'WEAPON': return 'ra-sword'
    case 'TOOL': return 'ra-hammer'
    case 'KEY': return 'ra-old-key'
    case 'READABLE': return 'ra-book'
    case 'WEARABLE': return 'ra-helmet'
    case 'COMBINABLE': return 'ra-gears'
    case 'PICKABLE': return 'ra-hand'
    case 'STATIC': return 'ra-anchor'
    default: return 'ra-quill-ink'
  }
}

const getTypeColor = (type?: string) => {
  switch (type?.toUpperCase()) {
    case 'WEAPON': return 'text-red-400'
    case 'CONSUMABLE': return 'text-emerald-400'
    case 'KEY': return 'text-amber-400'
    case 'READABLE': return 'text-cyan-400'
    case 'WEARABLE': return 'text-blue-400'
    default: return 'text-slate-400'
  }
}

const brokenImages = ref<Record<string, boolean>>({})

const getImageUrl = (path?: string) => {
  if (!path) return ''
  if (path.startsWith('http')) return path
  // In dev, the frontend is on 5173 and backend on 8000
  const baseUrl = window.location.origin.replace('5173', '8000')
  return `${baseUrl}${path}`
}

const handleImageError = (path: string) => {
  brokenImages.value[path] = true
}

const showImage = (path?: string) => {
  return path && !brokenImages.value[path]
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4"
        @click.self="emit('close')"
      >
        <div class="w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl relative">
          <!-- Header -->
          <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4 bg-slate-950/50 shrink-0">
            <h2 class="text-xl font-bold text-white flex items-center gap-3">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              Character Sheet
            </h2>
            <button
              class="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
              @click="emit('close')"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>

          <!-- Body -->
          <div class="flex-grow overflow-y-auto p-6" v-if="sheet">
            <div class="flex flex-col lg:flex-row gap-8">
              
              <!-- Left: Stats & Core -->
              <div class="w-full lg:w-72 space-y-6 shrink-0">
                <!-- Identity -->
                <div class="bg-slate-950/40 rounded-2xl p-6 border border-slate-800/50 shadow-inner">
                  <div class="flex items-center gap-4">
                    <div v-if="sheet.profile_image && showImage(sheet.profile_image)" class="w-16 h-16 rounded-lg overflow-hidden border border-slate-700">
                      <img :src="getImageUrl(sheet.profile_image)" class="w-full h-full object-cover" @error="handleImageError(sheet.profile_image)" />
                    </div>
                    <div>
                      <h3 class="text-2xl font-black tracking-tight text-white mb-1 uppercase">{{ sheet.name || 'Unnamed' }}</h3>
                      <div v-if="sheet.role" class="text-sm text-slate-400 font-semibold">{{ sheet.role }}</div>
                    </div>
                  </div>
                  <p v-if="sheet.description" class="text-sm text-slate-300 mt-3 italic">{{ sheet.description }}</p>
                    <StatBar label="Health" :value="sheet.hp" color="crimson" />
                  <StatBar label="Stamina" :value="sheet.stamina" color="emerald" />
                  <StatBar label="Mana" :value="sheet.mana" color="sapphire" />
                </div>
                
                <!-- Attributes -->
                <div class="bg-slate-950/40 rounded-2xl p-6 border border-slate-800/50 shadow-inner">
                  <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] mb-4 flex items-center gap-2">
                    <i class="ra ra-double-team"></i>
                    Attributes
                  </h4>
                  <div v-if="sortedStats.length" class="space-y-3">
                    <div
                      v-for="[key, value] in sortedStats"
                      :key="key"
                      class="flex items-center justify-between group"
                    >
                      <span class="text-xs text-slate-500 uppercase tracking-wider group-hover:text-slate-300 transition-colors">{{ key }}</span>
                      <span class="text-sm font-black text-amber-500 font-mono">{{ value }}</span>
                    </div>
                  </div>
                </div>

                <!-- Status -->
                <div class="bg-slate-950/40 rounded-2xl p-6 border border-slate-800/50 shadow-inner">
                  <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] mb-4 flex items-center gap-2">
                    <i class="ra ra-burning-embers"></i>
                    Status
                  </h4>
                  <div v-if="statusEffects.length" class="flex flex-wrap gap-2">
                    <span
                      v-for="effect in statusEffects"
                      :key="effect"
                      class="px-2 py-1 rounded bg-red-950/30 border border-red-900/50 text-red-400 text-[10px] font-bold uppercase tracking-tighter"
                    >
                      {{ effect }}
                    </span>
                  </div>
                  <p v-else class="text-[10px] text-slate-600 italic">No active effects.</p>
                </div>
              </div>

              <!-- Main Content: Equipment & Backpack -->
              <div class="flex-grow space-y-8">
                <!-- Equipment Grid -->
                <div class="bg-slate-950/20 rounded-2xl p-6 border border-slate-800 shadow-inner">
                  <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] mb-6 flex items-center gap-2">
                    <i class="ra ra-helmet"></i>
                    Worn Equipment
                  </h4>
                  <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                    <div
                      v-for="[slot, item] in equipmentEntries"
                      :key="slot"
                      class="p-3 bg-slate-900 border border-slate-800 rounded-xl flex flex-col items-center justify-center text-center group transition-all hover:bg-slate-800 hover:border-slate-700"
                    >
                      <span class="text-[9px] text-slate-600 uppercase font-bold tracking-widest mb-2">{{ slot }}</span>
                      <template v-if="item && typeof item === 'object'">
                        <div v-if="showImage((item as any).image_url)" class="relative w-12 h-12 mb-2 rounded-lg overflow-hidden border border-slate-700 shadow-lg">
                          <img 
                            :src="getImageUrl((item as any).image_url)" 
                            class="w-full h-full object-cover" 
                            @error="handleImageError((item as any).image_url)"
                          />
                        </div>
                        <i v-else :class="['text-xl mb-2', getItemIcon((item as any).item_type), getTypeColor((item as any).item_type)]"></i>
                        <span class="text-xs font-bold text-slate-200 line-clamp-1 truncate w-full px-1">{{ (item as any).name }}</span>
                      </template>
                      <template v-else>
                        <i class="ra ra-plain-dagger text-slate-800 text-lg mb-2 opacity-20"></i>
                        <span class="text-[10px] text-slate-700 italic">Empty</span>
                      </template>
                    </div>
                  </div>
                </div>

                <!-- Bag Grid -->
                <div class="flex-grow bg-slate-950/20 rounded-2xl p-6 border border-slate-800 shadow-inner min-h-[300px] flex flex-col">
                  <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] mb-6 flex items-center gap-2">
                    <i class="ra ra-knapsack"></i>
                    Backpack
                  </h4>
                  <div v-if="inventoryList.length" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5 gap-3">
                    <div
                      v-for="(item, idx) in inventoryList"
                      :key="idx"
                      class="p-3 bg-slate-900 border border-slate-800 rounded-xl group cursor-pointer transition-all hover:border-slate-500 hover:scale-[1.02] flex flex-col items-center"
                    >
                      <div v-if="showImage(item?.image_url)" class="relative w-16 h-16 mb-3 rounded-lg overflow-hidden border border-slate-700 shadow-lg">
                        <img 
                          :src="getImageUrl(item.image_url)" 
                          class="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500" 
                          @error="handleImageError(item.image_url)"
                        />
                      </div>
                      <i v-else :class="['text-2xl mb-3', getItemIcon(item?.item_type), getTypeColor(item?.item_type)]"></i>
                      <span class="text-[11px] font-bold text-slate-300 text-center leading-tight line-clamp-2 truncate w-full">{{ item?.name || 'Unknown' }}</span>
                      <span v-if="item?.item_type" class="text-[8px] text-slate-600 uppercase mt-2 font-mono tracking-widest">{{ item.item_type }}</span>
                    </div>
                  </div>
                  <div v-else class="flex-grow flex flex-col items-center justify-center opacity-20 py-12">
                    <i class="ra ra-desert-skull text-6xl mb-4"></i>
                    <p class="text-sm font-bold uppercase tracking-[0.3em]">Vault is Empty</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <div v-else class="p-12 text-center text-slate-500">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 mx-auto mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p>Character data unavailable.</p>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
