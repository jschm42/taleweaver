<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'

const props = defineProps<{
  open: boolean
  inventory: any[]
}>()

const emit = defineEmits<{
  close: []
  itemClick: [name: string]
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
}>()

const modalRef = ref<HTMLElement | null>(null)
const position = ref({ x: 100, y: 100 })
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })

const handleMouseDown = (e: MouseEvent) => {
  if (!modalRef.value) return
  isDragging.value = true
  dragOffset.value = {
    x: e.clientX - position.value.x,
    y: e.clientY - position.value.y
  }
  window.addEventListener('mousemove', handleMouseMove)
  window.addEventListener('mouseup', handleMouseUp)
}

const handleMouseMove = (e: MouseEvent) => {
  if (!isDragging.value) return
  position.value = {
    x: e.clientX - dragOffset.value.x,
    y: e.clientY - dragOffset.value.y
  }
}

const handleMouseUp = () => {
  isDragging.value = false
  window.removeEventListener('mousemove', handleMouseMove)
  window.removeEventListener('mouseup', handleMouseUp)
}

const brokenImages = ref<Record<string, boolean>>({})
const handleImageError = (path?: string | null) => {
  if (!path) return
  brokenImages.value[path] = true
}
const showImage = (path?: string | null) => {
  return !!path && !brokenImages.value[path]
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.open) {
    emit('close')
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  // Default position: bottom right area
  position.value = {
    x: window.innerWidth - 450,
    y: window.innerHeight - 550
  }
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="pop">
      <div
        v-if="open"
        ref="modalRef"
        class="fixed z-[60] w-[400px] bg-slate-900/95 backdrop-blur-xl border border-slate-700/50 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] flex flex-col overflow-hidden select-none"
        :style="{ left: position.x + 'px', top: position.y + 'px' }"
      >
        <!-- Header / Drag Handle -->
        <div 
          class="bg-slate-950/60 px-4 py-3 border-b border-slate-800 flex items-center justify-between cursor-move active:cursor-grabbing"
          @mousedown="handleMouseDown"
        >
          <div class="flex items-center gap-2">
            <img src="@/assets/svg/medieval-leather-pouch.svg" class="h-5 w-5 brightness-110" />
            <span class="text-xs font-black text-slate-100 uppercase tracking-[0.2em]">Pouch</span>
            <span class="text-[10px] text-slate-500 font-bold ml-1">({{ inventory.length }}/18)</span>
          </div>
          <button 
            class="text-slate-500 hover:text-white transition-colors"
            @click="emit('close')"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>

        <!-- Content -->
        <div class="p-4 bg-slate-900/40">
          <div class="grid grid-cols-6 gap-3">
            <!-- We always show 18 slots (6x3) -->
            <div 
              v-for="idx in 18" 
              :key="idx"
              class="flex flex-col items-center gap-1.5 group"
            >
              <!-- Slot Box -->
              <div 
                class="w-12 h-12 rounded-xl border flex items-center justify-center transition-all relative shrink-0 shadow-lg"
                :class="[
                  inventory[idx-1] 
                    ? 'bg-slate-950 border-slate-700/50 hover:border-emerald-500/50 cursor-pointer active:scale-95' 
                    : 'bg-slate-800/20 border-slate-800/40'
                ]"
                @click="inventory[idx-1] && emit('itemClick', inventory[idx-1].name)"
                @mouseenter="inventory[idx-1] && emit('itemHover', inventory[idx-1], $event)"
                @mouseleave="emit('itemLeave')"
              >
                <template v-if="inventory[idx-1]">
                  <img 
                    v-if="inventory[idx-1].image_url && showImage(inventory[idx-1].image_url)" 
                    :src="getImageUrl(inventory[idx-1].image_url)" 
                    class="w-full h-full object-cover rounded-xl"
                    @error="handleImageError(inventory[idx-1].image_url)"
                  />
                  <div v-else class="flex items-center justify-center">
                    <i :class="['ra text-xl', getItemIcon(inventory[idx-1].item_type), getTypeColor(inventory[idx-1].item_type)]"></i>
                  </div>
                </template>
                <!-- Empty State -->
                <div v-else class="w-full h-full flex items-center justify-center opacity-10">
                   <i class="ra ra-pouch text-lg text-slate-600"></i>
                </div>
              </div>
              
              <!-- Mini Name -->
              <span 
                v-if="inventory[idx-1]" 
                class="text-[8px] font-bold text-slate-500 group-hover:text-emerald-400 transition-colors uppercase tracking-tight text-center truncate w-full px-0.5"
              >
                {{ inventory[idx-1].name }}
              </span>
              <div v-else class="h-2"></div>
            </div>
          </div>
        </div>

        <!-- Footer / Hint -->
        <div class="px-4 py-2 bg-slate-950/20 border-t border-slate-800/40 text-[9px] text-slate-600 font-bold uppercase tracking-widest text-center">
          Click item to use in chat
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.pop-enter-active, .pop-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.pop-enter-from, .pop-leave-to {
  opacity: 0;
  transform: scale(0.9) translateY(10px);
}

.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
