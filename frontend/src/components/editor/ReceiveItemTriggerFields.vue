<script setup lang="ts">
import TriggerScriptField from '@/components/editor/entity/TriggerScriptField.vue'

/** Inline on_receive_item trigger (script + text) of an NPC: the player gave it items. */
const script = defineModel<string>('script', { default: '' })
const text = defineModel<string>('text', { default: '' })
</script>

<template>
  <TriggerScriptField
    v-model:script="script"
    v-model:text="text"
    label="On receive item"
    help="Runs once when the player gives this NPC one or more items (context menu Give, /give_items or typing 'give <item> to <npc>'). received_items (list of dicts) and received_item_ids (list of IDs) are in scope. The items are already in the NPC's inventory; afterwards the Game Master narrates the NPC's reaction."
    context="on_receive_item"
    min-height="120px"
  />
</template>
