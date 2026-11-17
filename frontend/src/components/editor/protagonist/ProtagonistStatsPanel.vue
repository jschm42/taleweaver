<script setup lang="ts">
import { reactive, watch } from 'vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSection from '@/components/ui/UiSection.vue'
import type { ProtagonistData } from './protagonistTypes'

/** Resources, attributes, armor and experience of the protagonist. Each value saves when it changes. */
const props = defineProps<{ protagonist: ProtagonistData }>()
const emit = defineEmits<{ 'save-field': [field: string, value: number] }>()

type StatKey = 'hp' | 'stamina' | 'mana' | 'strength' | 'dexterity' | 'intelligence' | 'wisdom' | 'charisma' | 'armor_class' | 'exp'

interface StatDef {
  key: StatKey
  label: string
  min: number
  max: number
  fallback: number
}

const RESOURCES: StatDef[] = [
  { key: 'hp', label: 'Health (HP)', min: 0, max: 999, fallback: 20 },
  { key: 'stamina', label: 'Stamina', min: 0, max: 999, fallback: 20 },
  { key: 'mana', label: 'Mana', min: 0, max: 999, fallback: 20 },
]

const ATTRIBUTES: StatDef[] = [
  { key: 'strength', label: 'Strength', min: 1, max: 99, fallback: 10 },
  { key: 'dexterity', label: 'Dexterity', min: 1, max: 99, fallback: 10 },
  { key: 'intelligence', label: 'Intelligence', min: 1, max: 99, fallback: 10 },
  { key: 'wisdom', label: 'Wisdom', min: 1, max: 99, fallback: 10 },
  { key: 'charisma', label: 'Charisma', min: 1, max: 99, fallback: 10 },
  { key: 'armor_class', label: 'Armor class', min: 1, max: 99, fallback: 10 },
]

const EXPERIENCE: StatDef = { key: 'exp', label: 'Experience', min: 0, max: 999999, fallback: 0 }

const ALL = [...RESOURCES, ...ATTRIBUTES, EXPERIENCE]
const values = reactive<Record<StatKey, number | null>>({} as Record<StatKey, number | null>)

watch(
  () => props.protagonist,
  (p) => {
    for (const stat of ALL) values[stat.key] = p[stat.key] ?? stat.fallback
  },
  { immediate: true, deep: true },
)

function isValid(stat: StatDef): boolean {
  const value = values[stat.key]
  return typeof value === 'number' && Number.isInteger(value) && value >= stat.min && value <= stat.max
}

function errorOf(stat: StatDef): string | null {
  return isValid(stat) ? null : `${stat.min}–${stat.max}`
}

function commit(stat: StatDef): void {
  const value = values[stat.key]
  if (!isValid(stat) || value === (props.protagonist[stat.key] ?? stat.fallback)) return
  emit('save-field', stat.key, value as number)
}
</script>

<template>
  <div class="space-y-8">
    <p class="wb-hint">Each value is saved as soon as you leave the field.</p>

    <UiSection title="Resources" description="Starting values; they are also the maximum.">
      <div class="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <UiField v-for="stat in RESOURCES" :key="stat.key" :label="stat.label" :error="errorOf(stat)">
          <UiInput v-model="values[stat.key]" type="number" :min="stat.min" :max="stat.max" @change="commit(stat)" />
        </UiField>
      </div>
    </UiSection>

    <UiSection
      title="Attributes"
      description="10 is average. Attributes feed skill checks and attack rolls; armor class is what attackers must roll to hit."
      class="border-t border-wb-line pt-6"
    >
      <div class="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <UiField v-for="stat in ATTRIBUTES" :key="stat.key" :label="stat.label" :error="errorOf(stat)">
          <UiInput v-model="values[stat.key]" type="number" :min="stat.min" :max="stat.max" @change="commit(stat)" />
        </UiField>
      </div>
    </UiSection>

    <UiSection title="Progress" class="border-t border-wb-line pt-6">
      <div class="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <UiField :label="EXPERIENCE.label" hint="Starting experience points." :error="errorOf(EXPERIENCE)">
          <UiInput v-model="values.exp" type="number" :min="EXPERIENCE.min" @change="commit(EXPERIENCE)" />
        </UiField>
      </div>
    </UiSection>
  </div>
</template>
