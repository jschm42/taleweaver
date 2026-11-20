<script setup lang="ts">
// Editor setting for AdventureTemplate.game_over_rules: what happens when the protagonist falls
// to 0 HP. "game_over" ends the adventure; "respawn" revives them at the last revival point
// reached (else the start scene) with a share of their max HP. Saved with the adventure settings.
import { computed } from 'vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'

type GameOverRules = { on_zero_hp?: string; respawn_hp_percent?: number; [key: string]: unknown }

const model = defineModel<GameOverRules | null | undefined>({ required: true })

const DEFAULT_PERCENT = 25
const OPTIONS = [
  { value: 'game_over' as const, label: 'Game over' },
  { value: 'respawn' as const, label: 'Respawn' },
]

const mode = computed({
  get: (): 'game_over' | 'respawn' => (model.value?.on_zero_hp === 'respawn' ? 'respawn' : 'game_over'),
  set: (value: 'game_over' | 'respawn') => {
    model.value = { ...(model.value ?? {}), on_zero_hp: value, respawn_hp_percent: percent.value }
  },
})

const percent = computed((): number => Number(model.value?.respawn_hp_percent ?? DEFAULT_PERCENT) || DEFAULT_PERCENT)

function setPercent(value: string | number | null): void {
  const clamped = Math.max(1, Math.min(100, Math.round(Number(value) || DEFAULT_PERCENT)))
  model.value = { ...(model.value ?? {}), on_zero_hp: mode.value, respawn_hp_percent: clamped }
}
</script>

<template>
  <div class="space-y-3 border-t border-wb-line pt-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <p class="wb-label">At 0 HP</p>
      <UiSegmented v-model="mode" :options="OPTIONS" label="At 0 HP" />
    </div>
    <p class="wb-hint">
      <template v-if="mode === 'respawn'">
        The protagonist is knocked out and wakes up at the last revival point reached (else the start scene). Status
        effects are cleared; enemies keep their HP. Script penalties with the <code class="wb-mono">on_respawn</code> trigger.
      </template>
      <template v-else>Falling to 0 HP ends the adventure.</template>
    </p>
    <UiField v-if="mode === 'respawn'" label="Revive with" hint="Share of max HP, 1–100 %." class="max-w-48">
      <UiInput type="number" min="1" max="100" :model-value="percent" @update:model-value="setPercent" />
    </UiField>
  </div>
</template>
