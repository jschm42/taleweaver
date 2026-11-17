<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiToggle from '@/components/ui/UiToggle.vue'
import { CONTROL_TEXTAREA_CLASS } from '@/components/ui/fieldContext'

const ef = useEntityFormContext()

const REVEAL_INFO =
  'The action or event that reveals the item. Empty: revealed when the player searches the scene. ' +
  'Enter "script" to let only scripts, crafting or another item\'s reveal show it.'
</script>

<template>
  <UiSection v-if="ef.currentItemType !== 'CONSTRUCTABLE'" title="Visibility" class="border-t border-wb-line pt-6">
    <UiToggle
      v-model="ef.localForm.is_hidden"
      label="Start hidden"
      description="The player must search the scene or meet a condition to discover it."
    />
    <template v-if="ef.localForm.is_hidden">
      <UiField label="Hiding place" hint="Used by the Game Master when describing the room.">
        <UiInput v-model="ef.localForm.spatial_position" maxlength="255" placeholder="e.g. under the couch cushions, inside the locked desk drawer" />
      </UiField>
      <UiField label="Reveal rule" :info="REVEAL_INFO" :count="(ef.localForm.reveal_rule || '').length" :max-length="500">
        <ReferenceTextarea
          v-model="ef.localForm.reveal_rule"
          :options="ef.props.referenceOptions || []"
          :rows="2"
          :maxlength="500"
          placeholder="e.g. player inspects the couch, player opens the junk drawer"
          :class-name="CONTROL_TEXTAREA_CLASS"
        />
      </UiField>
    </template>

    <!-- Switches reveal things through their transitions, outcomes and scripts. -->
    <UiField
      v-if="ef.currentItemType !== 'SWITCH'"
      label="Reveals item"
      hint="When this item is opened, searched or changed, the chosen hidden item is revealed."
    >
      <EntityReferenceCombobox
        v-model="ef.localForm.reveals_item_id"
        :options="ef.itemReferenceOptions"
        placeholder="Optional – a hidden item this one reveals"
        search-placeholder="Search items by id or name"
        :enable-search="true"
      />
    </UiField>
  </UiSection>
  <UiNotice v-else tone="info" title="Recipe">
    Recipes never appear in the game, so they need no description, appearance, position, visibility, portability or pickup triggers.
  </UiNotice>
</template>
