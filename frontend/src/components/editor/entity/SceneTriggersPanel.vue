<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import TriggerScriptField from '@/components/editor/entity/TriggerScriptField.vue'
import UiSection from '@/components/ui/UiSection.vue'

const ef = useEntityFormContext()
</script>

<template>
  <div class="space-y-8">
    <UiSection title="Entering and leaving">
      <TriggerScriptField
        v-model:script="ef.localForm.on_enter_scene_script"
        v-model:text="ef.localForm.on_enter_scene_text"
        label="On enter"
        help="Runs when the protagonist enters this scene."
        context="on_enter_scene"
        min-height="120px"
      />
      <TriggerScriptField
        v-model:script="ef.localForm.on_leave_scene_script"
        v-model:text="ef.localForm.on_leave_scene_text"
        label="On leave"
        help="Runs when the protagonist leaves this scene."
        context="on_leave_scene"
        min-height="120px"
      />
    </UiSection>

    <UiSection title="Scene helpers" class="border-t border-wb-line pt-6">
      <ScriptEditor
        v-model="ef.localForm.helpers_script"
        label="Helpers"
        help-text="Functions and constants (def, NAME = value) every script can call, like the global init script. Loaded on every script run, wherever the player is; other statements never run."
        context="init_script"
        min-height="120px"
      />
    </UiSection>
  </div>
</template>
