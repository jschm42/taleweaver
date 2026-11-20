<script setup lang="ts">
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import { AC_RANGE, STAT_RANGE, type NpcCombatProfileState } from '@/composables/editor/useNpcCombatProfile'
import { STAT_SHORT, SUCCESS_STATS } from '@/utils/specialAttacks'

/** Attribute and armor class inputs of an NPC's combat profile. */
const props = defineProps<{ profile: NpcCombatProfileState }>()
// The profile object is fixed for the lifetime of this component; its refs hold the editable state.
const { stats, armorClass } = props.profile

function toInt(value: string | number | null): number {
  return value === null || value === '' ? Number.NaN : Number(value)
}

function setArmorClass(value: string | number | null): void {
  armorClass.value = toInt(value)
}
</script>

<template>
  <div class="space-y-3">
    <div class="grid grid-cols-3 gap-3 md:grid-cols-6">
      <UiField v-for="s in SUCCESS_STATS" :key="s" :label="STAT_SHORT[s]">
        <UiInput
          type="number"
          :min="STAT_RANGE.min"
          :max="STAT_RANGE.max"
          :model-value="stats[s]"
          @update:model-value="(value) => (stats[s] = toInt(value))"
        />
      </UiField>
      <UiField label="AC" info="Armor class: the attack roll an attacker must reach to hit this character.">
        <UiInput
          type="number"
          :min="AC_RANGE.min"
          :max="AC_RANGE.max"
          :model-value="armorClass"
          @update:model-value="setArmorClass"
        />
      </UiField>
    </div>
    <p class="wb-hint">
      10 is average. Stats feed the attack and special rolls; AC is what the protagonist must roll to hit
      (10 unarmored, 14 leather, 18 plate).
    </p>
  </div>
</template>
