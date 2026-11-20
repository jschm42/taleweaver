<script setup lang="ts">
import { computed } from 'vue'
import type { Chapter, ProgressionMode } from '@/composables/editor/useChapters'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import TriggerScriptField from '@/components/editor/entity/TriggerScriptField.vue'

/** Start / end triggers of a chapter and its helper functions. */
const chapter = defineModel<Chapter>({ required: true })

const props = defineProps<{ mode: ProgressionMode }>()

const dynamic = computed(() => props.mode === 'dynamic')
</script>

<template>
  <div class="space-y-6">
    <div class="space-y-6">
      <TriggerScriptField
        v-model:script="chapter.on_start_sequence_script"
        v-model:text="chapter.on_start_sequence_text"
        label="On start"
        help="Runs when this chapter becomes active."
        context="start_sequence"
        :text-placeholder="dynamic ? 'e.g. Workshop phase begins: Alex inspects the workbench.' : 'e.g. Chapter 2 begins: The sky darkens as thunder rumbles in the distance.'"
      />
      <TriggerScriptField
        v-model:script="chapter.on_end_sequence_script"
        v-model:text="chapter.on_end_sequence_text"
        label="On end"
        help="Runs when this chapter is completed."
        context="end_sequence"
        :text-placeholder="dynamic ? 'e.g. Sequence complete! The casket trial is solved.' : 'e.g. Chapter complete! The dungeon gates seal shut behind you.'"
      />
    </div>
    <ScriptEditor
      v-model="chapter.helpers_script"
      label="Chapter helpers"
      help-text="Functions and constants (def, NAME = value) of this chapter, e.g. its dialog handlers. Like the init script they load on every script run, whichever chapter is active; other statements never run."
      context="init_script"
      placeholder="def trial_score_answer(answ):&#10;    tw.vars.set('trial_score', tw.vars.get('trial_score', 0) + answ)"
      min-height="140px"
    />
  </div>
</template>
