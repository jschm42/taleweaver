<script setup lang="ts">
const props = defineProps<{
  adventureCount: number
  isDeleting?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm'): void
}>()
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
    <div class="w-full max-w-md rounded-2xl bg-slate-900 border border-white/10 shadow-2xl overflow-hidden" @click.stop>
      <div class="px-6 py-5 border-b border-white/10 flex items-start gap-3">
        <div class="w-10 h-10 rounded-full bg-red-500/20 border border-red-500/40 flex items-center justify-center shrink-0">
          <i class="ra ra-burning-embers text-red-400"></i>
        </div>
        <div>
          <h3 class="text-lg font-black text-white font-display">Delete all adventures</h3>
          <p class="text-sm text-slate-300 mt-1">This action cannot be undone.</p>
        </div>
      </div>

      <div class="px-6 py-5">
        <p class="text-sm text-slate-200">
          Are you sure you want to delete all
          <span class="font-bold text-white">{{ props.adventureCount }}</span>
          adventures?
        </p>
      </div>

      <div class="px-6 py-4 border-t border-white/10 flex justify-end gap-3">
        <button
          class="px-4 py-2 rounded-lg border border-white/15 text-slate-300 text-sm font-bold hover:bg-white/5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="props.isDeleting"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          class="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-black uppercase tracking-widest hover:bg-red-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          :disabled="props.isDeleting"
          @click="emit('confirm')"
        >
          <span v-if="props.isDeleting" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
          {{ props.isDeleting ? 'Deleting...' : 'Delete all' }}
        </button>
      </div>
    </div>
  </div>
</template>
