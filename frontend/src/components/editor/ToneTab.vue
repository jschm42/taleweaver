<script setup lang="ts">
import { Save, X } from 'lucide-vue-next'

const props = defineProps<{
  form: any
  adventure: any
  debugData: any
  toneCatalog: any[]
  isSaving: boolean
}>()

const emit = defineEmits<{
  (e: 'update:tone', val: string): void
  (e: 'save-changes'): void
}>()
</script>

<template>
  <section v-if="toneCatalog.length" class="space-y-6 bg-slate-900/40 p-8 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
     <div class="flex items-center justify-between">
        <div class="flex items-center gap-4">
           <div class="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
              <i class="ra ra-magic-wand text-indigo-500"></i>
           </div>
           <div>
              <h3 class="text-sm font-black text-white uppercase tracking-[0.2em]">Narrative Tone</h3>
              <p class="text-xs font-bold text-slate-500 uppercase tracking-widest">Choose the narrative voice and mood</p>
           </div>
        </div>
        <div v-if="form.selected_tone_id !== (adventure?.selected_tone || '')" class="flex items-center gap-2 animate-fade-in">
           <button @click="$emit('save-changes')" :disabled="isSaving" class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg disabled:opacity-50 flex items-center justify-center" title="Speichern">
              <i v-if="isSaving" class="ra ra-cycle animate-spin text-sm"></i>
              <Save v-else class="w-4 h-4" />
           </button>
           <button @click="$emit('update:tone', adventure?.selected_tone || '')" :disabled="isSaving" class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-xl transition-all flex items-center justify-center" title="Abbrechen">
              <X class="w-4 h-4" />
           </button>
        </div>
     </div>
       <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
            <button 
               v-for="tone in toneCatalog" 
               :key="tone.id" 
               @click="$emit('update:tone', tone.id)"
               class="relative aspect-4-5 rounded-2xl overflow-hidden border-2 transition-all duration-500 group"
               :class="form.selected_tone_id === tone.id ? 'border-indigo-500 ring-4 ring-indigo-500/20' : 'border-transparent hover:border-white/10'"
            >
                <img v-if="tone.image_url" :src="tone.image_url" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" />
                <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80 group-hover:opacity-40 transition-opacity"></div>
                <div class="absolute bottom-3 left-3 right-3">
                   <p class="text-[10px] font-black text-white uppercase tracking-tighter truncate">{{ tone.name }}</p>
                </div>
                <div v-if="form.selected_tone_id === tone.id" class="absolute top-2 right-2 w-5 h-5 bg-indigo-500 rounded-full flex items-center justify-center shadow-lg">
                   <i class="ra ra-checkmark text-[10px] text-white"></i>
                </div>
            </button>
       </div>
  </section>
</template>

<style scoped>
.aspect-4-5 { aspect-ratio: 4/5; }
</style>
