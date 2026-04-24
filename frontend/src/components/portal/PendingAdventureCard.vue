<script setup lang="ts">
import { X } from 'lucide-vue-next'

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
}>()
</script>

<template>
  <div class="adventure-card flex flex-col rounded-xl border border-white/10 bg-aether-surface/30 relative overflow-hidden group">
    <div class="absolute inset-0 animate-shimmer opacity-30 pointer-events-none"></div>
    
    <!-- Placeholder Cover Area -->
    <div class="aspect-[3/2] w-full bg-white/5 flex flex-col items-center justify-center border-b border-white/5 relative p-6 text-center">
      <div class="w-12 h-12 rounded-full bg-aether-primary/10 border border-aether-primary/20 flex items-center justify-center mb-3">
        <i
          :class="[
            'ra text-lg',
            props.pending.hasError ? 'ra-burning-embers text-red-400' : 'ra-cog text-aether-primary animate-spin',
          ]"
        ></i>
      </div>
      
      <span
        :class="[
          'px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border',
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
        @click="emit('cancel', props.pending.adventureId)"
        title="Abbrechen"
      >
        <X class="w-4 h-4" />
      </button>
    </div>

    <div class="p-6 flex-1 flex flex-col gap-2">
      <h3 class="text-2xl font-black text-white leading-tight tracking-tight line-clamp-1">{{ props.pending.title }}</h3>
      <p class="text-[10px] font-bold text-slate-500 uppercase tracking-widest line-clamp-2 leading-relaxed">
        {{ props.pending.status }}
      </p>

      <div class="mt-auto pt-4">
        <button
          v-if="props.pending.hasError"
          class="w-full px-3 py-3 rounded-lg bg-red-500/15 border border-red-500/30 text-red-300 text-[10px] font-black uppercase tracking-widest hover:bg-red-500/25 transition-colors"
          @click="emit('removeFailed', props.pending.adventureId, props.pending.kind)"
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
