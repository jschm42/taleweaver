<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  show: boolean
  context: { type: string; id: string } | null
  initialForm: { name: string; teaser: string; description: string; hp: number; stamina: number; mana: number; voice: string }
  availableVoices: Array<{ name: string; gender?: string; description?: string }>
  ruleEnforcementMode: string
  isSaving: boolean
  formatVoiceOption: (voice: any) => string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', data: any): void
}>()

const localForm = ref({ ...props.initialForm })

watch(() => props.initialForm, (newVal) => {
  localForm.value = { ...newVal }
}, { deep: true })

function handleSave() {
  emit('save', { ...localForm.value })
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show && context" class="fixed inset-0 z-[200] flex items-center justify-center p-6 backdrop-blur-xl bg-slate-950/60">
        <div class="modal-content w-full max-w-2xl bg-slate-900 border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden">
          <div class="p-10 space-y-8">
            <div class="flex justify-between items-center">
              <div class="space-y-1">
                <h3 class="text-xs font-black text-emerald-500 uppercase tracking-widest">Editing {{ context.type }}</h3>
                <p class="text-slate-500 text-xs uppercase font-bold tracking-tighter">ID: {{ context.id }}</p>
              </div>
              <button @click="emit('close')" class="text-slate-500 hover:text-white transition-colors">
                <i class="ra ra-cancel text-xl"></i>
              </button>
            </div>

            <div class="space-y-6">
              <div class="space-y-3">
                <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Entity Name</label>
                <input v-model="localForm.name" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-2xl font-bold text-white focus:border-emerald-500 outline-none transition-all shadow-inner" />
              
              <!-- Stats Inputs -->
              <div v-if="['protagonist', 'npc'].includes(context.type) && ruleEnforcementMode !== 'chat'" class="grid grid-cols-3 gap-4">
                <div class="space-y-2">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Health (HP)</label>
                  <input v-model.number="localForm.hp" type="number" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-red-500/50 outline-none transition-all" />
                </div>
                <div class="space-y-2">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Stamina (STM)</label>
                  <input v-model.number="localForm.stamina" type="number" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-emerald-500/50 outline-none transition-all" />
                </div>
                <div v-if="ruleEnforcementMode === 'rpg'" class="space-y-2">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Mana (MAN)</label>
                  <input v-model.number="localForm.mana" type="number" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-blue-500/50 outline-none transition-all" />
                </div>
              </div>
              </div>
              
              <div v-if="context.type === 'cover'" class="space-y-3">
                <div class="flex justify-between items-center">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Teaser (Max 300 Characters)</label>
                  <span :class="['text-xs font-bold tracking-widest', localForm.teaser.length > 300 ? 'text-red-500' : 'text-emerald-500/50']">
                    {{ localForm.teaser.length }} / 300
                  </span>
                </div>
                <textarea v-model="localForm.teaser" rows="3" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner" placeholder="A short, catchy teaser for your adventure..."></textarea>
              </div>

              <div v-if="context.type === 'npc'" class="space-y-3">
                <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Voice</label>
                <select v-model="localForm.voice" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-3 text-sm text-slate-200 focus:border-emerald-500 outline-none transition-all shadow-inner">
                  <option value="">Default narrator voice</option>
                  <option v-for="voice in availableVoices" :key="voice.name" :value="voice.name">{{ formatVoiceOption(voice) }}</option>
                </select>
                <p class="text-xs text-slate-500">Used for this NPC's direct dialogue in TTS. Empty keeps the global default voice.</p>
              </div>

              <div class="space-y-3">
                <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">{{ context.type === 'cover' ? 'Global Context / Premise' : 'Description / Biography' }}</label>
                <textarea v-model="localForm.description" rows="8" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-lg text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner"></textarea>
              </div>
            </div>

            <div class="flex justify-end gap-6 pt-4">
              <button @click="emit('close')" class="px-8 py-3 text-slate-400 hover:text-white font-black uppercase text-xs tracking-widest transition-colors">Discard</button>
              <button @click="handleSave" :disabled="isSaving" class="px-10 py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-black uppercase text-xs tracking-widest rounded-xl shadow-lg shadow-emerald-900/20 disabled:opacity-50 flex items-center gap-3">
                <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
                <span>{{ isSaving ? 'Saving...' : 'Apply Changes' }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-enter-from, .modal-leave-to { opacity: 0; }

.modal-enter-active .modal-content { animation: modalScaleIn 0.5s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-leave-active .modal-content { transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); transform: scale(0.95); }

@keyframes modalScaleIn {
  from { opacity: 0; transform: scale(0.9) translateY(40px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
</style>
