<script setup lang="ts">
/** In-game time of a new adventure: automatic, or a day clock or custom units set by hand. */
import { computed, watch } from 'vue'
import { Hourglass, Sun } from 'lucide-vue-next'
import { useCreateAdventureContext } from '@/composables/createAdventure/createAdventureContext'
import type { TimeConfigData, TimeSystem } from '@/composables/createAdventure/createAdventureForm'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiRadioCards, { type RadioCardOption } from '@/components/ui/UiRadioCards.vue'
import UiRange from '@/components/ui/UiRange.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const { form } = useCreateAdventureContext()

const SYSTEMS: RadioCardOption<TimeSystem>[] = [
  { value: 'calendar', label: 'Day & clock', icon: Sun, description: 'Day count and clock time, minutes per action.' },
  { value: 'units', label: 'Custom units', icon: Hourglass, description: 'An abstract counter such as cycles or hours.' },
]
const FORMATS = [
  { value: '24h' as const, label: '24 h' },
  { value: '12h' as const, label: '12 h' },
]

const config = computed<Required<TimeConfigData>>(() => {
  const tc = form.value.time_config || {}
  return {
    day_label: tc.day_label || 'Day',
    initial_day: tc.initial_day ?? 1,
    start_time: tc.start_time || '08:00',
    time_format: tc.time_format || '24h',
    pacing_minutes: tc.pacing_minutes ?? form.value.pacing_minutes ?? 5,
    max_time_per_turn: tc.max_time_per_turn ?? null,
    unit_name: tc.unit_name || 'Units',
    initial_units: tc.initial_units ?? 0,
    units_per_turn: tc.units_per_turn ?? 1,
    max_units_per_turn: tc.max_units_per_turn ?? null,
  }
})

function set<K extends keyof TimeConfigData>(key: K, value: TimeConfigData[K]): void {
  form.value.time_config = { ...config.value, [key]: value }
  if (key === 'pacing_minutes' && typeof value === 'number') form.value.pacing_minutes = value
}

function setNumber(key: 'initial_day' | 'initial_units' | 'units_per_turn', value: unknown, fallback: number): void {
  const number = typeof value === 'number' && Number.isFinite(value) ? value : fallback
  set(key, number)
}

// Switching to manual starts from the defaults, so the shown values are also what is sent.
watch(
  () => form.value.time_auto,
  (auto) => {
    if (!auto && !form.value.time_config) form.value.time_config = { ...config.value }
  },
)
</script>

<template>
  <UiCard title="Time" description="How in-game time passes with each action.">
    <div class="space-y-5">
      <UiToggle
        v-model="form.time_auto"
        label="Let the AI decide"
        description="Picks the time system, start time and pacing that fit the story."
      />
      <template v-if="!form.time_auto">
        <UiToggle v-model="form.clock_enabled" label="Clock runs" description="Off: the adventure has no advancing time." />
        <template v-if="form.clock_enabled">
          <UiRadioCards v-model="form.time_system" :options="SYSTEMS" label="Time system" />
          <div v-if="form.time_system === 'calendar'" class="space-y-4">
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <UiField label="Day label">
                <UiInput :model-value="config.day_label" maxlength="30" placeholder="Day, Sol, Cycle" @update:model-value="(v) => set('day_label', String(v ?? ''))" />
              </UiField>
              <UiField label="Start day">
                <UiInput type="number" :model-value="config.initial_day" min="1" max="10000" @update:model-value="(v) => setNumber('initial_day', v, 1)" />
              </UiField>
              <UiField label="Start time">
                <UiInput type="time" :model-value="config.start_time" @update:model-value="(v) => set('start_time', String(v || '08:00'))" />
              </UiField>
              <UiField label="Clock format">
                <UiSegmented :model-value="config.time_format" :options="FORMATS" label="Clock format" @update:model-value="(v) => set('time_format', v)" />
              </UiField>
            </div>
            <UiField label="Minutes per action" hint="In-game minutes that pass with each player action.">
              <UiRange :model-value="config.pacing_minutes" :min="1" :max="60" unit=" min" @update:model-value="(v) => set('pacing_minutes', v)" />
            </UiField>
          </div>
          <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <UiField label="Unit name">
              <UiInput :model-value="config.unit_name" maxlength="30" placeholder="Hours, cycles, light-years" @update:model-value="(v) => set('unit_name', String(v ?? ''))" />
            </UiField>
            <UiField label="Start value">
              <UiInput type="number" :model-value="config.initial_units" min="0" max="10000" @update:model-value="(v) => setNumber('initial_units', v, 0)" />
            </UiField>
            <UiField label="Units per action">
              <UiInput type="number" :model-value="config.units_per_turn" min="1" max="100" @update:model-value="(v) => setNumber('units_per_turn', v, 1)" />
            </UiField>
          </div>
        </template>
      </template>
    </div>
  </UiCard>
</template>
