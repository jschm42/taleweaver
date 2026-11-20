<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import NpcVoicePicker from '@/components/editor/NpcVoicePicker.vue'
import TraitFields from '@/components/editor/entity/TraitFields.vue'
import UiField from '@/components/ui/UiField.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const ef = useEntityFormContext()

const NPC_TYPES = [
  { value: 'HUMANOID', label: 'Humanoid – speaks full sentences, can be quoted' },
  { value: 'BEING', label: 'Sentient being – speaks full sentences, can be quoted' },
  { value: 'ANIMAL', label: 'Animal – non-verbal sounds and gestures only' },
  { value: 'MONSTER', label: 'Monster – creature sounds and gestures only' },
]
</script>

<template>
  <UiField
    v-if="ef.type === 'npc'"
    label="Kind and speech"
    hint="Humanoids and sentient beings speak in narration and can deliver transition quotes; animals and monsters only make sounds."
  >
    <UiSelect v-model="ef.localForm.npc_type" :options="NPC_TYPES" />
  </UiField>

  <NpcVoicePicker
    v-if="ef.type === 'npc' || ef.type === 'protagonist'"
    v-model="ef.localForm.voice"
    :voice-list="ef.props.voiceList ?? null"
    :npc-name="ef.localForm.name"
    :adventure-id="ef.props.adventureId"
  />

  <TraitFields
    v-if="ef.type === 'npc'"
    goal-label="Goal"
    goal-placeholder="What does this character want? e.g. wants to steal the player's gold"
    character-label="Character traits"
    character-placeholder="How does this character behave? e.g. grumpy and stubborn"
  />
</template>
