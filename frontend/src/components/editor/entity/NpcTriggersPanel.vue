<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import InteractTriggerFields from '@/components/editor/InteractTriggerFields.vue'
import ReceiveItemTriggerFields from '@/components/editor/ReceiveItemTriggerFields.vue'

const ef = useEntityFormContext()
</script>

<template>
  <InteractTriggerFields
    v-model:script="ef.localForm.on_interact_script"
    v-model:text="ef.localForm.on_interact_text"
    entity-label="NPC"
  />

  <ReceiveItemTriggerFields
    v-model:script="ef.localForm.on_receive_item_script"
    v-model:text="ef.localForm.on_receive_item_text"
  />

  <div class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
    <ScriptEditor
      v-model="ef.localForm.on_defeat_script"
      label="On Defeat Script"
      help-text="Executed immediately when this NPC is marked as defeated. Use to spawn loot or trigger story progression."
      context="on_defeat"
      min-height="120px"
    />
    <div class="space-y-2">
      <div class="flex items-center gap-2">
      <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Defeat Text (NPC speaks)</label>
      <div class="group relative flex items-center">
        <i class="ra ra-help text-slate-500 hover:text-white cursor-help transition-colors text-xs"></i>
        <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-800 text-[10px] text-slate-300 font-normal normal-case tracking-normal rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity border border-white/10 z-50">
          A final quote or description printed when the NPC is defeated.
        </div>
      </div>
    </div>
      <textarea v-model="ef.localForm.on_defeat_text" rows="4" class="w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y"></textarea>
    </div>
  </div>

  <div class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
    <ScriptEditor
      v-model="ef.localForm.on_protagonist_enters_scene_script"
      label="On Protagonist Enters Script"
      help-text="Executed by this NPC when the protagonist enters the scene. Use to alter the NPC state or trigger a trap."
      context="on_protagonist_enters_scene"
      min-height="120px"
    />
    <div class="space-y-2">
      <div class="flex items-center gap-2">
      <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Protagonist Enters Text</label>
      <div class="group relative flex items-center">
        <i class="ra ra-help text-slate-500 hover:text-white cursor-help transition-colors text-xs"></i>
        <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-800 text-[10px] text-slate-300 font-normal normal-case tracking-normal rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity border border-white/10 z-50">
          Text spoken or narrated by this NPC immediately when the player enters the scene.
        </div>
      </div>
    </div>
      <textarea v-model="ef.localForm.on_protagonist_enters_scene_text" rows="4" class="w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y"></textarea>
    </div>
  </div>
</template>
