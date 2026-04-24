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
  <div class="adventure-card flex flex-col rounded-xl border border-white/10 bg-aether-surface/30 p-6 relative overflow-hidden group">
    <div class="absolute inset-0 animate-shimmer opacity-60"></div>
    <div class="relative z-10 flex-1 flex flex-col">
      <div class="flex items-center justify-between mb-4">
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
        
        <div class="flex items-center gap-2">
          <!-- Cancel Button -->
          <button
            v-if="!props.pending.hasError && props.pending.kind === 'creation'"
            class="p-1.5 rounded-lg bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all opacity-0 group-hover:opacity-100"
            @click="emit('cancel', props.pending.adventureId)"
            title="Abbrechen"
          >
            <X class="w-4 h-4" />
          </button>

          <i
            :class="[
              'ra text-lg',
              props.pending.hasError ? 'ra-burning-embers text-red-400' : 'ra-cog text-aether-primary animate-spin',
            ]"
          ></i>
        </div>
      </div>

      <h3 class="text-xl font-black text-white mb-2 font-display line-clamp-2">{{ props.pending.title }}</h3>
      <p class="text-sm text-slate-300/90 mb-5 flex-1">{{ props.pending.status }}</p>

      <div class="mt-auto">
        <button
          v-if="props.pending.hasError"
          class="w-full px-3 py-2 rounded-lg bg-red-500/15 border border-red-500/30 text-red-300 text-[11px] font-black uppercase tracking-widest hover:bg-red-500/25 transition-colors"
          @click="emit('removeFailed', props.pending.adventureId, props.pending.kind)"
        >
          Delete Adventure
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
