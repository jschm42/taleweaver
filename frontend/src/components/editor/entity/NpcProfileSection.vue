<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import NpcVoicePicker from '@/components/editor/NpcVoicePicker.vue'

const ef = useEntityFormContext()
</script>

<template>

  <div v-if="ef.type === 'npc'" class="space-y-2">
    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">NPC Type & Speech Rule</label>
    <select
      v-model="ef.localForm.npc_type"
      class="w-full bg-black/40 border border-white/10 rounded-2xl px-4 py-3 text-sm font-bold text-slate-200 focus:border-emerald-500 outline-none transition-all shadow-inner"
    >
      <option value="HUMANOID" class="bg-slate-900 text-slate-200">Humanoid — Speaks full sentences & eligible for quotes</option>
      <option value="BEING" class="bg-slate-900 text-slate-200">Sentient Being — Speaks full sentences & eligible for quotes</option>
      <option value="ANIMAL" class="bg-slate-900 text-slate-200">Animal — Non-verbal sounds & gestures only</option>
      <option value="MONSTER" class="bg-slate-900 text-slate-200">Monster — Creature sounds & gestures only</option>
    </select>
    <p class="text-[11px] text-slate-500 leading-relaxed">
      Humanoid and Sentient Being NPCs speak intelligible full sentences in narration and can deliver transition quotes. Animal and Monster NPCs use creature sounds and body language only.
    </p>
  </div>

  <NpcVoicePicker
    v-if="ef.type === 'npc' || ef.type === 'protagonist'"
    v-model="ef.localForm.voice"
    :voice-list="ef.props.voiceList ?? null"
    :npc-name="ef.localForm.name"
    :adventure-id="ef.props.adventureId"
  />

  <div v-if="ef.type === 'npc'" class="grid grid-cols-1 md:grid-cols-2 gap-6">
    <div class="space-y-3">
      <div class="flex justify-between items-center">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">NPC Goal / Motivation</label>
        <span :class="['text-xs font-bold tracking-widest', (ef.localForm.goal || '').length > 200 ? 'text-red-500' : 'text-emerald-500/50']">
          {{ (ef.localForm.goal || '').length }} / 200
        </span>
      </div>
      <ReferenceTextarea
        v-model="ef.localForm.goal"
        :maxlength="200"
        :rows="2"
        :options="ef.props.referenceOptions || []"
        class-name="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner"
        placeholder="What does this NPC want? (e.g. 'Wants to steal the player's gold')"
      />
      <button 
        v-if="ef.localForm.description"
        @click="ef.handleGenerateTraits('goal')" 
        :disabled="ef.isGenerating['goal']"
        class="w-full py-2 bg-emerald-500/5 border border-emerald-500/10 hover:bg-emerald-500/10 hover:border-emerald-500/30 rounded-xl text-[10px] font-black text-emerald-500 uppercase tracking-widest flex items-center justify-center gap-2 transition-all disabled:opacity-50"
      >
        <i class="ra ra-crystals" :class="{ 'animate-spin': ef.isGenerating['goal'] }"></i>
        <span>Quick-Gen Goal</span>
      </button>
    </div>
    <div class="space-y-3">
      <div class="flex justify-between items-center">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">NPC Character / Traits</label>
        <span :class="['text-xs font-bold tracking-widest', (ef.localForm.character || '').length > 200 ? 'text-red-500' : 'text-emerald-500/50']">
          {{ (ef.localForm.character || '').length }} / 200
        </span>
      </div>
      <ReferenceTextarea
        v-model="ef.localForm.character"
        :maxlength="200"
        :rows="2"
        :options="ef.props.referenceOptions || []"
        class-name="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner"
        placeholder="How does this NPC behave? (e.g. 'Grumpy and stubborn')"
      />
      <button 
        v-if="ef.localForm.description"
        @click="ef.handleGenerateTraits('character')" 
        :disabled="ef.isGenerating['character']"
        class="w-full py-2 bg-emerald-500/5 border border-emerald-500/10 hover:bg-emerald-500/10 hover:border-emerald-500/30 rounded-xl text-[10px] font-black text-emerald-500 uppercase tracking-widest flex items-center justify-center gap-2 transition-all disabled:opacity-50"
      >
        <i class="ra ra-crystals" :class="{ 'animate-spin': ef.isGenerating['character'] }"></i>
        <span>Quick-Gen Traits</span>
      </button>
    </div>
  </div>
</template>
