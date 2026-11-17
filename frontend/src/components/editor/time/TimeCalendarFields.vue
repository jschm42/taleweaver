<script setup lang="ts">
import { computed } from 'vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import { useTimeSettings } from '@/composables/editor/useTimeSettings'
import { CALENDAR_UNITS, from12h, maxUnit, maxValue, pacingUnit, pacingValue, to12h } from '@/utils/timeSettings'

/** Game day & time system: day label, start, clock format, time per turn and GM limit. */
const time = useTimeSettings()
const { form, errors } = time

const UNIT_OPTIONS = CALENDAR_UNITS.map((unit) => ({ value: unit, label: unit }))
const FORMAT_OPTIONS = [
  { value: '24h' as const, label: '24h' },
  { value: '12h' as const, label: '12h (AM/PM)' },
]
const AMPM_OPTIONS = [
  { value: 'AM' as const, label: 'AM' },
  { value: 'PM' as const, label: 'PM' },
]

const startTime = computed(() => form.time_config?.start_time || '08:00')
const twelve = computed(() => to12h(startTime.value))
const timeFormat = computed({
  get: (): '24h' | '12h' => (form.time_config?.time_format === '12h' ? '12h' : '24h'),
  set: (value) => time.setConfig('time_format', value),
})

function set12h(part: 'hour' | 'minute', value: string | number | null): void {
  const next = { ...twelve.value, [part]: Number(value) }
  time.setConfig('start_time', from12h(next.hour, next.minute, next.ampm))
}

function setAmPm(ampm: 'AM' | 'PM'): void {
  time.setConfig('start_time', from12h(twelve.value.hour, twelve.value.minute, ampm))
}

const toNumber = (value: string | number | null): number | null => (value === null || value === '' ? null : Number(value))
</script>

<template>
  <div class="space-y-8">
    <UiSection title="Start" description="Where the clock stands when the adventure begins.">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <UiField label="Day label" hint="Shown in the HUD and the GM prompt, e.g. Day 1 or Sol 42." :error="errors.day_label">
          <UiInput
            :model-value="form.time_config?.day_label ?? 'Day'"
            maxlength="30"
            placeholder="e.g. Day, Sol, Cycle"
            @update:model-value="time.setConfig('day_label', $event ?? '')"
          />
        </UiField>
        <UiField label="Start day" hint="Day number at the start (1–10,000)." :error="errors.initial_day">
          <UiInput
            type="number"
            min="1"
            max="10000"
            step="1"
            :model-value="form.time_config?.initial_day ?? 1"
            @update:model-value="time.setConfig('initial_day', toNumber($event) ?? 1)"
          />
        </UiField>
        <UiField label="Clock format" hint="24-hour clock (14:00) or 12-hour clock (02:00 PM).">
          <UiSegmented v-model="timeFormat" :options="FORMAT_OPTIONS" label="Clock format" />
        </UiField>
        <UiField label="Start time" hint="Time of day when the adventure begins." :error="errors.start_time">
          <UiInput
            v-if="timeFormat === '24h'"
            type="time"
            :model-value="startTime"
            @update:model-value="time.setConfig('start_time', $event || '08:00')"
          />
          <div v-else class="flex items-center gap-2">
            <UiInput
              type="number"
              min="1"
              max="12"
              class="!w-16 text-center"
              aria-label="Hour (1–12)"
              :model-value="twelve.hour"
              @update:model-value="set12h('hour', $event)"
            />
            <span class="wb-body" aria-hidden="true">:</span>
            <UiInput
              type="number"
              min="0"
              max="59"
              class="!w-16 text-center"
              aria-label="Minute (0–59)"
              :model-value="String(twelve.minute).padStart(2, '0')"
              @update:model-value="set12h('minute', $event)"
            />
            <UiSegmented :model-value="twelve.ampm" :options="AMPM_OPTIONS" label="AM or PM" @update:model-value="setAmPm" />
          </div>
        </UiField>
      </div>
    </UiSection>

    <UiSection title="Pacing" description="How fast time passes." class="border-t border-wb-line pt-6">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <UiField
          label="Time per turn"
          hint="Passes after every narrated player message."
          info="1–10,000 of the chosen unit. Scripts can change it in-game with tw.time.set_minutes_per_tick()."
          :error="errors.pacing"
        >
          <div class="flex gap-2">
            <UiInput
              type="number"
              min="1"
              max="10000"
              step="1"
              class="!w-28"
              aria-label="Time per turn"
              :model-value="pacingValue(form)"
              @update:model-value="time.setPacingValue(toNumber($event))"
            />
            <UiSelect :model-value="pacingUnit(form)" :options="UNIT_OPTIONS" aria-label="Unit of the time per turn" @update:model-value="time.setPacingUnit(String($event))" />
          </div>
        </UiField>
        <UiField
          label="Max time per turn (GM limit)"
          hint="Caps the time per turn plus the GM's extra time. Empty: no cap."
          :error="errors.max_time"
        >
          <div class="flex gap-2">
            <UiInput
              type="number"
              min="1"
              max="10000"
              step="1"
              class="!w-28"
              placeholder="No cap"
              aria-label="Max time per turn"
              :model-value="maxValue(form)"
              @update:model-value="time.setMaxValue(toNumber($event))"
            />
            <UiSelect :model-value="maxUnit(form)" :options="UNIT_OPTIONS" aria-label="Unit of the GM limit" @update:model-value="time.setMaxUnit(String($event))" />
          </div>
        </UiField>
      </div>
    </UiSection>
  </div>
</template>
