<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'

const ef = useEntityFormContext()
</script>

<template>
  <!-- Scene Triggers -->
  <div class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
    <ScriptEditor
      v-model="ef.localForm.on_enter_scene_script"
      label="On Enter Scene Script"
      help-text="Executed immediately when the protagonist enters this scene."
      context="on_enter_scene"
      min-height="120px"
    />
    <div class="space-y-2">
      <div class="flex items-center gap-2">
      <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Enter Scene Text</label>
      <div class="group relative flex items-center">
        <i class="ra ra-help text-slate-500 hover:text-white cursor-help transition-colors text-xs"></i>
        <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-800 text-[10px] text-slate-300 font-normal normal-case tracking-normal rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity border border-white/10 z-50">
          A narrative text string shown right after the player enters the scene.
        </div>
      </div>
    </div>
      <textarea v-model="ef.localForm.on_enter_scene_text" rows="4" class="w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y"></textarea>
    </div>
  </div>

  <div class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
    <ScriptEditor
      v-model="ef.localForm.on_leave_scene_script"
      label="On Leave Scene Script"
      help-text="Executed immediately when the protagonist leaves this scene."
      context="on_leave_scene"
      min-height="120px"
    />
    <div class="space-y-2">
      <div class="flex items-center gap-2">
      <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Leave Scene Text</label>
      <div class="group relative flex items-center">
        <i class="ra ra-help text-slate-500 hover:text-white cursor-help transition-colors text-xs"></i>
        <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-800 text-[10px] text-slate-300 font-normal normal-case tracking-normal rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity border border-white/10 z-50">
          A narrative text string shown right when the player leaves this scene.
        </div>
      </div>
    </div>
      <textarea v-model="ef.localForm.on_leave_scene_text" rows="4" class="w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y"></textarea>
    </div>
  </div>

  <div class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
    <ScriptEditor
      v-model="ef.localForm.helpers_script"
      label="Scene Helpers"
      help-text="Functions and constants (def, NAME = value) that every script can call, like the global init script. Loaded on every script run, wherever the player is. Other statements never run; use the trigger scripts above for those."
      context="init_script"
      min-height="120px"
    />
  </div>
</template>
