<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  gameForm: any
  isSubmitting: boolean
}>()

const emit = defineEmits<{
  (e: 'save', payload: any): void
}>()

const localForm = ref({ ...props.gameForm })

watch(() => props.gameForm, (newVal) => {
  localForm.value = { ...newVal }
}, { deep: true })
</script>

<template>
  <div class="space-y-6 animate-fade-in max-w-5xl">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-3xl font-extrabold text-white tracking-tight">Speech to Text (STT)</h1>
        <p class="text-slate-400 text-sm mt-1">Configure speech recognition and input models.</p>
      </div>

      <button 
        type="button" 
        @click="emit('save', localForm)" 
        :disabled="isSubmitting" 
        class="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-emerald-900/30 disabled:opacity-50 flex items-center gap-2 self-start sm:self-auto cursor-pointer"
      >
        <i v-if="isSubmitting" class="ra ra-recycle animate-spin"></i>
        <i v-else class="ra ra-save"></i>
        <span>{{ isSubmitting ? 'Saving...' : 'Save STT Settings' }}</span>
      </button>
    </div>

    <div class="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
      <div class="p-6 bg-slate-950/40 border border-slate-800/40 rounded-2xl space-y-6">
        <!-- Provider (Preselected / Read-only) -->
        <div class="flex items-center justify-between p-4 bg-slate-900/60 rounded-xl border border-white/5">
          <div>
            <div class="text-sm font-bold text-white">Speech-to-Text Provider</div>
            <div class="text-xs text-slate-500">Currently, only local Whisper is supported for STT.</div>
          </div>
          <span class="text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-lg">
            faster-whisper (Local)
          </span>
        </div>

        <!-- Speech-to-Text Model (Whisper) Settings -->
        <div class="flex items-center justify-between p-4 bg-slate-900/60 rounded-xl border border-white/5">
          <div>
            <div class="text-sm font-bold text-white">Whisper Model Size</div>
            <div class="text-xs text-slate-500">Choose the Whisper model size. Larger models are more accurate but consume more CPU/RAM.</div>
          </div>
          <select 
            v-model="localForm.whisper_model"
            class="bg-slate-950 border border-slate-800 text-white text-xs rounded-lg focus:ring-emerald-500 focus:border-emerald-500 block p-2 px-4 outline-none"
          >
            <option value="tiny">Tiny (Default - fastest)</option>
            <option value="base">Base</option>
            <option value="small">Small</option>
            <option value="medium">Medium</option>
            <option value="large">Large (slowest)</option>
          </select>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.4s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
