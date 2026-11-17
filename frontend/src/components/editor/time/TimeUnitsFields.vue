<script setup lang="ts">
import { computed } from 'vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSection from '@/components/ui/UiSection.vue'
import { useTimeSettings } from '@/composables/editor/useTimeSettings'

/** Custom time units system: unit name, start value, units per turn and GM limit. */
const time = useTimeSettings()
const { form, errors } = time

const unit = computed(() => String(form.time_config?.unit_name || '').trim() || 'units')

const toNumber = (value: string | number | null): number | null => (value === null || value === '' ? null : Number(value))
</script>

<template>
  <div class="space-y-8">
    <UiSection title="Start" description="The counter the adventure starts with.">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <UiField label="Unit name" hint="e.g. Lightyears, Blobs, Cycles." :error="errors.unit_name">
          <UiInput
            :model-value="form.time_config?.unit_name ?? 'Blobs'"
            maxlength="30"
            placeholder="e.g. Lightyears"
            @update:model-value="time.setConfig('unit_name', $event ?? '')"
          />
        </UiField>
        <UiField label="Start value" hint="Counter value at the start (0–10,000)." :error="errors.initial_value">
          <UiInput
            type="number"
            min="0"
            max="10000"
            step="any"
            :model-value="form.time_config?.initial_value ?? 0"
            @update:model-value="time.setConfig('initial_value', toNumber($event) ?? 0)"
          />
        </UiField>
      </div>
    </UiSection>

    <UiSection title="Pacing" description="How fast the counter grows." class="border-t border-wb-line pt-6">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <UiField
          :label="`${unit} per turn`"
          hint="Passes after every narrated player message."
          info="Up to 10,000. Scripts can change it in-game with tw.time.set_minutes_per_tick()."
          :error="errors.units_pacing"
        >
          <UiInput
            type="number"
            min="0.001"
            max="10000"
            step="any"
            :model-value="form.time_per_turn ?? 1"
            @update:model-value="form.time_per_turn = toNumber($event)"
          />
        </UiField>
        <UiField
          :label="`Max ${unit} per turn (GM limit)`"
          hint="Caps the time per turn plus the GM's extra time. Empty: no cap."
          :error="errors.units_max"
        >
          <UiInput
            type="number"
            min="0.001"
            max="10000"
            step="any"
            placeholder="No cap"
            :model-value="form.max_time_per_turn ?? null"
            @update:model-value="form.max_time_per_turn = toNumber($event)"
          />
        </UiField>
      </div>
    </UiSection>
  </div>
</template>
