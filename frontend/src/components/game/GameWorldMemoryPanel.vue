<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  memories: Array<{
    id: string
    timestamp: string
    description: string
    npc_id?: string | null
    emotion: 'positive' | 'negative' | 'neutral'
  }>
  rumors: Array<{
    id: string
    timestamp: string
    text: string
    source_scene_id: string
    target_scene_ids: string[]
  }>
  isDebug?: boolean
}>()

const isOpen = ref(true)
const showDebugRumors = ref(false)
</script>

<template>
  <div class="mt-6 border-t border-slate-800/40 pt-6">
    <!-- Header/Toggle Button -->
    <button
      @click="isOpen = !isOpen"
      class="flex items-center justify-between w-full text-left group focus:outline-none cursor-pointer"
    >
      <div class="flex items-center gap-2">
        <i class="ra ra-quill text-amber-500 group-hover:scale-110 transition-transform"></i>
        <h3 class="text-xs font-bold uppercase tracking-[0.2em] text-amber-500/80 group-hover:text-amber-400 transition-colors">
          World Memories
        </h3>
      </div>
      <i
        :class="[
          'text-slate-500 group-hover:text-slate-300 transition-all duration-200 text-[10px] transform',
          isOpen ? 'rotate-180' : 'rotate-0'
        ]"
        class="ra ra-chevron-down"
      ></i>
    </button>

    <!-- Collapsible Container -->
    <transition name="expand">
      <div v-show="isOpen" class="mt-4 overflow-hidden">
        <!-- Memories List -->
        <div v-if="memories.length === 0" class="text-xs text-slate-500 italic py-2">
          No lasting memories recorded. Your deeds will shape the world.
        </div>
        <div v-else class="flex flex-col gap-2 max-h-64 overflow-y-auto pr-1 custom-scrollbar">
          <transition-group name="list">
            <div
              v-for="mem in memories"
              :key="mem.id"
              :class="[
                'p-3 rounded-xl border text-xs leading-relaxed transition-all shadow-md flex items-start gap-2.5',
                mem.emotion === 'positive'
                  ? 'bg-emerald-950/20 border-emerald-500/20 text-emerald-300/90 shadow-emerald-950/10'
                  : mem.emotion === 'negative'
                  ? 'bg-rose-950/20 border-rose-500/20 text-rose-300/90 shadow-rose-950/10'
                  : 'bg-slate-950/40 border-slate-800/40 text-slate-300/90 shadow-slate-950/10'
              ]"
            >
              <!-- Icon Indicator -->
              <span class="mt-0.5 shrink-0">
                <i
                  :class="[
                    'ra',
                    mem.emotion === 'positive'
                      ? 'ra-shield text-emerald-400'
                      : mem.emotion === 'negative'
                      ? 'ra-broken-shield text-rose-400'
                      : 'ra-pawn text-slate-400'
                  ]"
                ></i>
              </span>
              <!-- Content -->
              <div class="flex-grow min-w-0">
                <p>{{ mem.description }}</p>
              </div>
            </div>
          </transition-group>
        </div>

        <!-- Debug Rumors section -->
        <div v-if="isDebug" class="mt-4 border-t border-slate-850 pt-4">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-1.5 text-rose-500/80">
              <i class="ra ra-microphone text-xxs"></i>
              <span class="text-[10px] font-bold uppercase tracking-wider">Debug: Rumors</span>
            </div>
            <label class="relative inline-flex items-center cursor-pointer select-none">
              <input type="checkbox" v-model="showDebugRumors" class="sr-only peer" />
              <div class="w-7 h-4 bg-slate-805 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-500 after:border-slate-400 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-rose-500/60 peer-checked:after:bg-white"></div>
            </label>
          </div>
          
          <transition name="expand">
            <div v-show="showDebugRumors" class="space-y-1.5 max-h-48 overflow-y-auto custom-scrollbar">
              <div v-if="rumors.length === 0" class="text-[10px] text-slate-500 italic">
                No rumors circulating.
              </div>
              <div 
                v-else 
                v-for="rum in rumors" 
                :key="rum.id"
                class="bg-slate-950/60 border border-rose-500/10 p-2 rounded-lg text-[10px] text-slate-400 font-mono leading-snug"
              >
                <div class="text-[8px] font-bold text-rose-400 uppercase tracking-tight mb-0.5">
                  Source: {{ rum.source_scene_id }} &rarr; Target: {{ rum.target_scene_ids.join(', ') || '*' }}
                </div>
                <div>{{ rum.text }}</div>
              </div>
            </div>
          </transition>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* Collapsible expansion animation */
.expand-enter-active,
.expand-leave-active {
  transition: max-height 0.3s ease-out, opacity 0.3s ease-out;
  max-height: 300px;
}
.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
}

/* List animation */
.list-enter-active,
.list-leave-active {
  transition: all 0.4s ease;
}
.list-enter-from {
  opacity: 0;
  transform: translateX(-15px) scale(0.95);
}
.list-leave-to {
  opacity: 0;
  transform: translateX(15px) scale(0.95);
}
</style>
