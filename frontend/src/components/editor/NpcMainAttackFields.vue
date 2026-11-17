<script setup lang="ts">
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import WeaponCombatSettings from '@/components/editor/WeaponCombatSettings.vue'
import { emptyAttack, type NpcCombatProfileState } from '@/composables/editor/useNpcCombatProfile'
import type { WeaponConfig } from '@/utils/weaponConfig'

/** Main attack of an NPC's combat profile, with presets. */
const props = defineProps<{ profile: NpcCombatProfileState }>()
// The profile object is fixed for the lifetime of this component; its refs hold the editable state.
const { hasAttack, attackName, attack, legacyItems } = props.profile

const PRESETS: Array<{ label: string; name: string; config: Partial<WeaponConfig> }> = [
  { label: 'Longsword', name: 'Longsword', config: { category: 'MELEE', damage_dice: '1d8', hit_stat: 'strength' } },
  { label: 'Bow', name: 'Bow Shot', config: { category: 'RANGED', damage_dice: '1d6', hit_stat: 'dexterity' } },
  { label: 'Magic Missile', name: 'Magic Missile', config: { category: 'MAGIC', damage_dice: '1d4+1', hit_stat: 'intelligence', cost_type: 'mana', cost_value: 5 } },
  { label: 'Claws', name: 'Claws', config: { category: 'MELEE', damage_dice: '2d4', hit_stat: 'strength' } },
]

function applyPreset(preset: (typeof PRESETS)[number]): void {
  hasAttack.value = true
  attackName.value = preset.name
  attack.value = { ...emptyAttack(), ...preset.config, effects: [] }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <UiCheckbox v-model="hasAttack" label="Main attack" />
      <div class="flex flex-wrap items-center gap-1.5">
        <span class="wb-hint mr-1">Preset</span>
        <UiButton v-for="preset in PRESETS" :key="preset.label" size="sm" @click="applyPreset(preset)">{{ preset.label }}</UiButton>
      </div>
    </div>
    <p v-if="!hasAttack" class="wb-hint">
      Without a main attack it fights
      {{ legacyItems.length ? 'with its equipped weapon item (deprecated)' : 'unarmed (1d6)' }}.
    </p>
    <template v-else>
      <UiField label="Attack name" hint="Shown in the combat log.">
        <UiInput v-model="attackName" maxlength="60" placeholder="e.g. Longsword, Bite, Magic Missile" />
      </UiField>
      <WeaponCombatSettings v-model="attack" title="Attack settings" />
    </template>
    <UiNotice v-if="legacyItems.length" tone="warn">
      Still uses deprecated equipment items ({{ legacyItems.join(', ') }}).
      {{ hasAttack ? 'The main attack replaces the weapon item.' : 'Configure a main attack to replace the weapon item.' }}
      Set the armor bonus via AC instead of an armor item.
    </UiNotice>
  </div>
</template>
