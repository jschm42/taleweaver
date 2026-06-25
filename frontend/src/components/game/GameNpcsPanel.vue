<script setup lang="ts">
import { ref } from 'vue'
import { ChevronDown, ChevronRight } from 'lucide-vue-next'
import { getItemIcon, getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'
import StatBar from './StatBar.vue'

interface Entity {
  id: string
  name: string
  image_url?: string | null
  hp?: number
  max_hp?: number
  stamina?: number
  max_stamina?: number
  mana?: number
  max_mana?: number
  inventory?: any[]
}

defineProps<{
  npcs: Entity[]
  showImage: (path?: string | null) => boolean
  mode?: 'rpg' | 'story' | 'chat'
  isDebug?: boolean
}>()

const emit = defineEmits<{
  hover: [entity: Entity, event: MouseEvent]
  move: [event: MouseEvent]
  leave: []
  imageError: [path: string]
  contextmenu: [entity: Entity, event: MouseEvent]
  click: [entity: Entity]
}>()

const isOpen = ref(true)
</script>

<template>
  <div v-if="npcs.length > 0" class="mb-8">
    <button
      @click="isOpen = !isOpen"
      class="flex items-center gap-1.5 w-full text-left focus:outline-none cursor-pointer mb-4 select-none"
    >
      <ChevronDown v-if="isOpen" class="w-3.5 h-3.5 text-slate-500 transition-all shrink-0" />
      <ChevronRight v-else class="w-3.5 h-3.5 text-slate-500 transition-all shrink-0" />
      <i class="ra ra-venoms-trap text-cyan-500"></i>
      <h3 class="text-xs font-bold uppercase tracking-[0.2em] text-cyan-500/80">Population</h3>
    </button>
    <transition name="expand">
      <div v-show="isOpen" class="overflow-hidden">
        <div class="grid grid-cols-2 gap-3">
          <div
            v-for="ent in npcs"
            :key="ent.id"
            class="relative bg-slate-950/40 border border-slate-800/40 rounded-2xl group cursor-help transition-all hover:border-cyan-500/40 hover:bg-slate-900/50 p-2 flex flex-col items-center shadow-lg"
            @mouseenter="emit('hover', ent, $event)"
            @mousemove="emit('move', $event)"
            @mouseleave="emit('leave')"
            @contextmenu.prevent="emit('contextmenu', ent, $event)"
            @click="emit('click', ent)"
          >
            <div class="w-16 h-16 rounded-xl overflow-hidden border border-slate-800 bg-slate-900 flex items-center justify-center shrink-0 mb-2 relative">
              <!-- Defeated Ribbon -->
              <div v-if="ent.hp === 0" class="absolute -right-8 top-1 bg-red-600 text-white text-[8px] font-black uppercase tracking-[0.1em] py-0.5 w-24 text-center rotate-45 shadow-lg z-10">
                Defeated
              </div>
              <img
                v-if="ent.image_url && showImage(ent.image_url)"
                :src="getImageUrl(ent.image_url, { thumbnail: true })"
                class="w-full h-full object-cover object-top transition-all duration-500 group-hover:scale-110"
                :class="{ 'grayscale opacity-50': ent.hp === 0 }"
                @error="(e) => {
                  const target = e.target as HTMLImageElement
                  if (target.src.includes('_thumb')) {
                    target.src = getOriginalImageUrl(ent.image_url)
                  } else {
                    emit('imageError', ent.image_url!)
                  }
                }"
              />
              <div v-else class="w-full h-full flex items-center justify-center bg-slate-800/50" :class="{ 'grayscale opacity-40': ent.hp === 0 }">
                <i :class="['ra text-2xl', getItemIcon('NPC'), 'text-cyan-500/40']"></i>
              </div>
            </div>
            <span class="text-xs font-bold text-slate-400 group-hover:text-cyan-400 transition-colors uppercase tracking-tight truncate w-full text-center px-1 leading-tight">
              {{ ent.name }}
              <span v-if="isDebug" class="block text-[8px] font-mono opacity-50 mt-0.5">ID: {{ ent.id }}</span>
            </span>
            
            <!-- Very thin bars -->
            <div v-if="mode !== 'chat' && (ent.hp != null || ent.stamina != null || ent.mana != null)" class="w-full mt-1 px-1 flex flex-col gap-0.5 opacity-60 group-hover:opacity-100 transition-opacity">
              <StatBar v-if="ent.hp != null" :value="ent.hp" :max="ent.max_hp" color="crimson" size="xs" />
              <StatBar v-if="ent.stamina != null" :value="ent.stamina" :max="ent.max_stamina" color="emerald" size="xs" />
              <StatBar v-if="ent.mana != null && mode === 'rpg'" :value="ent.mana" :max="ent.max_mana" color="sapphire" size="xs" />
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
/* Collapsible expansion animation */
.expand-enter-active,
.expand-leave-active {
  transition: max-height 0.3s ease-out, opacity 0.3s ease-out;
  max-height: 500px;
}
.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>

