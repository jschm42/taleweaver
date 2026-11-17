<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Save } from 'lucide-vue-next'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSection from '@/components/ui/UiSection.vue'
import type { NpcMainAttack, SuccessStat } from '@/types'
import WeaponCombatSettings from '@/components/editor/WeaponCombatSettings.vue'
import { specialAttackService } from '@/services/specialAttackService'
import { AMOUNT_PATTERN, STAT_SHORT, SUCCESS_STATS } from '@/utils/specialAttacks'
import { DEFAULT_WEAPON_HIT_STAT, DICE_PATTERN, type WeaponConfig } from '@/utils/weaponConfig'

/** Mirrors backend/engine/combat/npc_attack.py (stats stored as absolute values, AC as offset to 10). */
const BASE_AC = 10
const STAT_RANGE = { min: 1, max: 30 }
const AC_RANGE = { min: 1, max: 40 }

type NpcLike = {
  id: string
  name: string
  stat_modifier_strength?: number | null
  stat_modifier_dexterity?: number | null
  stat_modifier_intelligence?: number | null
  stat_modifier_wisdom?: number | null
  stat_modifier_charisma?: number | null
  stat_modifier_armor_class?: number | null
  metadata_json?: {
    main_attack?: Partial<NpcMainAttack> | null
    equipped_weapon_id?: string | null
    equipped_armor_id?: string | null
  } | null
}

const props = defineProps<{
  adventureId: string
  npc: NpcLike
}>()

const emit = defineEmits<{ saved: [] }>()

const stats = ref<Record<SuccessStat, number>>({ strength: 10, dexterity: 10, intelligence: 10, wisdom: 10, charisma: 10 })
const armorClass = ref(BASE_AC)
const hasAttack = ref(false)
const attackName = ref('')
const attack = ref<WeaponConfig>(emptyAttack())
const saving = ref(false)
const note = ref('')
const error = ref('')

function emptyAttack(): WeaponConfig {
  return { damage_dice: '1d6', cost_type: 'stamina', cost_value: 0, category: 'MELEE', hit_stat: null, effects: [] }
}

function statValue(value: number | null | undefined): number {
  return typeof value === 'number' ? value : 10
}

watch(() => `${props.npc.id}:${JSON.stringify(props.npc)}`, () => {
  const npc = props.npc
  stats.value = {
    strength: statValue(npc.stat_modifier_strength),
    dexterity: statValue(npc.stat_modifier_dexterity),
    intelligence: statValue(npc.stat_modifier_intelligence),
    wisdom: statValue(npc.stat_modifier_wisdom),
    charisma: statValue(npc.stat_modifier_charisma),
  }
  armorClass.value = BASE_AC + (npc.stat_modifier_armor_class ?? 0)
  const stored = npc.metadata_json?.main_attack
  hasAttack.value = !!stored
  attackName.value = stored?.name ?? ''
  attack.value = stored
    ? {
        damage_dice: stored.damage_dice ?? '1d6',
        cost_type: stored.cost_type ?? 'stamina',
        cost_value: stored.cost ?? 0,
        category: stored.category ?? 'MELEE',
        hit_stat: stored.hit_stat ?? null,
        effects: (stored.effects ?? []).map((e) => ({ ...e })),
      }
    : emptyAttack()
}, { immediate: true })

const legacyItems = computed(() => {
  const meta = props.npc.metadata_json ?? {}
  return [meta.equipped_weapon_id, meta.equipped_armor_id].filter(Boolean) as string[]
})

const PRESETS: Array<{ label: string; name: string; config: Partial<WeaponConfig> }> = [
  { label: 'Longsword', name: 'Longsword', config: { category: 'MELEE', damage_dice: '1d8', hit_stat: 'strength' } },
  { label: 'Bow', name: 'Bow Shot', config: { category: 'RANGED', damage_dice: '1d6', hit_stat: 'dexterity' } },
  { label: 'Magic Missile', name: 'Magic Missile', config: { category: 'MAGIC', damage_dice: '1d4+1', hit_stat: 'intelligence', cost_type: 'mana', cost_value: 5 } },
  { label: 'Claws', name: 'Claws', config: { category: 'MELEE', damage_dice: '2d4', hit_stat: 'strength' } },
]

function applyPreset(preset: (typeof PRESETS)[number]): void {
  hasAttack.value = true
  attackName.value = preset.name
  attack.value = { ...emptyAttack(), ...preset.config, effects: [] }
}

function inRange(value: number, range: { min: number; max: number }): boolean {
  return Number.isInteger(value) && value >= range.min && value <= range.max
}

const problems = computed(() => {
  const issues: string[] = []
  if (SUCCESS_STATS.some((s) => !inRange(Number(stats.value[s]), STAT_RANGE))) {
    issues.push(`Stats must be whole numbers from ${STAT_RANGE.min} to ${STAT_RANGE.max}.`)
  }
  if (!inRange(Number(armorClass.value), AC_RANGE)) issues.push(`AC must be from ${AC_RANGE.min} to ${AC_RANGE.max}.`)
  if (!hasAttack.value) return issues
  if (!attackName.value.trim()) issues.push('The main attack needs a name.')
  if (!DICE_PATTERN.test(attack.value.damage_dice.replace(/\s/g, ''))) issues.push('Damage must look like 1d8 or 2d6+1.')
  if (attack.value.effects.some((e) => !AMOUNT_PATTERN.test(e.amount.replace(/\s/g, '')))) {
    issues.push('Effect amounts must look like -1d4, +2 or -3.')
  }
  return issues
})

function mainAttackPayload(): NpcMainAttack | null {
  if (!hasAttack.value) return null
  const a = attack.value
  return {
    name: attackName.value.trim(),
    category: a.category,
    damage_dice: a.damage_dice.replace(/\s/g, '').toLowerCase(),
    hit_stat: a.hit_stat ?? DEFAULT_WEAPON_HIT_STAT,
    cost_type: a.cost_type,
    cost: Math.max(0, Number(a.cost_value) || 0),
    effects: a.effects.map((e) => ({ ...e, amount: e.amount.replace(/\s/g, '') })),
  }
}

async function save(): Promise<void> {
  if (problems.value.length) return
  saving.value = true
  note.value = ''
  error.value = ''
  try {
    await specialAttackService.saveNpcProfile(props.adventureId, props.npc.id, {
      ...stats.value,
      armor_class: Number(armorClass.value),
      main_attack: mainAttackPayload(),
    })
    note.value = 'Saved.'
    emit('saved')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save.'
  } finally {
    saving.value = false
  }
}

function toInt(value: string | number | null): number {
  return value === null || value === '' ? Number.NaN : Number(value)
}
</script>

<template>
  <UiSection title="Combat profile" description="Stats, armor and the main attack this character fights with.">
    <div class="grid grid-cols-3 gap-3 md:grid-cols-6">
      <UiField v-for="s in SUCCESS_STATS" :key="s" :label="STAT_SHORT[s]">
        <UiInput
          type="number"
          :min="STAT_RANGE.min"
          :max="STAT_RANGE.max"
          :model-value="stats[s]"
          @update:model-value="(value) => (stats[s] = toInt(value))"
        />
      </UiField>
      <UiField label="AC" info="Armor class: the attack roll an attacker must reach to hit this character.">
        <UiInput
          type="number"
          :min="AC_RANGE.min"
          :max="AC_RANGE.max"
          :model-value="armorClass"
          @update:model-value="(value) => (armorClass = toInt(value))"
        />
      </UiField>
    </div>
    <p class="wb-hint">
      10 is average. Stats feed the attack and special rolls; AC is what the protagonist must roll to hit
      (10 unarmored, 14 leather, 18 plate).
    </p>

    <div class="space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <UiCheckbox v-model="hasAttack" label="Main attack" />
        <div class="flex flex-wrap items-center gap-1.5">
          <span class="wb-hint mr-1">Preset</span>
          <UiButton v-for="preset in PRESETS" :key="preset.label" size="sm" @click="applyPreset(preset)">{{ preset.label }}</UiButton>
        </div>
      </div>
      <p v-if="!hasAttack" class="wb-hint">
        Without a main attack it fights {{ legacyItems.length ? 'with its equipped weapon item (deprecated)' : 'unarmed (1d6)' }}.
      </p>
      <template v-else>
        <UiField label="Attack name" hint="Shown in the combat log.">
          <UiInput v-model="attackName" maxlength="60" placeholder="e.g. Longsword, Bite, Magic Missile" />
        </UiField>
        <WeaponCombatSettings v-model="attack" title="Attack settings" />
      </template>
      <UiNotice v-if="legacyItems.length" tone="warn">
        Still uses deprecated equipment items ({{ legacyItems.join(', ') }}).
        {{ hasAttack ? 'The main attack replaces the weapon item.' : 'Configure a main attack to replace the weapon item.' }}
        Set the armor bonus via AC instead of an armor item.
      </UiNotice>
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <UiButton :icon="Save" :loading="saving" :disabled="problems.length > 0" @click="save">Save combat profile</UiButton>
      <span v-if="note" class="wb-hint !text-wb-accent-text" role="status">{{ note }}</span>
      <span v-if="error" class="wb-hint !text-wb-danger-text" role="alert">{{ error }}</span>
      <span v-for="p in problems" :key="p" class="wb-hint !text-wb-warn-text">{{ p }}</span>
    </div>
  </UiSection>
</template>
