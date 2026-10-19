<script setup lang="ts">
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import { formatObjectIds } from '@/utils/editor_utils'

defineProps<{
  form: any
  adventure: any
  editingField: string | null
  tempValue: string
  isSaving: boolean
  isGeneratingField?: Record<string, boolean>
  fixNewlines: (text: string) => string
  referenceOptions?: Array<{ id: string; name?: string; imageUrl?: string | null }>
}>()

const emit = defineEmits<{
  (e: 'save-changes'): void
  (e: 'start-edit', field: string, value: string): void
  (e: 'save-field'): void
  (e: 'cancel-edit'): void
  (e: 'generate-field', field: string): void
  (e: 'update:tempValue', val: string): void
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
               {{ mode === 'rpg' ? 'RPG' : mode }}
             </button>
           </div>
         </div>

         
      </div>

      <div class="flex flex-col gap-10">
        <!-- Adventure Plot Section -->
        <div class="space-y-4">
          <div class="flex justify-between items-center">
            <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Adventure Plot (Secret)</label>
            <span v-if="editingField === 'plot'" :class="['text-[10px] font-bold tracking-widest', tempValue.length > 5000 ? 'text-red-500' : 'text-emerald-500/50']">
              {{ tempValue.length }} / 5000
            </span>
          </div>
          <div v-if="editingField === 'plot'" class="space-y-4 animate-fade-in">
            <ReferenceTextarea
              :model-value="tempValue"
              :rows="10"
              :options="referenceOptions || []"
              class-name="w-full bg-black/60 border border-emerald-500/50 rounded-3xl px-8 py-6 text-lg text-slate-200 focus:ring-2 ring-emerald-500/20 outline-none transition-all leading-relaxed shadow-2xl resize-y min-h-[200px]"
              placeholder="The main plotline, hidden goals, and core narrative..."
              @update:model-value="emit('update:tempValue', $event)"
            />
            <div class="flex gap-4">
              <button @click="emit('save-field')" :disabled="isSaving || isGeneratingField?.['plot'] || tempValue.length > 5000" class="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2">
                <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
                <span>Save Plot</span>
              </button>
              <button type="button" @click="emit('generate-field', 'plot')" :disabled="isSaving || isGeneratingField?.['plot']" class="px-6 py-2 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all flex items-center gap-2">
                <i class="ra ra-crystals" :class="{ 'animate-spin': isGeneratingField?.['plot'] }"></i>
                <span>AI Generate</span>
              </button>
              <button @click="emit('cancel-edit')" :disabled="isGeneratingField?.['plot']" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all">Cancel</button>
            </div>
          </div>
          <div v-else @click="emit('start-edit', 'plot', form.plot)" class="group relative cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-[2rem] p-8 transition-all duration-300 shadow-inner">
            <div class="absolute top-6 right-8 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 text-emerald-500 text-xs font-black uppercase">
              <i class="ra ra-quill-pen"></i> Edit Plot
            </div>
            <p v-if="form.plot" class="text-lg text-slate-300 leading-relaxed whitespace-pre-wrap" v-html="formatObjectIds(form.plot)"></p>
            <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-6">No plot defined. Click to weave the story.</p>
          </div>
        </div>

        <!-- Rules Section -->
        <div class="space-y-4">
          <div class="flex justify-between items-center">
            <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Adventure Rules / Mechanics</label>
            <span v-if="editingField === 'rules'" :class="['text-[10px] font-bold tracking-widest', tempValue.length > 5000 ? 'text-red-500' : 'text-emerald-500/50']">
              {{ tempValue.length }} / 5000
            </span>
          </div>
          <div v-if="editingField === 'rules'" class="space-y-4 animate-fade-in">
            <ReferenceTextarea
              :model-value="tempValue"
              :rows="6"
              :options="referenceOptions || []"
              class-name="w-full bg-black/60 border border-emerald-500/50 rounded-3xl px-8 py-6 text-lg text-slate-200 focus:ring-2 ring-emerald-500/20 outline-none transition-all leading-relaxed shadow-2xl resize-y min-h-[150px]"
              placeholder="Special rules for this world..."
              @update:model-value="emit('update:tempValue', $event)"
            />
            <div class="flex gap-4">
              <button @click="emit('save-field')" :disabled="isSaving || isGeneratingField?.['rules'] || tempValue.length > 5000" class="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2">
                <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
                <span>Save Rules</span>
              </button>
              <button type="button" @click="emit('generate-field', 'rules')" :disabled="isSaving || isGeneratingField?.['rules']" class="px-6 py-2 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all flex items-center gap-2">
                <i class="ra ra-crystals" :class="{ 'animate-spin': isGeneratingField?.['rules'] }"></i>
                <span>AI Generate</span>
              </button>
              <button @click="emit('cancel-edit')" :disabled="isGeneratingField?.['rules']" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all">Cancel</button>
            </div>
          </div>
          <div v-else @click="emit('start-edit', 'rules', form.rules)" class="group relative cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-[2rem] p-8 transition-all duration-300 shadow-inner">
            <div class="absolute top-6 right-8 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 text-emerald-500 text-xs font-black uppercase">
              <i class="ra ra-quill-pen"></i> Edit Rules
            </div>
            <p v-if="form.rules" class="text-lg text-slate-300 leading-relaxed whitespace-pre-wrap" v-html="formatObjectIds(form.rules)"></p>
            <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-6">No specific rules. Click to define world logic.</p>
          </div>
        </div>

        <!-- Session Intro Section -->
        <div class="space-y-4">
          <div class="flex justify-between items-center">
            <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Session Intro Text (Shown Once)</label>
            <span v-if="editingField === 'intro_text'" :class="['text-[10px] font-bold tracking-widest', tempValue.length > 20000 ? 'text-red-500' : 'text-emerald-500/50']">
              {{ tempValue.length }} / 20000
            </span>
          </div>
          <div v-if="editingField === 'intro_text'" class="space-y-4 animate-fade-in">
            <ReferenceTextarea
              :model-value="tempValue"
              :rows="6"
              :options="referenceOptions || []"
              class-name="w-full bg-black/60 border border-emerald-500/50 rounded-3xl px-8 py-6 text-lg text-slate-200 focus:ring-2 ring-emerald-500/20 outline-none transition-all leading-relaxed shadow-2xl resize-y min-h-[150px]"
              placeholder="Optional opening system text for a newly started session..."
              @update:model-value="emit('update:tempValue', $event)"
            />
            <div class="flex gap-4">
              <button @click="emit('save-field')" :disabled="isSaving || isGeneratingField?.['intro_text'] || tempValue.length > 20000" class="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2">
                <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
                <span>Save Intro</span>
              </button>
              <button type="button" @click="emit('generate-field', 'intro_text')" :disabled="isSaving || isGeneratingField?.['intro_text']" class="px-6 py-2 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all flex items-center gap-2">
                <i class="ra ra-crystals" :class="{ 'animate-spin': isGeneratingField?.['intro_text'] }"></i>
                <span>AI Generate</span>
              </button>
              <button @click="emit('cancel-edit')" :disabled="isGeneratingField?.['intro_text']" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all">Cancel</button>
            </div>
          </div>
          <div v-else @click="emit('start-edit', 'intro_text', form.intro_text)" class="group relative cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-[2rem] p-8 transition-all duration-300 shadow-inner">
            <div class="absolute top-6 right-8 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 text-emerald-500 text-xs font-black uppercase">
              <i class="ra ra-quill-pen"></i> Edit Intro
            </div>
            <p v-if="form.intro_text" class="text-lg text-slate-300 leading-relaxed whitespace-pre-wrap" v-html="formatObjectIds(form.intro_text)"></p>
            <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-6">No intro text set. Click to add a one-time session opener.</p>
          </div>
        </div>

        <!-- Conditions -->
        <div class="space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-black text-slate-400 uppercase tracking-[0.25em] flex items-center gap-2">
              <i class="ra ra-trophy text-emerald-400"></i> Outcome Criteria (Victory & Defeat)
            </h3>
            <span class="text-[11px] text-slate-500 font-medium">
              Best Practice: Use either a soft narrative rule OR a scripted guard per outcome, but not both.
            </span>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-10">
            <!-- WIN CONDITIONS COLUMN -->
            <div class="space-y-6 bg-slate-950/40 p-6 rounded-3xl border border-emerald-500/20">
              <div class="flex justify-between items-center">
                <div class="flex items-center gap-2">
                  <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
                  <label class="text-xs font-black text-emerald-400 uppercase tracking-[0.3em]">Win Conditions</label>
                </div>
                <span v-if="form.completed_condition && form.completed_guard_expression" class="text-[10px] text-amber-400 font-bold px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20">
                  Dual rules configured
                </span>
              </div>

              <!-- Soft Rule (completed_condition) -->
              <div class="space-y-2">
                <div class="flex justify-between items-center">
                  <div class="flex items-center gap-2">
                    <span class="text-[10px] font-bold tracking-widest uppercase text-slate-400">Soft Rule</span>
                    <span class="text-[9px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 font-mono">AI GM Evaluated</span>
                  </div>
                  <span v-if="editingField === 'completed_condition'" :class="['text-[10px] font-bold tracking-widest', tempValue.length > 2000 ? 'text-red-500' : 'text-emerald-500/50']">
                    {{ tempValue.length }} / 2000
                  </span>
                </div>

                <div v-if="editingField === 'completed_condition'" class="space-y-4 animate-fade-in">
                  <ReferenceTextarea
                    :model-value="tempValue"
                    :rows="4"
                    :options="referenceOptions || []"
                    class-name="w-full bg-black/60 border border-emerald-500/50 rounded-2xl px-6 py-5 text-base text-slate-200 outline-none transition-all resize-y"
                    placeholder="Describe how the player achieves victory in prose..."
                    @update:model-value="emit('update:tempValue', $event)"
                  />
                  <div class="flex gap-4">
                    <button @click="emit('save-field')" :disabled="isSaving || isGeneratingField?.['completed_condition'] || tempValue.length > 2000" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-lg transition-all">Save</button>
                    <button type="button" @click="emit('generate-field', 'completed_condition')" :disabled="isSaving || isGeneratingField?.['completed_condition']" class="px-4 py-2 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-400 text-xs font-black uppercase tracking-widest rounded-lg transition-all flex items-center gap-2">
                      <i class="ra ra-crystals" :class="{ 'animate-spin': isGeneratingField?.['completed_condition'] }"></i>
                      <span>AI Generate</span>
                    </button>
                    <button @click="emit('cancel-edit')" :disabled="isGeneratingField?.['completed_condition']" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-lg transition-all">Cancel</button>
                  </div>
                </div>
                <div v-else @click="emit('start-edit', 'completed_condition', form.completed_condition)" class="group relative cursor-pointer bg-emerald-500/5 hover:bg-emerald-500/10 border border-emerald-500/10 hover:border-emerald-500/30 rounded-2xl p-4 transition-all duration-300">
                  <p v-if="form.completed_condition" class="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap" v-html="formatObjectIds(form.completed_condition)"></p>
                  <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-2">Click to set soft victory condition</p>
                </div>
              </div>

              <!-- Hard Rule Guard (completed_guard_expression) -->
              <div class="space-y-2 pt-2 border-t border-emerald-500/10">
                <div class="flex justify-between items-center">
                  <div class="flex items-center gap-2">
                    <span class="text-[10px] font-bold tracking-widest uppercase text-emerald-400">Hard Rule Guard</span>
                    <span class="text-[9px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 font-mono">Deterministic Engine</span>
                  </div>
                  <span v-if="editingField === 'completed_guard_expression'" :class="['text-[10px] font-bold tracking-widest', tempValue.length > 2000 ? 'text-red-500' : 'text-emerald-500/50']">
                    {{ tempValue.length }} / 2000
                  </span>
                </div>

                <div v-if="editingField === 'completed_guard_expression'" class="space-y-3 animate-fade-in">
                  <ScriptEditor
                    :model-value="tempValue"
                    label="Win Guard Expression (Safe Python)"
                    help-text="Deterministic boolean condition evaluated by the engine. Must evaluate to True for victory."
                    context="guard_expression"
                    placeholder="e.g. tw.vars.get('boss_defeated') == True and tw.player.has_item('MOB_LEDGER')"
                    min-height="80px"
                    @update:model-value="emit('update:tempValue', $event)"
                  />
                  <div class="flex gap-4">
                    <button @click="emit('save-field')" :disabled="isSaving || tempValue.length > 2000" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-lg transition-all">Save Guard</button>
                    <button @click="emit('cancel-edit')" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-lg transition-all">Cancel</button>
                  </div>
                </div>
                <div v-else @click="emit('start-edit', 'completed_guard_expression', form.completed_guard_expression)" class="group relative cursor-pointer bg-slate-900/80 hover:bg-slate-900 border border-emerald-500/20 hover:border-emerald-500/40 rounded-2xl p-4 transition-all duration-300 font-mono">
                  <div v-if="form.completed_guard_expression" class="flex items-center gap-2 text-xs text-emerald-300">
                    <i class="ra ra-shield text-emerald-400"></i>
                    <code class="text-xs break-all">{{ form.completed_guard_expression }}</code>
                  </div>
                  <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-2 font-sans">Click to set scripted win guard</p>
                </div>
              </div>
            </div>

            <!-- LOSS CONDITIONS COLUMN -->
            <div class="space-y-6 bg-slate-950/40 p-6 rounded-3xl border border-red-500/20">
              <div class="flex justify-between items-center">
                <div class="flex items-center gap-2">
                  <span class="w-2.5 h-2.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"></span>
                  <label class="text-xs font-black text-red-400 uppercase tracking-[0.3em]">Loss Conditions</label>
                </div>
                <span v-if="form.gameover_condition && form.gameover_guard_expression" class="text-[10px] text-amber-400 font-bold px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20">
                  Dual rules configured
                </span>
              </div>

              <!-- Soft Rule (gameover_condition) -->
              <div class="space-y-2">
                <div class="flex justify-between items-center">
                  <div class="flex items-center gap-2">
                    <span class="text-[10px] font-bold tracking-widest uppercase text-slate-400">Soft Rule</span>
                    <span class="text-[9px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 font-mono">AI GM Evaluated</span>
                  </div>
                  <span v-if="editingField === 'gameover_condition'" :class="['text-[10px] font-bold tracking-widest', tempValue.length > 2000 ? 'text-red-500' : 'text-emerald-500/50']">
                    {{ tempValue.length }} / 2000
                  </span>
                </div>

                <div v-if="editingField === 'gameover_condition'" class="space-y-4 animate-fade-in">
                  <ReferenceTextarea
                    :model-value="tempValue"
                    :rows="4"
                    :options="referenceOptions || []"
                    class-name="w-full bg-black/60 border border-red-500/50 rounded-2xl px-6 py-5 text-base text-slate-200 outline-none transition-all resize-y"
                    placeholder="Describe failure or death circumstances in prose..."
                    @update:model-value="emit('update:tempValue', $event)"
                  />
                  <div class="flex gap-4">
                    <button @click="emit('save-field')" :disabled="isSaving || isGeneratingField?.['gameover_condition'] || tempValue.length > 2000" class="px-6 py-2 bg-red-600 hover:bg-red-500 text-white text-xs font-black uppercase tracking-widest rounded-lg transition-all">Save</button>
                    <button type="button" @click="emit('generate-field', 'gameover_condition')" :disabled="isSaving || isGeneratingField?.['gameover_condition']" class="px-4 py-2 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-400 text-xs font-black uppercase tracking-widest rounded-lg transition-all flex items-center gap-2">
                      <i class="ra ra-crystals" :class="{ 'animate-spin': isGeneratingField?.['gameover_condition'] }"></i>
                      <span>AI Generate</span>
                    </button>
                    <button @click="emit('cancel-edit')" :disabled="isGeneratingField?.['gameover_condition']" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-lg transition-all">Cancel</button>
                  </div>
                </div>
                <div v-else @click="emit('start-edit', 'gameover_condition', form.gameover_condition)" class="group relative cursor-pointer bg-red-500/5 hover:bg-red-500/10 border border-red-500/10 hover:border-red-500/30 rounded-2xl p-4 transition-all duration-300">
                  <p v-if="form.gameover_condition" class="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap" v-html="formatObjectIds(form.gameover_condition)"></p>
                  <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-2">Click to set soft failure condition</p>
                </div>
              </div>

              <!-- Hard Rule Guard (gameover_guard_expression) -->
              <div class="space-y-2 pt-2 border-t border-red-500/10">
                <div class="flex justify-between items-center">
                  <div class="flex items-center gap-2">
                    <span class="text-[10px] font-bold tracking-widest uppercase text-red-400">Hard Rule Guard</span>
                    <span class="text-[9px] px-1.5 py-0.2 rounded bg-red-500/20 text-red-300 font-mono">Deterministic Engine</span>
                  </div>
                  <span v-if="editingField === 'gameover_guard_expression'" :class="['text-[10px] font-bold tracking-widest', tempValue.length > 2000 ? 'text-red-500' : 'text-emerald-500/50']">
                    {{ tempValue.length }} / 2000
                  </span>
                </div>

                <div v-if="editingField === 'gameover_guard_expression'" class="space-y-3 animate-fade-in">
                  <ScriptEditor
                    :model-value="tempValue"
                    label="Loss Guard Expression (Safe Python)"
                    help-text="Deterministic boolean condition evaluated by the engine. When True, immediately triggers Game Over."
                    context="guard_expression"
                    placeholder="e.g. tw.vars.get('countdown') <= 0 or tw.vars.get('cover_blown') == True"
                    min-height="80px"
                    @update:model-value="emit('update:tempValue', $event)"
                  />
                  <div class="flex gap-4">
                    <button @click="emit('save-field')" :disabled="isSaving || tempValue.length > 2000" class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-xs font-black uppercase tracking-widest rounded-lg transition-all">Save Guard</button>
                    <button @click="emit('cancel-edit')" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-lg transition-all">Cancel</button>
                  </div>
                </div>
                <div v-else @click="emit('start-edit', 'gameover_guard_expression', form.gameover_guard_expression)" class="group relative cursor-pointer bg-slate-900/80 hover:bg-slate-900 border border-red-500/20 hover:border-red-500/40 rounded-2xl p-4 transition-all duration-300 font-mono">
                  <div v-if="form.gameover_guard_expression" class="flex items-center gap-2 text-xs text-red-300">
                    <i class="ra ra-skull text-red-400"></i>
                    <code class="text-xs break-all">{{ form.gameover_guard_expression }}</code>
                  </div>
                  <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-2 font-sans">Click to set scripted loss guard</p>
                </div>
              </div>
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
