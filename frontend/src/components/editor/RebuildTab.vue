<script setup lang="ts">
defineProps<{
  aiEditPrompt: string
  aiAutoVisualize: boolean
  isAiEditing: boolean
}>()

const emit = defineEmits<{
  (e: 'update:aiEditPrompt', val: string): void
  (e: 'update:aiAutoVisualize', val: boolean): void
  (e: 'run-ai-edit'): void
}>()
</script>

<template>
  <div class="space-y-10 animate-page-in">
    <div class="bg-slate-900/40 p-10 rounded-[3rem] border border-white/5 backdrop-blur-md shadow-2xl space-y-8">
      <div class="flex items-center gap-6">
        <div class="w-16 h-16 bg-emerald-500/10 rounded-2xl flex items-center justify-center border border-emerald-500/20 shadow-lg">
          <i class="ra ra-player-teleport text-emerald-500 text-3xl"></i>
        </div>
        <div>
          <h2 class="text-2xl font-black text-white tracking-tight uppercase">AI Reality Weaver</h2>
          <p class="text-xs font-bold text-slate-500 uppercase tracking-widest">Rebuild or expand your world using natural language</p>
        </div>
      </div>

      <div class="space-y-6">
         <div class="relative">
            <textarea 
              :value="aiEditPrompt"
              @input="emit('update:aiEditPrompt', ($event.target as HTMLTextAreaElement).value)"
              @keyup.enter.ctrl="emit('run-ai-edit')" 
              :disabled="isAiEditing"
              rows="4"
              class="w-full bg-black/40 border border-white/5 rounded-3xl px-8 py-6 text-lg text-white focus:border-emerald-500 outline-none transition-all disabled:opacity-50 shadow-inner" 
              placeholder="Tell the Weaver to change reality... (e.g. 'Add a hidden basement to the tavern with a smuggler NPC')" 
            ></textarea>
            <div class="absolute bottom-6 right-8 text-xs font-bold text-slate-600 uppercase tracking-widest">Ctrl + Enter to Execute</div>
         </div>

         <div class="flex flex-wrap items-center justify-between gap-6">
            <div class="flex bg-black/60 p-1 rounded-2xl border border-white/5 shadow-inner">
              <button 
                @click="emit('update:aiAutoVisualize', false)" 
                :class="['px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all', !aiAutoVisualize ? 'bg-slate-800 text-white shadow-lg' : 'text-slate-500 hover:text-slate-400']"
              >
                Text Only
              </button>
              <button 
                @click="emit('update:aiAutoVisualize', true)" 
                :class="['px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all flex items-center gap-2', aiAutoVisualize ? 'bg-emerald-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-400']"
              >
                <i class="ra ra-eye-shield"></i>
                Visuals
              </button>
            </div>

            <button @click="emit('run-ai-edit')" :disabled="isAiEditing || !aiEditPrompt" class="px-12 py-4 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-black uppercase tracking-widest rounded-2xl disabled:opacity-50 transition-all shadow-xl shadow-emerald-900/40 flex items-center gap-4">
              <i v-if="isAiEditing" class="ra ra-cycle animate-spin"></i>
              <span>{{ isAiEditing ? 'Weaving Reality...' : 'Execute Command' }}</span>
            </button>
         </div>
      </div>

      <!-- Helpful Hints -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 pt-8 border-t border-white/5">
        <div v-for="hint in [
          { icon: 'ra-quill-ink', title: 'Content', desc: 'Add new scenes, NPCs, or items' },
          { icon: 'ra-cycle', title: 'Refine', desc: 'Modify existing descriptions or connections' },
          { icon: 'ra-crystal-ball', title: 'Logic', desc: 'Establish new rules or hidden secrets' }
        ]" :key="hint.title" class="flex gap-4">
          <i :class="['ra', hint.icon, 'text-emerald-500/50 mt-1']"></i>
          <div>
            <h4 class="text-xs font-black text-slate-400 uppercase tracking-widest mb-1">{{ hint.title }}</h4>
            <p class="text-xs text-slate-500 leading-relaxed">{{ hint.desc }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-page-in {
  animation: pageIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes pageIn {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
</style>
