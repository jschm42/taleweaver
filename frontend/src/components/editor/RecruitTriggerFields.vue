<script setup lang="ts">
import ScriptEditor from '@/components/editor/ScriptEditor.vue'

/**
 * Inline on_recruit_success / on_recruit_failure triggers (script + text) of a companion NPC
 * whose recruit mode is INSTANT or ITEM (see the Companion settings).
 */
const successScript = defineModel<string>('successScript', { default: '' })
const successText = defineModel<string>('successText', { default: '' })
const failureScript = defineModel<string>('failureScript', { default: '' })
const failureText = defineModel<string>('failureText', { default: '' })
</script>

<template>
  <div class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
    <p class="text-[11px] text-slate-400">
      Only for companions with a Recruit action (Companion settings: recruit mode "joins at once" or "wants an item").
      <code class="text-sky-300">offered_item_id</code> is in scope of both scripts.
    </p>
    <ScriptEditor
      v-model="successScript"
      label="On Recruit Success Script"
      help-text="Executed after the NPC joined the party through its Recruit action. In item mode the NPC already holds the offered item."
      context="on_recruit_success"
      min-height="100px"
    />
    <div class="space-y-2">
      <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Recruit Success Text</label>
      <textarea
        v-model="successText"
        rows="2"
        placeholder="Without a success text or script, the Game Master narrates how the NPC joins."
        class="w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y"
      ></textarea>
    </div>
    <ScriptEditor
      v-model="failureScript"
      label="On Recruit Failure Script"
      help-text="Item mode only: executed when the player offers the wrong item or none. The item stays with the player."
      context="on_recruit_failure"
      min-height="100px"
    />
    <div class="space-y-2">
      <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Recruit Failure Text</label>
      <textarea
        v-model="failureText"
        rows="2"
        placeholder="e.g. Grull sniffs the flask and shakes his head. 'That's water, friend.'"
        class="w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y"
      ></textarea>
    </div>
  </div>
</template>
