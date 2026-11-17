<script setup lang="ts">
import { cloneValue, useDraft } from '@/composables/useDraft'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const props = defineProps<{
  gameForm: any
  isSubmitting: boolean
}>()

const emit = defineEmits<{
  (e: 'save', payload: any): void
}>()

const { draft, isDirty, changedCount, reset } = useDraft(() => props.gameForm)

const DATE_FORMATS = [
  { value: 'DD.MM.YY', label: 'DD.MM.YY (e.g. 24.12.26)' },
  { value: 'MM/DD/YY', label: 'MM/DD/YY (e.g. 12/24/26)' },
  { value: 'YY-MM-DD', label: 'YY-MM-DD (e.g. 26-12-24)' },
]
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Game settings" description="Interface and gameplay options for all players." />

    <UiCard title="In-game clock">
      <div class="space-y-5">
        <UiToggle
          v-model="draft.clock_24h"
          label="24-hour format"
          description="Off shows the time as 12-hour clock with AM/PM."
        />
        <UiField label="Date format" hint="How the in-game date is written.">
          <UiSelect v-model="draft.date_format" :options="DATE_FORMATS" class="max-w-xs" />
        </UiField>
      </div>
    </UiCard>

    <UiSaveBar
      :dirty="isDirty"
      :count="changedCount"
      :saving="isSubmitting"
      @save="emit('save', cloneValue(draft))"
      @discard="reset"
    />
  </div>
</template>
