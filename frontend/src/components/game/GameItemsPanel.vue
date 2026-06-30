<script setup lang="ts">
import { ref } from 'vue'
import { ChevronDown, ChevronRight } from 'lucide-vue-next'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'

interface Entity {
  id: string
  name: string
  item_type?: string | null
  image_url?: string | null
  is_portable?: boolean
  is_read?: boolean
  [key: string]: unknown
}

const isReadable = (entity: Entity) => String(entity.item_type || '').toUpperCase() === 'READABLE'
const isRead = (entity: Entity) => Boolean(entity.is_read)

defineProps<{
  items: Entity[]
  showImage: (path?: string | null) => boolean
  isDebug?: boolean
}>()

const emit = defineEmits<{
  hover: [entity: Entity, event: MouseEvent]
  move: [event: MouseEvent]
  leave: []
  imageError: [path: string]
  takeDirect: [entity: Entity]
  contextmenu: [entity: Entity, event: MouseEvent]
  click: [entity: Entity]
}>()

const isOpen = ref(true)
</script>

<template>
  <div v-if="items.length > 0" class="mb-8">
    <button
      @click="isOpen = !isOpen"
      class="flex items-center gap-1.5 w-full text-left focus:outline-none cursor-pointer mb-4 select-none"
    >
      <ChevronDown v-if="isOpen" class="w-3.5 h-3.5 text-slate-500 transition-all shrink-0" />
      <ChevronRight v-else class="w-3.5 h-3.5 text-slate-500 transition-all shrink-0" />
      <h3 class="text-xs font-bold uppercase tracking-[0.2em] text-amber-500/80">Discovery</h3>
    </button>
    <transition name="expand">
      <div v-show="isOpen" class="overflow-hidden">
        <div class="grid grid-cols-2 gap-3">
          <div
            v-for="ent in items"
            :key="ent.id"
            class="relative bg-slate-950/40 border border-slate-800/40 rounded-2xl group transition-all hover:border-amber-500/40 hover:bg-slate-900/50 p-2 flex flex-col items-center shadow-lg"
            :class="ent.is_portable !== false ? 'cursor-pointer' : 'cursor-help'"
            @mouseenter="emit('hover', ent, $event)"
            @mousemove="emit('move', $event)"
            @mouseleave="emit('leave')"
            @click="emit('click', ent)"
            @contextmenu.prevent="emit('contextmenu', ent, $event)"
          >
            <div v-if="isReadable(ent)" class="absolute top-1.5 left-1.5 z-20 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border"
                 :class="isRead(ent) ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' : 'bg-amber-500/20 text-amber-200 border-amber-500/30'">
              {{ isRead(ent) ? 'READ' : 'NOTE' }}
            </div>
            <div class="w-12 h-12 rounded-xl overflow-hidden border border-slate-800 bg-slate-900 flex items-center justify-center shrink-0 mb-2">
              <img
                v-if="ent.image_url && showImage(ent.image_url)"
                :src="getImageUrl(ent.image_url)"
                class="w-full h-full object-cover object-top transition-transform duration-500 group-hover:scale-110"
                @error="emit('imageError', ent.image_url)"
              />
              <div v-else class="w-full h-full flex items-center justify-center bg-slate-800/50">
                <i :class="['ra text-xl', getItemIcon(ent.item_type ?? undefined), getTypeColor(ent.item_type ?? undefined)]"></i>
              </div>
            </div>
            <span class="text-xs font-bold text-slate-400 group-hover:text-amber-400 transition-colors uppercase tracking-tight truncate w-full text-center px-1 leading-tight">
              {{ ent.name }}
              <span class="block text-[9px] font-mono text-slate-500/70 mt-0.5 truncate" :title="ent.id">ID: {{ ent.id }}</span>
            </span>
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

