<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import InteractTriggerFields from '@/components/editor/InteractTriggerFields.vue'
import ReceiveItemTriggerFields from '@/components/editor/ReceiveItemTriggerFields.vue'
import TriggerScriptField from '@/components/editor/entity/TriggerScriptField.vue'
import UiSection from '@/components/ui/UiSection.vue'

const ef = useEntityFormContext()
</script>

<template>
  <div class="space-y-8">
    <InteractTriggerFields
      v-model:script="ef.localForm.on_interact_script"
      v-model:text="ef.localForm.on_interact_text"
      entity-label="NPC"
    />
    <ReceiveItemTriggerFields
      v-model:script="ef.localForm.on_receive_item_script"
      v-model:text="ef.localForm.on_receive_item_text"
    />
    <UiSection title="Defeat and arrival" class="border-t border-wb-line pt-6">
      <TriggerScriptField
        v-model:script="ef.localForm.on_defeat_script"
        v-model:text="ef.localForm.on_defeat_text"
        label="On defeat"
        help="Runs when this character is defeated, e.g. to spawn loot or move the story on. The text is its last words."
        context="on_defeat"
        min-height="120px"
      />
      <TriggerScriptField
        v-model:script="ef.localForm.on_protagonist_enters_scene_script"
        v-model:text="ef.localForm.on_protagonist_enters_scene_text"
        label="On protagonist arrival"
        help="Runs when the protagonist enters this character's scene, e.g. to change its state or spring a trap."
        context="on_protagonist_enters_scene"
        min-height="120px"
      />
    </UiSection>
  </div>
</template>
