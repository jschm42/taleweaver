<script setup lang="ts">
import { computed, toRef } from 'vue'
import type { CharacterSheet, CombatState, NormalizedSpecialAttack } from '@/types'
import {
  areaLabel,
  CATEGORY_META,
  checkLabel,
  isAreaAttack,
  costLabel,
  describeEffects,
  normalizeSpecialAttack,
} from '@/utils/specialAttacks'
import { WEAPON_CATEGORY_META, weaponCheckLabel } from '@/utils/weaponConfig'
import AbilityCard from './AbilityCard.vue'
import { useCombatLoadout } from './useCombatLoadout'

const props = defineProps<{
  combat: CombatState
  playerSheet: CharacterSheet | null
  locked: boolean
  targetName: string | null
}>()

const emit = defineEmits<{
  attack: []
  special: [id: string]
  hover: [entity: Record<string, unknown>, event: MouseEvent]
  leave: []
}>()

/** Card frame colors per category tone (see CATEGORY_META). */
const TONE_HEX: Record<string, string> = {
  emerald: '#10b981',
  violet: '#8b5cf6',
  orange: '#f97316',
  green: '#22c55e',
  pink: '#ec4899',
  cyan: '#06b6d4',
}

const { resources, weapon, canAffordWeapon } = useCombatLoadout(toRef(props, 'combat'), toRef(props, 'playerSheet'))

const specials = computed<NormalizedSpecialAttack[]>(() => {
  const fromCombat = props.combat.player?.special_actions
  if (fromCombat?.length) return fromCombat
  const unlocked = new Set(props.playerSheet?.unlocked_actions ?? [])
  return (props.playerSheet?.special_actions ?? []).map((a) => ({
    ...normalizeSpecialAttack(a),
    locked: !unlocked.has(a.id),
  }))
})

function canUse(action: NormalizedSpecialAttack): boolean {
  if (action.locked) return false
  if (action.targets_enemy && !props.targetName) return false
  return resources.value[action.cost_type] >= action.cost
}

function actionKind(action: NormalizedSpecialAttack): string {
  if (isAreaAttack(action)) return 'Area Attack'
  if (action.targets_enemy) return 'Attack'
  return action.action_type === 'HEAL' ? 'Heal' : 'Utility'
}

function specialFooter(action: NormalizedSpecialAttack): string {
  if (action.locked) return 'Locked'
  return action.targets_enemy ? `→ ${areaLabel(action, props.targetName)}` : '→ Self'
}

const weaponCostLabel = computed(() => `${weapon.value.cost} ${weapon.value.costType === 'mana' ? 'MP' : 'STA'}`)
const attackDisabled = computed(() => props.locked || !canAffordWeapon.value || !props.targetName)

const weaponEffectsLabel = computed(() => (
  [`${weapon.value.dice} damage`, describeEffects(weapon.value.effects)].filter(Boolean).join(' · ')
))

function weaponTooltip(): Record<string, unknown> {
  const onHit = describeEffects(weapon.value.effects)
  return {
    id: 'WEAPON_ATTACK',
    entity_type: 'ITEM',
    item_type: 'WEAPON',
    name: weapon.value.name,
    description: [
      'Basic weapon attack.',
      `Cost: ${weaponCostLabel.value} · Check: ${weaponCheckLabel(weapon.value.hitStat)}`,
      `Damage: ${weapon.value.dice}`,
      onHit ? `On hit: ${onHit}` : '',
    ].filter(Boolean).join('\n'),
  }
}

function specialTooltip(action: NormalizedSpecialAttack): Record<string, unknown> {
  const lockNote = action.locked ? ` (Locked${action.unlock_condition_target ? `: requires ${action.unlock_condition_target}` : ''})` : ''
  return {
    id: action.id,
    entity_type: 'ITEM',
    item_type: 'SPECIAL',
    name: `${action.name}${lockNote}`,
    description: [
      action.description,
      `Cost: ${costLabel(action)} · Check: ${checkLabel(action)}`,
      isAreaAttack(action) ? `Area: ${areaLabel(action, props.targetName)}` : '',
      `Effects: ${describeEffects(action.effects) || 'narrative only'}`,
    ].filter(Boolean).join('\n'),
  }
}
</script>

<template>
  <div class="tw-ability-hand" role="toolbar" aria-label="Abilities">
    <AbilityCard
      :icon="WEAPON_CATEGORY_META[weapon.category].icon"
      :type-line="`Weapon — ${WEAPON_CATEGORY_META[weapon.category].label}`"
      :title="weapon.name"
      :cost="weaponCostLabel"
      :check="weaponCheckLabel(weapon.hitStat)"
      :effects="weaponEffectsLabel"
      :footer="`→ ${targetName || 'no target'}`"
      :tone="TONE_HEX.emerald"
      :disabled="attackDisabled"
      @use="emit('attack')"
      @hover="(event) => emit('hover', weaponTooltip(), event)"
      @leave="emit('leave')"
    />
    <AbilityCard
      v-for="action in specials"
      :key="action.id"
      :icon="CATEGORY_META[action.category].icon"
      :type-line="`${CATEGORY_META[action.category].label} — ${actionKind(action)}`"
      :title="action.name"
      :cost="costLabel(action)"
      :check="checkLabel(action)"
      :effects="describeEffects(action.effects) || 'Narrative only'"
      :footer="specialFooter(action)"
      :tone="TONE_HEX[CATEGORY_META[action.category].tone]"
      :disabled="locked || !canUse(action)"
      :locked="action.locked"
      @use="emit('special', action.id)"
      @hover="(event) => emit('hover', specialTooltip(action), event)"
      @leave="emit('leave')"
    />
  </div>
</template>
