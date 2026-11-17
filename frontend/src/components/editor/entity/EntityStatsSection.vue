<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'

const ef = useEntityFormContext()

const outOfRange = (value: unknown): boolean => typeof value === 'number' && (value < 0 || value > 999)
</script>

<template>
  <div class="space-y-5">
    <UiField
      label="Name"
      required
      :count="(ef.localForm.name || '').length"
      :max-length="50"
    >
      <UiInput v-model="ef.localForm.name" maxlength="50" class="!h-11 !text-base font-semibold" />
    </UiField>

    <div v-if="['protagonist', 'npc'].includes(ef.type) && ef.props.ruleEnforcementMode !== 'chat'" class="grid grid-cols-3 gap-4">
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
  </div>
</template>
