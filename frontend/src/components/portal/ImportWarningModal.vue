<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  type: 'defaults' | 'samples'
  conflicts: Array<{ title: string; already_exists: boolean }>
  isImporting: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm'): void
}>()

const conflictList = computed(() => props.conflicts.filter(c => c.already_exists))
</script>

<template>
  <div class="fixed inset-0 z-[100] flex items-center justify-center p-6">
    <!-- Backdrop -->
    <div 
      class="absolute inset-0 bg-slate-950/80 backdrop-blur-md animate-fade-in"
      @click="emit('close')"
    ></div>

    <!-- Modal Content -->
    <div class="relative w-full max-w-lg bg-[#0a1120] border border-white/10 rounded-2xl shadow-2xl overflow-hidden animate-scale-in">
      <div class="p-8">
        <!-- Icon & Header -->
        <div class="flex items-center gap-6 mb-8">
          <div class="w-16 h-16 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-500 text-3xl">
            <i class="ra ra-warning"></i>
          </div>
          <div>
            <h3 class="text-2xl font-black text-white tracking-tight leading-tight">
              Adventures already exist
            </h3>
            <p class="text-slate-400 text-sm mt-1">
              Some of the adventures you are about to import are already in your library.
            </p>
          </div>
        </div>

        <!-- Conflict List -->
        <div class="bg-white/5 rounded-xl border border-white/10 p-4 mb-8 max-h-48 overflow-y-auto">
          <ul class="space-y-3">
            <li 
              v-for="item in conflictList" 
              :key="item.title"
              class="flex items-center gap-3 text-sm"
            >
              <i class="ra ra-book-tome text-amber-500/60"></i>
              <span class="text-slate-200 font-bold">{{ item.title }}</span>
              <span class="ml-auto text-[10px] uppercase tracking-widest text-slate-500 font-black">Existing</span>
            </li>
          </ul>
        </div>

        <p class="text-slate-400 text-sm mb-8 leading-relaxed">
          Importing them again will skip the duplicates to avoid confusion. Do you want to proceed with the import?
        </p>

        <!-- Actions -->
        <div class="flex items-center justify-end gap-4">
          <button
            @click="emit('close')"
            class="px-6 py-3 rounded-xl text-slate-400 font-bold text-sm hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            @click="emit('confirm')"
            :disabled="isImporting"
            class="px-8 py-3 rounded-xl bg-amber-500 text-slate-950 font-black text-xs uppercase tracking-widest hover:bg-amber-400 transition-all shadow-lg shadow-amber-500/20 disabled:opacity-50 flex items-center gap-3"
          >
            <span v-if="isImporting" class="w-4 h-4 border-2 border-slate-950/20 border-t-slate-950 rounded-full animate-spin"></span>
            {{ isImporting ? 'Importing...' : 'Proceed Anyway' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.3s ease-out;
}
.animate-scale-in {
  animation: scaleIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.95) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
</style>
