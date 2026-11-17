<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import InteractTriggerFields from '@/components/editor/InteractTriggerFields.vue'
import { FileText } from 'lucide-vue-next'
import { Sparkles } from 'lucide-vue-next'

const ef = useEntityFormContext()
</script>

<template>
  <!-- SWITCH Triggers in Advanced Tab -->
  <div v-if="['SWITCH', 'CONTAINER_SWITCH'].includes(ef.currentItemType)" class="space-y-4">
    <div class="p-4 bg-lime-500/10 border border-lime-500/20 rounded-2xl space-y-1">
      <div class="flex items-center gap-2 text-lime-400 font-bold text-xs uppercase tracking-wider">
        <Sparkles class="w-4 h-4" /> Global Switch Script Triggers
      </div>
      <p class="text-xs text-slate-300">
        These global scripts are executed every time any transition on this switch is triggered: immediately when a transition succeeds, or when it fails / is blocked by guards.
      </p>
    </div>
    <div class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
      <ScriptEditor
        v-model="ef.localForm.on_success_script"
        label="Global On Success Script"
        help-text="Executed every time any transition on this switch succeeds (e.g. tw.vars.set('safe', True), tw.story.narrate(...))."
        context="switch_success"
        min-height="120px"
      />
      <ScriptEditor
        v-model="ef.localForm.on_failure_script"
        label="Global On Failure Script"
        help-text="Executed every time a transition on this switch fails or is blocked by guards (e.g. tw.player.damage(10), trigger trap)."
        context="switch_failure"
        min-height="120px"
      />
    </div>
  </div>

  <!-- Non-Switch Object Triggers -->
  <div v-if="!ef.isRecipe && ef.currentItemType !== 'SWITCH' && ef.localForm.is_portable && ef.currentItemType !== 'WEARABLE'" class="space-y-3 border border-white/5 bg-black/20 p-4 rounded-xl">
    <div class="space-y-1">
      <label class="block text-[10px] font-black text-slate-500 uppercase tracking-widest">On Pickup Mode</label>
      <p class="text-[10px] text-slate-500 uppercase tracking-tighter">Choose whether the Game Master or an NPC reacts when the player takes this item.</p>
    </div>
    <select
      v-model="ef.localForm.pickup_trigger_mode"
      class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold uppercase tracking-widest focus:border-emerald-500/50 outline-none transition-all"
    >
      <option value="silent">Silent (no reaction)</option>
      <option value="narration">Narration Pass (short reaction only)</option>
      <option value="turn">Full Turn (NPCs and rules may react)</option>
    </select>
    <textarea
      v-if="ef.localForm.pickup_trigger_mode && ef.localForm.pickup_trigger_mode !== 'silent'"
      v-model="ef.localForm.pickup_trigger_cue"
      rows="4"
      maxlength="500"
      placeholder="Optional cue for the GM, e.g. 'The HR clerk smirks and warns Arthur that signing is binding.'"
      class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white text-sm focus:border-emerald-500/50 outline-none transition-all resize-y"
    ></textarea>
  </div>

  <InteractTriggerFields
    v-model:script="ef.localForm.on_interact_script"
    v-model:text="ef.localForm.on_interact_text"
    entity-label="object"
  />

  <div v-if="!ef.isRecipe && ef.currentItemType !== 'SWITCH'" class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
    <ScriptEditor
      v-model="ef.localForm.on_pickup_script"
      label="On Pickup Script"
      help-text="Executed immediately when the player picks up this item. Use this to mutate game state (e.g. give a curse or trigger a flag)."
      context="on_pickup"
      min-height="120px"
    />
    <div class="space-y-2">
      <div class="flex items-center gap-2">
      <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Pickup Text</label>
      <div class="group relative flex items-center">
        <i class="ra ra-help text-slate-500 hover:text-white cursor-help transition-colors text-xs"></i>
        <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-800 text-[10px] text-slate-300 font-normal normal-case tracking-normal rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity border border-white/10 z-50">
          A narrative text string shown to the player when picking up this item.
        </div>
      </div>
    </div>
      <textarea v-model="ef.localForm.on_pickup_text" rows="4" class="w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y"></textarea>
    </div>
  </div>

  <div v-if="!ef.isRecipe && ef.currentItemType !== 'SWITCH'" class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
    <ScriptEditor
      v-model="ef.localForm.on_drop_script"
      label="On Drop Script"
      help-text="Executed immediately when the player drops this item from their inventory."
      context="on_drop"
      min-height="120px"
    />
    <div class="space-y-2">
      <div class="flex items-center gap-2">
      <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Drop Text</label>
      <div class="group relative flex items-center">
        <i class="ra ra-help text-slate-500 hover:text-white cursor-help transition-colors text-xs"></i>
        <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-800 text-[10px] text-slate-300 font-normal normal-case tracking-normal rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity border border-white/10 z-50">
          A narrative text string shown to the player when dropping this item.
        </div>
      </div>
    </div>
      <textarea v-model="ef.localForm.on_drop_text" rows="4" class="w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y"></textarea>
    </div>
  </div>

  <div v-if="ef.currentItemType === 'WEARABLE' || ef.currentItemType === 'WEAPON'" class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
    <ScriptEditor
      v-model="ef.localForm.on_equip_script"
      label="On Equip Script"
      help-text="Executed when the player equips this wearable/weapon."
      context="on_equip"
      min-height="120px"
    />
    <div class="space-y-2">
      <div class="flex items-center gap-2">
      <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Equip Text</label>
      <div class="group relative flex items-center">
        <i class="ra ra-help text-slate-500 hover:text-white cursor-help transition-colors text-xs"></i>
        <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-800 text-[10px] text-slate-300 font-normal normal-case tracking-normal rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity border border-white/10 z-50">
          A narrative text string shown to the player upon equipping.
        </div>
      </div>
    </div>
      <textarea v-model="ef.localForm.on_equip_text" rows="4" class="w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y"></textarea>
    </div>
  </div>

  <div v-if="ef.currentItemType === 'WEARABLE' || ef.currentItemType === 'WEAPON'" class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
    <ScriptEditor
      v-model="ef.localForm.on_unequip_script"
      label="On Unequip Script"
      help-text="Executed when the player unequips this wearable/weapon."
      context="on_unequip"
      min-height="120px"
    />
    <div class="space-y-2">
      <div class="flex items-center gap-2">
      <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Unequip Text</label>
      <div class="group relative flex items-center">
        <i class="ra ra-help text-slate-500 hover:text-white cursor-help transition-colors text-xs"></i>
        <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-800 text-[10px] text-slate-300 font-normal normal-case tracking-normal rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity border border-white/10 z-50">
          A narrative text string shown to the player upon unequipping.
        </div>
      </div>
    </div>
      <textarea v-model="ef.localForm.on_unequip_text" rows="4" class="w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y"></textarea>
    </div>
  </div>

  <!-- READABLE Triggers in Advanced Tab -->
  <div v-if="ef.currentItemType === 'READABLE'" class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
    <div class="flex items-center gap-2 text-cyan-400 font-bold text-xs uppercase tracking-wider">
      <FileText class="w-4 h-4" /> On Read Trigger & Script
    </div>
    <ScriptEditor
      v-model="ef.localForm.on_read_script"
      label="On Read Script"
      help-text="Executed immediately when the player reads or inspects this readable item."
      context="on_read"
      min-height="120px"
    />
    <div class="space-y-2">
      <div class="flex items-center gap-2">
        <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Read Text</label>
        <div class="group relative flex items-center">
          <i class="ra ra-help text-slate-500 hover:text-white cursor-help transition-colors text-xs"></i>
          <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-800 text-[10px] text-slate-300 font-normal normal-case tracking-normal rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity border border-white/10 z-50">
            A narrative text string shown to the player upon reading this document.
          </div>
        </div>
      </div>
      <textarea v-model="ef.localForm.on_read_text" rows="4" class="w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y"></textarea>
    </div>
  </div>
</template>
