<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  adventureTitle: string
  format: 'adz' | 'adv' | 'ads'
  progress: number
  errorMsg?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const statusText = computed(() => {
  if (props.errorMsg) return 'Export Failed'
  if (props.progress === 100) return 'Export Completed!'
  if (props.progress > 80) return 'Finalizing assets...'
  if (props.progress > 40) return props.format === 'ads' ? 'Downloading session archive...' : 'Downloading packages...'
  return props.format === 'ads' ? 'Preparing game state & files...' : 'Cleaning database & packing files...'
})

const isDone = computed(() => props.progress === 100)
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
    <div class="w-full max-w-md rounded-2xl bg-[#081425]/90 border border-white/10 shadow-[0_0_50px_rgba(78,222,163,0.15)] overflow-hidden font-ui">
      <!-- Header -->
      <div class="px-6 py-5 border-b border-white/10 flex items-start gap-4">
        <div 
          class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 border transition-all duration-300"
          :class="[
            props.errorMsg
              ? 'bg-red-500/20 border-red-500/40 text-red-400'
              : isDone
                ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.3)]'
                : 'bg-aether-primary/10 border-aether-primary/30 text-aether-primary animate-pulse'
          ]"
        >
          <i v-if="props.errorMsg" class="ra ra-warning text-xl"></i>
          <i v-else-if="isDone" class="ra ra-checkmark text-xl"></i>
          <i v-else class="ra ra-download text-xl"></i>
        </div>
        <div>
          <h3 class="text-lg font-black text-white font-display uppercase tracking-wider">
            Export {{ props.format === 'ads' ? 'Session' : 'Adventure' }}
          </h3>
          <p class="text-xs text-slate-400 mt-0.5">
            Format: <span class="font-bold text-aether-primary uppercase">{{ props.format }}</span>
          </p>
        </div>
      </div>

      <!-- Content -->
      <div class="px-6 py-6 flex flex-col gap-5">
        <div class="text-sm text-slate-300">
          {{ props.format === 'ads' ? 'Session' : 'Adventure' }}: <span class="font-bold text-white">"{{ props.adventureTitle }}"</span>
        </div>

        <div v-if="props.errorMsg" class="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs break-words">
          {{ props.errorMsg }}
        </div>

        <div v-else class="flex flex-col gap-2">
          <div class="flex justify-between items-center text-xs font-bold tracking-wide">
            <span class="text-slate-400 uppercase">{{ statusText }}</span>
            <span class="text-aether-primary font-black text-sm">{{ props.progress }}%</span>
          </div>

          <!-- Progress Bar Container -->
          <div class="w-full h-3 bg-slate-950/50 rounded-full border border-white/5 p-[1px] overflow-hidden">
            <div 
              class="h-full bg-gradient-to-r from-aether-primary to-emerald-400 rounded-full transition-all duration-300 shadow-[0_0_10px_rgba(78,222,163,0.5)]"
              :style="{ width: props.progress + '%' }"
            ></div>
          </div>
        </div>
      </div>

      <!-- Action Button Footer -->
      <div class="px-6 py-4 border-t border-white/10 flex justify-end">
        <button
          v-if="isDone || props.errorMsg"
          class="px-5 py-2 rounded-xl text-xs font-black uppercase tracking-widest transition-all duration-200 border"
          :class="[
            props.errorMsg
              ? 'bg-red-600 border-red-500 text-white hover:bg-red-500'
              : 'bg-emerald-600 border-emerald-500 text-white hover:bg-emerald-500 hover:shadow-[0_0_15px_rgba(16,185,129,0.4)]'
          ]"
          @click="emit('close')"
        >
          {{ props.errorMsg ? 'Close' : 'Finished' }}
        </button>
        <div v-else class="flex items-center gap-2 text-xxs font-bold uppercase tracking-wider text-slate-500">
          <span class="w-3 h-3 border-2 border-slate-500/30 border-t-slate-400 rounded-full animate-spin"></span>
          Preparing files...
        </div>
      </div>
    </div>
  </div>
</template>
