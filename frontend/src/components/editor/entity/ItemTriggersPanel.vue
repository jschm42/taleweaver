<script setup lang="ts">
import { computed } from 'vue'
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import InteractTriggerFields from '@/components/editor/InteractTriggerFields.vue'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import TriggerScriptField from '@/components/editor/entity/TriggerScriptField.vue'
import UiField from '@/components/ui/UiField.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const ef = useEntityFormContext()

const PICKUP_MODES = [
  { value: 'silent', label: 'Silent (no reaction)' },
  { value: 'narration', label: 'Short narration only' },
  { value: 'turn', label: 'Full turn (characters and rules may react)' },
]

const isSwitch = computed(() => ['SWITCH', 'CONTAINER_SWITCH'].includes(ef.currentItemType))
const hasCarryTriggers = computed(() => !ef.isRecipe && ef.currentItemType !== 'SWITCH')
const isEquipment = computed(() => ef.currentItemType === 'WEARABLE' || ef.currentItemType === 'WEAPON')
const showsPickupMode = computed(
  () => hasCarryTriggers.value && ef.localForm.is_portable && ef.currentItemType !== 'WEARABLE',
)
</script>

<template>
  <div class="space-y-8">
    <UiSection
      v-if="isSwitch"
      title="Switch scripts"
      description="Run for every transition of this switch: when it succeeds, or when it fails or a requirement blocks it."
    >
      <ScriptEditor
        v-model="ef.localForm.on_success_script"
        label="On success script"
        help-text="Runs every time a transition succeeds, e.g. tw.vars.set('safe', True)."
        context="switch_success"
        min-height="120px"
      />
      <ScriptEditor
        v-model="ef.localForm.on_failure_script"
        label="On failure script"
        help-text="Runs every time a transition fails or is blocked, e.g. tw.player.damage(10)."
        context="switch_failure"
        min-height="120px"
      />
    </UiSection>

    <UiSection v-if="showsPickupMode" title="Pickup reaction" description="Whether the Game Master or a character reacts when the player takes this item.">
      <UiField label="Reaction">
        <UiSelect v-model="ef.localForm.pickup_trigger_mode" :options="PICKUP_MODES" class="sm:max-w-sm" />
      </UiField>
      <UiField
        v-if="ef.localForm.pickup_trigger_mode && ef.localForm.pickup_trigger_mode !== 'silent'"
        label="Cue for the Game Master"
        hint="Optional."
        :count="(ef.localForm.pickup_trigger_cue || '').length"
        :max-length="500"
      >
        <UiTextarea
          v-model="ef.localForm.pickup_trigger_cue"
          :rows="3"
          maxlength="500"
          placeholder="e.g. The HR clerk smirks and warns Arthur that signing is binding."
        />
      </UiField>
    </UiSection>

    <InteractTriggerFields
      v-model:script="ef.localForm.on_interact_script"
      v-model:text="ef.localForm.on_interact_text"
      entity-label="object"
    />

    <UiSection v-if="hasCarryTriggers" title="Pickup and drop">
      <TriggerScriptField
        v-model:script="ef.localForm.on_pickup_script"
        v-model:text="ef.localForm.on_pickup_text"
        label="On pickup"
        help="Runs when the player picks up this item, e.g. to set a flag or give a curse."
        context="on_pickup"
        min-height="120px"
      />
      <TriggerScriptField
        v-model:script="ef.localForm.on_drop_script"
        v-model:text="ef.localForm.on_drop_text"
        label="On drop"
        help="Runs when the player drops this item."
        context="on_drop"
        min-height="120px"
      />
    </UiSection>

    <UiSection v-if="isEquipment" title="Equip and unequip">
      <TriggerScriptField
        v-model:script="ef.localForm.on_equip_script"
        v-model:text="ef.localForm.on_equip_text"
        label="On equip"
        help="Runs when the player equips this item."
        context="on_equip"
        min-height="120px"
      />
      <TriggerScriptField
        v-model:script="ef.localForm.on_unequip_script"
        v-model:text="ef.localForm.on_unequip_text"
        label="On unequip"
        help="Runs when the player takes it off."
        context="on_unequip"
        min-height="120px"
      />
    </UiSection>

    <UiSection v-if="ef.currentItemType === 'READABLE'" title="Reading">
      <TriggerScriptField
        v-model:script="ef.localForm.on_read_script"
        v-model:text="ef.localForm.on_read_text"
        label="On read"
        help="Runs when the player reads or inspects this item."
        context="on_read"
        min-height="120px"
      />
    </UiSection>
  </div>
</template>
