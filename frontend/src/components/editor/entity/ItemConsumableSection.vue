<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSection from '@/components/ui/UiSection.vue'

const ef = useEntityFormContext()
</script>

<template>
  <UiSection
    v-if="ef.currentItemType === 'CONSUMABLE'"
    title="Effects when consumed"
    description="Positive values restore, negative values drain."
    class="border-t border-wb-line pt-6"
  >
    <div class="grid grid-cols-3 gap-4">
      <UiField label="Health (HP)">
        <UiInput v-model="ef.localForm.effects_hp" type="number" min="-999" max="999" />
      </UiField>
      <UiField label="Stamina">
        <UiInput v-model="ef.localForm.effects_stamina" type="number" min="-999" max="999" />
      </UiField>
      <UiField label="Mana">
        <UiInput v-model="ef.localForm.effects_mana" type="number" min="-999" max="999" />
      </UiField>
    </div>
  </UiSection>
</template>
