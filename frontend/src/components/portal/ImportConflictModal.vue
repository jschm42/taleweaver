<script setup lang="ts">
interface ConflictInfo {
  title: string
  existing_version: string | null
  new_version: string | null
  template_id: string
}

const props = defineProps<{
  conflict: ConflictInfo
  isImporting?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm'): void
}>()
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
    <div class="w-full max-w-md rounded-2xl bg-slate-900 border border-white/10 shadow-2xl overflow-hidden">
      <div class="px-6 py-5 border-b border-white/10 flex items-start gap-3">
        <div class="w-10 h-10 rounded-full bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center shrink-0">
          <i class="ra ra-double-team text-cyan-400"></i>
        </div>
        <div>
          <h3 class="text-lg font-black text-white font-display">Adventure Conflict</h3>
          <p class="text-sm text-slate-300 mt-1">This adventure already exists in your library.</p>
        </div>
      </div>

      <div class="px-6 py-5 space-y-4">
        <p class="text-sm text-slate-200">
          The adventure <span class="font-bold text-white">"{{ props.conflict.title }}"</span> is already present. 
          Do you want to replace it with the new version?
        </p>

        <div v-if="props.conflict.existing_version || props.conflict.new_version" class="grid grid-cols-2 gap-4 bg-slate-800/50 rounded-xl p-4 border border-white/5">
          <div class="space-y-1">
            <span class="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Existing</span>
            <div class="text-sm font-mono text-cyan-300">{{ props.conflict.existing_version || 'Not set' }}</div>
          </div>
          <div class="space-y-1">
            <span class="text-[10px] uppercase font-bold text-slate-500 tracking-wider">New</span>
            <div class="text-sm font-mono text-emerald-400">{{ props.conflict.new_version || 'Not set' }}</div>
          </div>
        </div>
        
        <p class="text-xs text-red-400 italic">
          <i class="ra ra-warning mr-1"></i>
          Warning: Replacing will delete the existing adventure and all its associated game sessions.
        </p>
      </div>

      <div class="px-6 py-4 border-t border-white/10 flex justify-end gap-3">
        <button
          class="px-4 py-2 rounded-lg border border-white/15 text-slate-300 text-sm font-bold hover:bg-white/5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="props.isImporting"
          @click="emit('close')"
        >
          Keep Existing
        </button>
        <button
          class="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-black uppercase tracking-widest hover:bg-emerald-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          :disabled="props.isImporting"
          @click="emit('confirm')"
        >
          <span v-if="props.isImporting" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
          {{ props.isImporting ? 'Importing...' : 'Replace' }}
        </button>
      </div>
    </div>
  </div>
</template>
