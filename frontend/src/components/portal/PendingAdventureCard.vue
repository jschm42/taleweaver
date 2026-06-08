<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { X } from 'lucide-vue-next'
import { GENERATION_SAYINGS } from '@/composables/useApi'

const props = defineProps<{
  pending: {
    adventureId: string
    title: string
    status: string
    hasError: boolean
    kind: 'creation' | 'import'
  }
  loadingWordIndex: number
}>()

const emit = defineEmits<{
  (e: 'removeFailed', adventureId: string, kind: 'creation' | 'import'): void
  (e: 'cancel', adventureId: string): void
  (e: 'click'): void
}>()

const currentSaying = ref(GENERATION_SAYINGS[Math.floor(Math.random() * GENERATION_SAYINGS.length)])
let sayingTimer: number | null = null

function updateSaying() {
  const randomIndex = Math.floor(Math.random() * GENERATION_SAYINGS.length)
  currentSaying.value = GENERATION_SAYINGS[randomIndex]
}

onMounted(() => {
  sayingTimer = window.setInterval(updateSaying, 5000)
})

onUnmounted(() => {
  if (sayingTimer) {
    clearInterval(sayingTimer)
  }
})
</script>

<template>
  <div 
    class="adventure-card flex flex-col rounded-xl border border-white/10 bg-aether-surface/30 relative overflow-hidden group cursor-pointer hover:border-aether-primary/40 hover:shadow-[0_0_20px_rgba(56,189,248,0.05)] transition-all duration-200"
    @click="emit('click')"
  >
    <div class="absolute inset-0 animate-shimmer opacity-30 pointer-events-none"></div>
    
    <!-- Placeholder Cover Area -->
    <div class="aspect-[3/2] w-full bg-white/5 flex flex-col items-center justify-center border-b border-white/5 relative p-4 sm:p-6 text-center">
      <div class="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-aether-primary/10 border border-aether-primary/20 flex items-center justify-center mb-2 sm:mb-3">
        <i
          :class="[
            'ra text-base sm:text-lg',
            props.pending.hasError ? 'ra-burning-embers text-red-400' : 'ra-cog text-aether-primary animate-spin',
          ]"
        ></i>
      </div>
      
      <span
        :class="[
          'px-3 py-1 rounded-full text-xs font-black uppercase tracking-widest border',
          props.pending.hasError
            ? 'bg-red-500/15 border-red-500/30 text-red-400'
            : 'bg-aether-primary/15 border-aether-primary/30 text-aether-primary',
        ]"
      >
        {{ props.pending.hasError ? (props.pending.status === 'Cancelled' ? 'Cancelled' : 'Failed') : (props.pending.kind === 'import' ? 'Import' : 'Generating') }}
      </span>

      <!-- Cancel Button -->
      <button
        v-if="!props.pending.hasError && props.pending.kind === 'creation'"
        class="absolute top-3 right-3 p-1.5 rounded-lg bg-black/40 border border-white/10 text-slate-400 hover:text-white hover:bg-black/60 transition-all opacity-0 group-hover:opacity-100"
        @click.stop="emit('cancel', props.pending.adventureId)"
        title="Abbrechen"
      >
        <X class="w-4 h-4" />
      </button>
    </div>

    <div class="p-4 sm:p-5 lg:p-6 flex-1 flex flex-col gap-2">
      <h3 class="text-lg sm:text-xl lg:text-2xl font-black text-white leading-tight tracking-tight line-clamp-1">{{ props.pending.title }}</h3>
      <p class="text-[11px] sm:text-xs font-bold text-slate-500 uppercase tracking-widest line-clamp-2 leading-relaxed min-h-[2rem]">
        {{ props.pending.hasError ? props.pending.status : currentSaying }}
      </p>
      
      <span
        v-if="!props.pending.hasError"
        class="text-[10px] font-bold text-sky-400/80 uppercase tracking-widest flex items-center gap-1.5 mt-1 animate-pulse"
      >
        <span class="w-1.5 h-1.5 rounded-full bg-sky-400"></span>
        Click for details
      </span>

      <div class="mt-auto pt-4">
        <button
          v-if="props.pending.hasError"
          class="w-full px-3 py-3 rounded-lg bg-red-500/15 border border-red-500/30 text-red-300 text-xs font-black uppercase tracking-widest hover:bg-red-500/25 transition-colors"
          @click.stop="emit('removeFailed', props.pending.adventureId, props.pending.kind)"
        >
          Remove Adventure
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-shimmer {
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0) 0%,
    rgba(255, 255, 255, 0.05) 50%,
    rgba(255, 255, 255, 0) 0%
  );
  background-size: 200% 100%;
  animation: shimmer 2s infinite linear;
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
</style>

