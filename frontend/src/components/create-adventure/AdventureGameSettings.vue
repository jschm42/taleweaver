<script setup lang="ts">
import { watch } from 'vue'
import AdventureRuleModeSelector from './AdventureRuleModeSelector.vue'
import AdventureTimeSettings, { type TimeConfigData } from './AdventureTimeSettings.vue'
import AdventureCombatSettings from './AdventureCombatSettings.vue'

type RuleMode = 'rpg' | 'story' | 'chat'

const props = defineProps<{
  modelValue: {
    rule_enforcement_mode: RuleMode
    clock_enabled: boolean
    pacing_minutes: number
    min_scenes: number | null
    max_scenes: number | null
    min_items: number | null
    max_items: number | null
    quest_generation_enabled: boolean
    min_quests: number | null
    max_quests: number | null
    min_sequences: number | null
    max_sequences: number | null
    container_generation_enabled: boolean
    scripts_generation_enabled?: boolean
    min_containers: number | null
    max_containers: number | null
    text_log_generation_enabled: boolean
    min_text_logs: number | null
    max_text_logs: number | null
    award_generation_enabled: boolean
    min_awards: number | null
    max_awards: number | null
    can_damage_npcs: boolean
    npcs_can_damage_protagonist: boolean
    time_auto?: boolean
    time_system?: 'calendar' | 'units'
    time_config?: TimeConfigData | null
  }
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: any): void
}>()

function update<K extends keyof typeof props.modelValue>(key: K, value: typeof props.modelValue[K]) {
  emit('update:modelValue', {
    ...props.modelValue,
    [key]: value,
  })
}

// Ensure combat permissions are disabled when not in RPG mode
watch(
  () => props.modelValue.rule_enforcement_mode,
  (newMode) => {
    if (newMode !== 'rpg') {
      if (props.modelValue.can_damage_npcs || props.modelValue.npcs_can_damage_protagonist) {
        emit('update:modelValue', {
          ...props.modelValue,
          can_damage_npcs: false,
          npcs_can_damage_protagonist: false,
        })
      }
    }
  },
  { immediate: true }
)
</script>

<template>
  <div class="space-y-6 md:space-y-8">
    <!-- 1. Rule Enforcement Mode -->
    <AdventureRuleModeSelector
      :model-value="modelValue.rule_enforcement_mode"
      @update:model-value="update('rule_enforcement_mode', $event)"
    />

    <!-- 2. Time & Pacing System (with Auto Mode switch) -->
    <AdventureTimeSettings
      :clock-enabled="modelValue.clock_enabled"
      :time-auto="modelValue.time_auto ?? true"
      :time-system="modelValue.time_system ?? 'calendar'"
      :pacing-minutes="modelValue.pacing_minutes"
      :time-config="modelValue.time_config ?? null"
      @update:clock-enabled="update('clock_enabled', $event)"
      @update:time-auto="update('time_auto', $event)"
      @update:time-system="update('time_system', $event)"
      @update:pacing-minutes="update('pacing_minutes', $event)"
      @update:time-config="update('time_config', $event)"
    />

    <!-- 3. Combat Permissions (Active only in RPG Mode) -->
    <AdventureCombatSettings
      :rule-enforcement-mode="modelValue.rule_enforcement_mode"
      :can-damage-npcs="modelValue.can_damage_npcs"
      :npcs-can-damage-protagonist="modelValue.npcs_can_damage_protagonist"
      @update:can-damage-npcs="update('can_damage_npcs', $event)"
      @update:npcs-can-damage-protagonist="update('npcs_can_damage_protagonist', $event)"
    />
  </div>
</template>
