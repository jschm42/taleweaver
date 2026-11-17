<script setup lang="ts">
import { computed } from 'vue'
import { Hourglass, Sun } from 'lucide-vue-next'
import PageHeader from '@/components/workbench/PageHeader.vue'
import TimeCalendarFields from '@/components/editor/time/TimeCalendarFields.vue'
import TimeClockPreview from '@/components/editor/time/TimeClockPreview.vue'
import TimeUnitsFields from '@/components/editor/time/TimeUnitsFields.vue'
import UiRadioCards, { type RadioCardOption } from '@/components/ui/UiRadioCards.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiToggle from '@/components/ui/UiToggle.vue'
import { useTimeSettings } from '@/composables/editor/useTimeSettings'

/**
 * Time & pacing: the in-game clock (game days or custom units), its start, the time per turn,
 * the GM limit and whether the GM may change the time. Saved through the editor's save bar.
 */
const { form } = useTimeSettings()

const SYSTEMS: RadioCardOption<'relative' | 'units'>[] = [
  { value: 'relative', label: 'Game day and time', description: 'Day count, time of day and time per turn.', icon: Sun },
  { value: 'units', label: 'Custom time units', description: 'A counter such as lightyears, cycles or sandglasses.', icon: Hourglass },
]

const clockEnabled = computed({
  get: (): boolean => !!form.clock_enabled,
  set: (value) => {
    form.clock_enabled = value
  },
})

const system = computed({
  get: (): 'relative' | 'units' => (form.time_system === 'units' ? 'units' : 'relative'),
  set: (value) => {
    form.time_system = value
  },
})

const gmTimeControl = computed({
  get: (): boolean => form.gm_time_control ?? true,
  set: (value) => {
    form.gm_time_control = value
  },
})
</script>

<template>
  <div class="space-y-8">
    <PageHeader title="Time & pacing" description="The in-game clock: what it counts, where it starts and how fast it runs." />

    <UiToggle
      v-model="clockEnabled"
      label="In-game clock"
      description="Off: the adventure has no clock; time never passes."
    />

    <template v-if="clockEnabled">
      <UiSection title="Time system" class="border-t border-wb-line pt-6">
        <UiRadioCards v-model="system" :options="SYSTEMS" label="Time system" />
      </UiSection>

      <div class="border-t border-wb-line pt-6">
        <TimeUnitsFields v-if="system === 'units'" />
        <TimeCalendarFields v-else />
      </div>

      <div class="border-t border-wb-line pt-6">
        <TimeClockPreview />
      </div>
    </template>

    <div class="border-t border-wb-line pt-6">
      <UiToggle
        v-model="gmTimeControl"
        label="GM may change the time"
        description="The Game Master may add time for long actions (capped by the GM limit). Off: only the time per turn and scripts move the clock; scripts can override this with tw.time.allow_gm_time()."
      />
    </div>
  </div>
</template>
