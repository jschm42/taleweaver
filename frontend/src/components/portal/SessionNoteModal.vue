<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { FileText, X } from 'lucide-vue-next'

const props = defineProps<{
  initialNote: string
  isSaving?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', note: string): void
}>()

const note = ref('')
const maxChars = 500

onMounted(() => {
  note.value = props.initialNote
})
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
    <div class="w-full max-w-md rounded-2xl bg-slate-900 border border-white/10 shadow-2xl overflow-hidden" @click.stop>
      <!-- Header -->
      <div class="px-6 py-5 border-b border-white/10 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-full bg-amber-500/20 border border-amber-500/40 flex items-center justify-center shrink-0">
            <FileText class="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <h3 class="text-lg font-black text-white font-display">Session Note</h3>
            <p class="text-xs text-slate-400">Add status notes to remember your progress.</p>
          </div>
        </div>
        <button 
          class="text-slate-400 hover:text-white transition-colors"
          @click="emit('close')"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Content -->
      <div class="px-6 py-5 flex flex-col gap-4">
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-black uppercase tracking-widest text-slate-400">Note Content</label>
          <textarea
            v-model="note"
            :maxlength="maxChars"
            rows="6"
            class="w-full bg-black/30 border border-white/10 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500/50 resize-none transition-colors"
            placeholder="Type your notes here... (e.g. 'Paused before entering the dragon's lair', 'Got new magic sword')"
          ></textarea>
          <div class="flex justify-end">
            <span 
              class="text-[10px] font-bold transition-colors"
              :class="note.length >= maxChars ? 'text-red-400' : 'text-slate-500'"
            >
              {{ note.length }}/{{ maxChars }}
            </span>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-6 py-4 border-t border-white/10 flex justify-end gap-3">
        <button
          class="px-4 py-2 rounded-lg border border-white/15 text-slate-300 text-sm font-bold hover:bg-white/5 transition-colors"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          class="px-5 py-2 rounded-lg bg-amber-500 text-slate-950 text-sm font-black uppercase tracking-widest hover:bg-amber-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          :disabled="props.isSaving"
          @click="emit('save', note)"
        >
          <span v-if="props.isSaving" class="w-4 h-4 border-2 border-slate-950/30 border-t-slate-950 rounded-full animate-spin"></span>
          {{ props.isSaving ? 'Saving...' : 'Save Note' }}
        </button>
      </div>
    </div>
  </div>
</template>
