<script setup lang="ts">
import { AlertTriangle } from 'lucide-vue-next'

defineProps<{
  form: any
  adventure: any
  toneCatalog: any[]
  editingField: string | null
  tempValue: string
  isSaving: boolean
  fixNewlines: (text: string) => string
}>()

const emit = defineEmits<{
  (e: 'save-changes'): void
  (e: 'start-edit', field: string, value: string): void
  (e: 'save-field'): void
  (e: 'cancel-edit'): void
  (e: 'update:tempValue', val: string): void
  (e: 'update:tone', val: string): void
  (e: 'update:mode', val: 'rpg' | 'story' | 'chat'): void
}>()
</script>

<template>
  <div class="space-y-10 animate-page-in">
    <div class="bg-slate-900/40 p-10 rounded-[3rem] border border-white/5 backdrop-blur-md shadow-2xl space-y-12">
      <div class="flex justify-between items-center">
        <div>
          <h2 class="text-2xl font-black text-white tracking-tight uppercase tracking-[0.2em]">Narrative Blueprint</h2>
          <p class="text-xs font-bold text-slate-500 uppercase tracking-widest">Adjust the soul and mechanics of your chronicles</p>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-10 border-b border-white/5 pb-10">
         <!-- Rule Enforcement -->
         <div class="space-y-4">
           <div class="flex justify-between items-center">
             <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Game Mechanics</label>
             <button v-if="form.rule_enforcement_mode !== adventure?.rule_enforcement_mode" @click="emit('save-changes')" class="text-xs font-bold text-emerald-500 uppercase tracking-widest hover:text-emerald-400 transition-colors">Save Mode</button>
           </div>
           <div class="flex bg-black/40 p-1 rounded-2xl border border-white/5 shadow-inner">
             <button 
               v-for="mode in (['rpg', 'story', 'chat'] as const)" 
               :key="mode" 
               @click="emit('update:mode', mode)"
               :class="[
                 'flex-1 py-3 rounded-xl text-xs font-black uppercase tracking-widest transition-all',
                 form.rule_enforcement_mode === mode ? 'bg-emerald-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'
               ]"
             >
               {{ mode === 'rpg' ? 'RPG (Exp)' : mode }}
             </button>
           </div>
           <div v-if="form.rule_enforcement_mode === 'rpg'" class="p-4 rounded-2xl border border-amber-500/30 bg-amber-500/5 flex items-start gap-4">
              <AlertTriangle class="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
              <p class="text-slate-400 text-[10px] leading-relaxed uppercase font-bold tracking-tight">
                <span class="text-amber-500 font-black">Warning:</span> Experimental mode. Combat and attribute checks may behave unexpectedly.
              </p>
           </div>
         </div>

         <!-- Narrative Tone -->
         <div class="space-y-4">
           <div class="flex justify-between items-center">
              <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Narrative Tone</label>
              <button v-if="form.selected_tone_id !== (adventure?.selected_tone || '')" @click="emit('save-changes')" class="text-xs font-bold text-emerald-500 uppercase tracking-widest hover:text-emerald-400 transition-colors">Apply Tone</button>
           </div>
           <div class="grid grid-cols-2 gap-3">
              <button 
                v-for="tone in toneCatalog" 
                :key="tone.id" 
                @click="emit('update:tone', tone.id)"
                class="relative h-14 rounded-xl overflow-hidden border-2 transition-all group"
                :class="form.selected_tone_id === tone.id ? 'border-emerald-500 ring-4 ring-emerald-500/20' : 'border-transparent hover:border-white/10'"
              >
                 <img :src="tone.image_url" class="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" />
                 <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-[1px] flex items-center justify-center group-hover:bg-slate-900/40 transition-colors">
                   <span class="text-[10px] font-black text-white uppercase tracking-[0.2em]">{{ tone.name }}</span>
                 </div>
              </button>
           </div>
         </div>
      </div>

      <div class="flex flex-col gap-10">
        <!-- Adventure Plot Section -->
        <div class="space-y-4">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Adventure Plot (Secret)</label>
          <div v-if="editingField === 'plot'" class="space-y-4 animate-fade-in">
            <textarea :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLTextAreaElement).value)" rows="10" class="w-full bg-black/60 border border-emerald-500/50 rounded-3xl px-8 py-6 text-lg text-slate-200 focus:ring-2 ring-emerald-500/20 outline-none transition-all leading-relaxed shadow-2xl resize-y min-h-[200px]" placeholder="The main plotline, hidden goals, and core narrative..."></textarea>
            <div class="flex gap-4">
              <button @click="emit('save-field')" :disabled="isSaving" class="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2">
                <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
                <span>Save Plot</span>
              </button>
              <button @click="emit('cancel-edit')" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all">Cancel</button>
            </div>
          </div>
          <div v-else @click="emit('start-edit', 'plot', form.plot)" class="group relative cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-[2rem] p-8 transition-all duration-300 shadow-inner">
            <div class="absolute top-6 right-8 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 text-emerald-500 text-xs font-black uppercase">
              <i class="ra ra-quill-pen"></i> Edit Plot
            </div>
            <p v-if="form.plot" class="text-lg text-slate-300 leading-relaxed whitespace-pre-wrap">{{ fixNewlines(form.plot) }}</p>
            <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-6">No plot defined. Click to weave the story.</p>
          </div>
        </div>

        <!-- Rules Section -->
        <div class="space-y-4">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Adventure Rules / Mechanics</label>
          <div v-if="editingField === 'rules'" class="space-y-4 animate-fade-in">
            <textarea :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLTextAreaElement).value)" rows="6" class="w-full bg-black/60 border border-emerald-500/50 rounded-3xl px-8 py-6 text-lg text-slate-200 focus:ring-2 ring-emerald-500/20 outline-none transition-all leading-relaxed shadow-2xl resize-y min-h-[150px]" placeholder="Special rules for this world..."></textarea>
            <div class="flex gap-4">
              <button @click="emit('save-field')" :disabled="isSaving" class="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2">
                <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
                <span>Save Rules</span>
              </button>
              <button @click="emit('cancel-edit')" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all">Cancel</button>
            </div>
          </div>
          <div v-else @click="emit('start-edit', 'rules', form.rules)" class="group relative cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-[2rem] p-8 transition-all duration-300 shadow-inner">
            <div class="absolute top-6 right-8 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 text-emerald-500 text-xs font-black uppercase">
              <i class="ra ra-quill-pen"></i> Edit Rules
            </div>
            <p v-if="form.rules" class="text-lg text-slate-300 leading-relaxed whitespace-pre-wrap">{{ fixNewlines(form.rules) }}</p>
            <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-6">No specific rules. Click to define world logic.</p>
          </div>
        </div>

        <!-- Session Intro Section -->
        <div class="space-y-4">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Session Intro Text (Shown Once)</label>
          <div v-if="editingField === 'intro_text'" class="space-y-4 animate-fade-in">
            <textarea :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLTextAreaElement).value)" rows="6" class="w-full bg-black/60 border border-emerald-500/50 rounded-3xl px-8 py-6 text-lg text-slate-200 focus:ring-2 ring-emerald-500/20 outline-none transition-all leading-relaxed shadow-2xl resize-y min-h-[150px]" placeholder="Optional opening system text for a newly started session..."></textarea>
            <div class="flex gap-4">
              <button @click="emit('save-field')" :disabled="isSaving" class="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2">
                <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
                <span>Save Intro</span>
              </button>
              <button @click="emit('cancel-edit')" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all">Cancel</button>
            </div>
          </div>
          <div v-else @click="emit('start-edit', 'intro_text', form.intro_text)" class="group relative cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-[2rem] p-8 transition-all duration-300 shadow-inner">
            <div class="absolute top-6 right-8 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 text-emerald-500 text-xs font-black uppercase">
              <i class="ra ra-quill-pen"></i> Edit Intro
            </div>
            <p v-if="form.intro_text" class="text-lg text-slate-300 leading-relaxed whitespace-pre-wrap">{{ fixNewlines(form.intro_text) }}</p>
            <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-6">No intro text set. Click to add a one-time session opener.</p>
          </div>
        </div>

        <!-- Walkthrough Section -->
        <div class="space-y-4">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">GM Walkthrough (Solution Path)</label>
          <div v-if="editingField === 'walkthrough'" class="space-y-4 animate-fade-in">
            <textarea :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLTextAreaElement).value)" rows="10" class="w-full bg-black/60 border border-emerald-500/50 rounded-3xl px-8 py-6 text-lg text-slate-200 focus:ring-2 ring-emerald-500/20 outline-none transition-all leading-relaxed shadow-2xl resize-y min-h-[200px]" placeholder="Step-by-step secret solution for the GM..."></textarea>
            <div class="flex gap-4">
              <button @click="emit('save-field')" :disabled="isSaving" class="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2">
                <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
                <span>Save Walkthrough</span>
              </button>
              <button @click="emit('cancel-edit')" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all">Cancel</button>
            </div>
          </div>
          <div v-else @click="emit('start-edit', 'walkthrough', form.walkthrough)" class="group relative cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-[2rem] p-8 transition-all duration-300 shadow-inner">
            <div class="absolute top-6 right-8 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 text-emerald-500 text-xs font-black uppercase">
              <i class="ra ra-quill-pen"></i> Edit Walkthrough
            </div>
            <p v-if="form.walkthrough" class="text-lg text-slate-300 leading-relaxed whitespace-pre-wrap">{{ fixNewlines(form.walkthrough) }}</p>
            <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-6">No walkthrough set. Click to define the path.</p>
          </div>
        </div>

        <!-- Director's TTS Notes Section -->
        <div class="space-y-4">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Director's Text-to-Speech Notes (Gemini TTS only)</label>
          <div v-if="editingField === 'tts_director_notes'" class="space-y-4 animate-fade-in">
            <textarea :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLTextAreaElement).value)" rows="8" class="w-full bg-black/60 border border-emerald-500/50 rounded-3xl px-8 py-6 text-lg text-slate-200 focus:ring-2 ring-emerald-500/20 outline-none transition-all leading-relaxed shadow-2xl resize-y min-h-[150px]" placeholder="Specific instructions for voice style, dynamics, and tone..."></textarea>
            <p class="text-[10px] text-slate-500 uppercase tracking-widest italic px-2">Note: These instructions only apply when using Gemini-based TTS models.</p>
            <div class="flex gap-4">
              <button @click="emit('save-field')" :disabled="isSaving" class="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2">
                <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
                <span>Save TTS Notes</span>
              </button>
              <button @click="emit('cancel-edit')" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all">Cancel</button>
            </div>
          </div>
          <div v-else @click="emit('start-edit', 'tts_director_notes', form.tts_director_notes)" class="group relative cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-[2rem] p-8 transition-all duration-300 shadow-inner">
            <div class="absolute top-6 right-8 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 text-emerald-500 text-xs font-black uppercase">
              <i class="ra ra-quill-pen"></i> Edit TTS Notes
            </div>
            <p v-if="form.tts_director_notes" class="text-lg text-slate-300 leading-relaxed whitespace-pre-wrap">{{ fixNewlines(form.tts_director_notes) }}</p>
            <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-6">No TTS notes set. Click to customize voice delivery.</p>
          </div>
        </div>

        <!-- Conditions -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-10">
          <div class="space-y-4">
            <label class="block text-xs font-black text-emerald-500/80 uppercase tracking-[0.3em]">Win Conditions</label>
            <div v-if="editingField === 'completed_condition'" class="space-y-4 animate-fade-in">
              <textarea :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLTextAreaElement).value)" rows="4" class="w-full bg-black/60 border border-emerald-500/50 rounded-2xl px-6 py-5 text-base text-slate-200 outline-none transition-all resize-y" placeholder="What must the player achieve?"></textarea>
              <div class="flex gap-4">
                <button @click="emit('save-field')" :disabled="isSaving" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-lg transition-all">Save</button>
                <button @click="emit('cancel-edit')" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-lg transition-all">Cancel</button>
              </div>
            </div>
            <div v-else @click="emit('start-edit', 'completed_condition', form.completed_condition)" class="group relative cursor-pointer bg-emerald-500/5 hover:bg-emerald-500/10 border border-emerald-500/10 hover:border-emerald-500/30 rounded-2xl p-6 transition-all duration-300">
              <p v-if="form.completed_condition" class="text-base text-slate-300 leading-relaxed whitespace-pre-wrap">{{ fixNewlines(form.completed_condition) }}</p>
              <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center">Define Victory Conditions</p>
            </div>
          </div>

          <div class="space-y-4">
            <label class="block text-xs font-black text-red-500/80 uppercase tracking-[0.3em]">Loss Conditions</label>
            <div v-if="editingField === 'gameover_condition'" class="space-y-4 animate-fade-in">
              <textarea :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLTextAreaElement).value)" rows="4" class="w-full bg-black/60 border border-red-500/50 rounded-2xl px-6 py-5 text-base text-slate-200 outline-none transition-all resize-y" placeholder="How can the adventure fail?"></textarea>
              <div class="flex gap-4">
                <button @click="emit('save-field')" :disabled="isSaving" class="px-6 py-2 bg-red-600 hover:bg-red-500 text-white text-xs font-black uppercase tracking-widest rounded-lg transition-all">Save</button>
                <button @click="emit('cancel-edit')" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-lg transition-all">Cancel</button>
              </div>
            </div>
            <div v-else @click="emit('start-edit', 'gameover_condition', form.gameover_condition)" class="group relative cursor-pointer bg-red-500/5 hover:bg-red-500/10 border border-red-500/10 hover:border-red-500/30 rounded-2xl p-6 transition-all duration-300">
              <p v-if="form.gameover_condition" class="text-base text-slate-300 leading-relaxed whitespace-pre-wrap">{{ fixNewlines(form.gameover_condition) }}</p>
              <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center">Define Failure Conditions</p>
            </div>
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

.animate-fade-in {
  animation: fadeIn 0.3s ease-out forwards;
}

@keyframes pageIn {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
