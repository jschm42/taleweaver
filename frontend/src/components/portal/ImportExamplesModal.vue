<script setup lang="ts">
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm'): void
}>()
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
    <div class="w-full max-w-md rounded-2xl bg-slate-900 border border-white/10 shadow-2xl overflow-hidden">
      <div class="px-6 py-5 border-b border-white/10 flex items-start gap-3">
        <div class="w-10 h-10 rounded-full bg-blue-500/20 border border-blue-500/40 flex items-center justify-center shrink-0">
          <i class="ra ra-book text-blue-400"></i>
        </div>
        <div>
          <h3 class="text-lg font-black text-white font-display">Seed Library</h3>
          <p class="text-sm text-slate-300 mt-1">Populate your collection.</p>
        </div>
      </div>

      <div class="px-6 py-5">
        <p class="text-sm text-slate-200">
          Would you like to import the bundled example adventures? This will add several classic templates to your library.
        </p>
      </div>

      <div class="px-6 py-4 border-t border-white/10 flex justify-end gap-3">
        <button
          class="px-4 py-2 rounded-lg border border-white/15 text-slate-300 text-sm font-bold hover:bg-white/5 transition-colors"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          class="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-black uppercase tracking-widest hover:bg-blue-500 transition-colors"
          @click="emit('confirm')"
        >
          Import
        </button>
      </div>
    </div>
  </div>
</template>
