<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import WeaponCombatSettings from '@/components/editor/WeaponCombatSettings.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'

const ef = useEntityFormContext()

const SLOTS = ['Head', 'Neck', 'Chest', 'Hands', 'Legs', 'Feet', 'MainHand', 'OffHand', 'Finger', 'Wrist', 'Back', 'Waist']
const SLOT_LABELS: Record<string, string> = { MainHand: 'Main hand', OffHand: 'Off hand' }

function toggleSlot(slot: string, checked: boolean): void {
  const slots: string[] = ef.localForm.wearable_slots_input
  ef.localForm.wearable_slots_input = checked ? [...slots, slot] : slots.filter((s) => s !== slot)
}
</script>

<template>
  <!-- WEAPON: damage, cost, attack roll and on-hit effects -->
  <WeaponCombatSettings v-if="ef.currentItemType === 'WEAPON' && ef.localForm.weapon_config" v-model="ef.localForm.weapon_config" />

  <UiField
    v-if="['WEAPON', 'WEARABLE'].includes(ef.currentItemType)"
    label="Wearable slots"
    :hint="ef.localForm.is_wearable_slots_fixed ? 'Fixed for this item.' : 'Where it can be equipped.'"
  >
    <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <UiCheckbox
        v-for="slot in SLOTS"
        :key="slot"
        :model-value="ef.localForm.wearable_slots_input.includes(slot)"
        :label="SLOT_LABELS[slot] ?? slot"
        :disabled="ef.localForm.is_wearable_slots_fixed"
        @update:model-value="(checked) => toggleSlot(slot, checked)"
      />
    </div>
  </UiField>
</template>
