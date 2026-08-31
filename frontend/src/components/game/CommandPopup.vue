<script setup lang="ts">
import { computed, ref, watch } from 'vue'

interface GameCommand {
  id: string
  label: string
  description: string
  category: 'game' | 'debug'
}

const props = defineProps<{
  commands: GameCommand[]
  activeIndex: number
}>()

const emit = defineEmits(['select', 'close', 'update:activeIndex'])

const scrollContainer = ref<HTMLElement | null>(null)
const lastMouseX = ref(0)
const lastMouseY = ref(0)

watch(() => props.activeIndex, (newIdx) => {
  if (!scrollContainer.value) return
  const items = scrollContainer.value.querySelectorAll('.command-item')
  const activeItem = items[newIdx] as HTMLElement
  if (activeItem) {
    activeItem.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }
})

const handleMouseEnter = (e: MouseEvent, idx: number) => {
  // Only update if the mouse actually moved (prevents jumping during scroll)
  if (Math.abs(e.clientX - lastMouseX.value) > 2 || Math.abs(e.clientY - lastMouseY.value) > 2) {
    emit('update:activeIndex', idx)
  }
  lastMouseX.value = e.clientX
  lastMouseY.value = e.clientY
}

const handleSelect = (cmd: Command) => {
  emit('select', cmd.id)
}
</script>

<template>
  <div class="command-popup-container absolute bottom-full left-0 mb-2 w-80 max-h-96 overflow-hidden bg-slate-900/90 backdrop-blur-xl border border-slate-700/50 rounded-2xl shadow-2xl z-[100] animate-popup-in">
    <div class="p-3 border-b border-slate-800 bg-slate-950/50 flex items-center justify-between">
      <span class="text-xxs font-black uppercase tracking-[0.2em] text-emerald-500">Available Commands</span>
      <span class="text-[10px] text-slate-500 font-mono">ESC to close</span>
    </div>
    
    <div 
      ref="scrollContainer" 
      class="overflow-y-auto max-h-80 custom-scrollbar p-1"
      @mousemove="e => { lastMouseX = e.clientX; lastMouseY = e.clientY }"
    >
      <div 
        v-for="(cmd, idx) in commands" 
        :key="cmd.id"
        class="command-item group relative flex items-center gap-3 p-3 rounded-xl transition-all cursor-pointer"
        :class="[
          activeIndex === idx ? 'bg-emerald-500/10 border-emerald-500/30' : 'hover:bg-slate-800/50 border-transparent',
          'border'
        ]"
        @click="handleSelect(cmd)"
        @mouseenter="e => handleMouseEnter(e, idx)"
      >
        <!-- Selection Indicator -->
        <div 
          v-if="activeIndex === idx"
          class="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-emerald-500 rounded-r-full shadow-[0_0_10px_rgba(16,185,129,0.8)]"
        ></div>

        <!-- Content -->
        <div class="flex-grow min-w-0">
          <div class="flex items-center justify-between gap-2">
            <span 
              class="text-sm font-bold tracking-wide transition-colors"
              :class="activeIndex === idx ? 'text-white' : 'text-slate-300'"
            >
              {{ cmd.label }}
            </span>
            <span 
              v-if="cmd.category === 'debug'"
              class="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 uppercase font-black tracking-tighter"
            >
              Dev
            </span>
          </div>
          <p class="text-[11px] text-slate-500 line-clamp-1 italic mt-0.5">{{ cmd.description }}</p>
        </div>

        <!-- Confirm Key -->
        <div 
          v-if="activeIndex === idx"
          class="shrink-0 animate-fade-in"
        >
          <kbd class="px-1.5 py-0.5 rounded bg-slate-950 border border-slate-800 text-[10px] text-emerald-500 font-bold">ENTER</kbd>
        </div>
      </div>

      <!-- Empty State -->
      <div v-if="commands.length === 0" class="p-8 text-center">
        <i class="ra ra-search text-3xl text-slate-700 mb-2"></i>
        <p class="text-xs text-slate-500 italic">No matching commands found</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.command-popup-container {
  transform-origin: bottom left;
}

@keyframes popup-in {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.animate-popup-in {
  animation: popup-in 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

/* Ensure RPG Awesome icons render correctly */
.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
