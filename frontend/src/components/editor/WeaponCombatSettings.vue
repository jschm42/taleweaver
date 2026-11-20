<script setup lang="ts">
import { computed } from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'
import { AMOUNT_PATTERN, EFFECT_STATS, STAT_SHORT, SUCCESS_STATS } from '@/utils/specialAttacks'
import {
  DEFAULT_WEAPON_HIT_STAT,
  DICE_PATTERN,
  MAX_WEAPON_EFFECTS,
  WEAPON_CATEGORIES,
  WEAPON_CATEGORY_META,
  type WeaponConfig,
} from '@/utils/weaponConfig'
import type { SuccessStat } from '@/types'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const props = withDefaults(defineProps<{ title?: string }>(), { title: 'Weapon attack' })

const config = defineModel<WeaponConfig>({ required: true })

const CATEGORY_OPTIONS = WEAPON_CATEGORIES.map((c) => ({ value: c, label: WEAPON_CATEGORY_META[c].label }))
const HIT_STAT_OPTIONS = [
  { value: '', label: `${STAT_SHORT[DEFAULT_WEAPON_HIT_STAT]} (default)` },
  ...SUCCESS_STATS.map((s) => ({ value: s, label: STAT_SHORT[s] })),
]
const COST_OPTIONS = [
  { value: 'stamina', label: 'Stamina' },
  { value: 'mana', label: 'Mana' },
]
const EFFECT_TARGET_OPTIONS = [
  { value: 'target', label: 'Target' },
  { value: 'self', label: 'Wielder' },
]
const EFFECT_STAT_OPTIONS = EFFECT_STATS.map((s) => ({ value: s, label: STAT_SHORT[s] }))

/** The select works with '' for "default"; the config stores null. */
const hitStat = computed({
  get: (): string => config.value.hit_stat ?? '',
  set: (value: string) => {
    config.value.hit_stat = (value || null) as SuccessStat | null
  },
})
const diceValid = computed(() => DICE_PATTERN.test(config.value.damage_dice.replace(/\s/g, '')))

function addEffect(): void {
  if (config.value.effects.length >= MAX_WEAPON_EFFECTS) return
  config.value.effects.push({ target: 'target', stat: 'stamina', amount: '-1d4' })
}

function validAmount(amount: string): boolean {
  return AMOUNT_PATTERN.test(amount.replace(/\s/g, ''))
}
</script>

<template>
  <UiSection :title="props.title">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <UiField label="Category">
        <UiSelect v-model="config.category" :options="CATEGORY_OPTIONS" />
      </UiField>
      <UiField label="Attack roll stat">
        <UiSelect :model-value="hitStat" :options="HIT_STAT_OPTIONS" @update:model-value="(value) => (hitStat = String(value ?? ''))" />
      </UiField>
      <UiField label="Damage (dice)" :error="diceValid ? null : 'Use dice notation, e.g. 1d8+1.'">
        <UiInput v-model="config.damage_dice" mono placeholder="1d8+1" />
      </UiField>
      <div class="grid grid-cols-2 gap-3">
        <UiField label="Cost per attack">
          <UiInput
            type="number"
            min="0"
            :model-value="config.cost_value"
            @update:model-value="(value) => (config.cost_value = Number(value ?? 0))"
          />
        </UiField>
        <UiField label="Paid with">
          <UiSelect v-model="config.cost_type" :options="COST_OPTIONS" />
        </UiField>
      </div>
    </div>

    <div class="space-y-2">
      <div class="flex items-center justify-between gap-3">
        <p class="wb-label">Extra effects on hit</p>
        <UiButton size="sm" variant="ghost" :icon="Plus" :disabled="config.effects.length >= MAX_WEAPON_EFFECTS" @click="addEffect">
          Add effect
        </UiButton>
      </div>
      <div v-for="(eff, idx) in config.effects" :key="idx" class="flex items-center gap-2">
        <UiSelect v-model="eff.target" size="sm" :options="EFFECT_TARGET_OPTIONS" class="w-32" aria-label="Effect target" />
        <UiSelect v-model="eff.stat" size="sm" :options="EFFECT_STAT_OPTIONS" class="w-28" aria-label="Effect stat" />
        <UiInput v-model="eff.amount" size="sm" class="w-28" mono placeholder="-1d4" :invalid="!validAmount(eff.amount)" aria-label="Effect amount" />
        <UiIconButton :icon="Trash2" label="Remove effect" size="sm" variant="danger" @click="config.effects.splice(idx, 1)" />
      </div>
      <p class="wb-hint">
        Applied on every hit, e.g. poison (Target STA -1d4) or life drain (Wielder HP +2). Negative amounts drain,
        positive ones boost; attribute changes last until the fight ends.
      </p>
    </div>
  </UiSection>
</template>
