<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiToggle from '@/components/ui/UiToggle.vue'
import { CONTROL_TEXTAREA_CLASS } from '@/components/ui/fieldContext'

const ef = useEntityFormContext()

const REVEAL_INFO =
  'When the Game Master reveals the character. Empty: when the player searches the scene or the character speaks. ' +
  'Enter "script" to let only scripts reveal it.'
</script>

<template>
  <UiSection v-if="ef.type === 'npc'" title="Visibility" class="border-t border-wb-line pt-6">
    <UiToggle
      v-model="ef.localForm.is_hidden"
      label="Start hidden"
      description="Appears only when discovered or when it speaks."
    />
    <template v-if="ef.localForm.is_hidden">
      <UiField label="Hiding place" hint="Used by the narrator when describing the scene.">
        <UiInput v-model="ef.localForm.spatial_position" maxlength="255" placeholder="e.g. hiding in the cellar behind the wine barrels" />
      </UiField>
      <UiField label="Reveal rule" :info="REVEAL_INFO" :count="(ef.localForm.reveal_rule || '').length" :max-length="500">
        <ReferenceTextarea
          v-model="ef.localForm.reveal_rule"
          :options="ef.props.referenceOptions || []"
          :rows="2"
          :maxlength="500"
          placeholder="e.g. when the protagonist inspects the wine rack or calls the secret passphrase"
          :class-name="CONTROL_TEXTAREA_CLASS"
        />
      </UiField>
    </template>
  </UiSection>
</template>
