<script setup lang="ts">
import { ref } from 'vue'
import { ChevronDown, ChevronRight } from 'lucide-vue-next'

defineProps<{
  memories: Array<{
    id: string
    timestamp: string
    description: string
    npc_id?: string | null
    emotion: 'positive' | 'negative' | 'neutral'
    scope?: 'local' | 'global'
    scene_id?: string | null
  }>
}>()

const isOpen = ref(false)
</script>

<template>
  <div class="mt-6 border-t border-slate-800/40 pt-6">
    <!-- Header/Toggle Button -->
    <button
      @click="isOpen = !isOpen"
      class="flex items-center gap-1.5 w-full text-left focus:outline-none cursor-pointer mb-4 select-none"
    >
      <ChevronDown v-if="isOpen" class="w-3.5 h-3.5 text-slate-500 transition-all shrink-0" />
      <ChevronRight v-else class="w-3.5 h-3.5 text-slate-500 transition-all shrink-0" />
      <i class="ra ra-quill text-amber-500 group-hover:scale-110 transition-transform"></i>
      <h3 class="text-xs font-bold uppercase tracking-[0.2em] text-amber-500/80">
        World Memories
      </h3>
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
                mem.scope === 'local' ? 'border-dashed border-opacity-70' : '',
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
                <div class="flex items-center justify-between mt-1.5 text-[8px] uppercase tracking-wider select-none">
                  <span 
                    :class="[
                      'flex items-center gap-1 font-semibold',
                      mem.scope === 'local' ? 'text-amber-500/60' : 'text-slate-500/60'
                    ]"
                  >
                    <i :class="mem.scope === 'local' ? 'ra ra-compass' : 'ra ra-world'"></i>
                    {{ mem.scope === 'local' ? 'Szenen-lokal' : 'Global' }}
                  </span>
                </div>
              </div>
            </div>
          </transition-group>
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
  max-height: 500px;
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
