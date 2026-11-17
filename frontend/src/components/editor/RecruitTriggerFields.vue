<script setup lang="ts">
import TriggerScriptField from '@/components/editor/entity/TriggerScriptField.vue'

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
  <div class="space-y-6">
    <p class="wb-hint">
      Only for companions with a Recruit action (recruit mode "joins at once" or "wants an item").
      <code class="wb-mono">offered_item_id</code> is in scope of both scripts.
    </p>
    <TriggerScriptField
      v-model:script="successScript"
      v-model:text="successText"
      label="On recruit success"
      help="Runs after the NPC joined the party through its Recruit action. In item mode the NPC already holds the offered item."
      context="on_recruit_success"
      text-placeholder="Without a success text or script, the Game Master narrates how the NPC joins."
    />
    <TriggerScriptField
      v-model:script="failureScript"
      v-model:text="failureText"
      label="On recruit failure"
      help="Item mode only: runs when the player offers the wrong item or none. The item stays with the player."
      context="on_recruit_failure"
      text-placeholder="e.g. Grull sniffs the flask and shakes his head. 'That's water, friend.'"
    />
  </div>
</template>
