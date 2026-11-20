<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import NpcAttributeFields from '@/components/editor/NpcAttributeFields.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSection from '@/components/ui/UiSection.vue'
import type { NpcCombatProfileState } from '@/composables/editor/useNpcCombatProfile'

/** Stats tab of a character: resources (HP, stamina, mana), attributes and armor class. */
defineProps<{ profile: NpcCombatProfileState | null }>()

const ef = useEntityFormContext()

const outOfRange = (value: unknown): boolean => typeof value === 'number' && (value < 0 || value > 999)
</script>

<template>
  <div class="space-y-8">
    <UiSection
      v-if="ef.props.ruleEnforcementMode !== 'chat'"
      title="Resources"
      description="Starting values; they are also the maximum."
    >
      <div class="grid grid-cols-3 gap-4">
        <UiField label="Health (HP)" :error="outOfRange(ef.localForm.hp) ? '0–999' : null">
          <UiInput v-model="ef.localForm.hp" type="number" min="0" max="999" />
        </UiField>
        <UiField label="Stamina" :error="outOfRange(ef.localForm.stamina) ? '0–999' : null">
          <UiInput v-model="ef.localForm.stamina" type="number" min="0" max="999" />
        </UiField>
        <UiField v-if="ef.props.ruleEnforcementMode === 'rpg'" label="Mana" :error="outOfRange(ef.localForm.mana) ? '0–999' : null">
          <UiInput v-model="ef.localForm.mana" type="number" min="0" max="999" />
        </UiField>
      </div>
    </UiSection>

    <UiSection
      title="Attributes"
      description="Strength, dexterity, intelligence, wisdom, charisma and armor class."
      :class="ef.props.ruleEnforcementMode !== 'chat' ? 'border-t border-wb-line pt-6' : ''"
    >
      <NpcAttributeFields v-if="profile" :profile="profile" />
      <UiNotice v-else>Save the character first to set its attributes and armor class.</UiNotice>
    </UiSection>
  </div>
</template>
