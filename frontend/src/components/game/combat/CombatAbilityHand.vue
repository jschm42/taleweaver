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
import { useCombatLoadout, type CombatWeapon } from './useCombatLoadout'

const props = defineProps<{
  combat: CombatState
  playerSheet: CharacterSheet | null
  locked: boolean
  targetName: string | null
}>()

const emit = defineEmits<{
  /** Weapon item id to attack with; null for the default weapon (Bare Fists). */
  attack: [weaponId: string | null]
  special: [id: string]
  hover: [entity: Record<string, unknown>, event: MouseEvent]
  leave: []
}>()

/** Card frame colors per category tone (see CATEGORY_META). */
const TONE_HEX: Record<string, string> = {
  weapon: '#d4a24c',
  emerald: '#10b981',
  violet: '#8b5cf6',
  orange: '#f97316',
  green: '#22c55e',
  pink: '#ec4899',
  cyan: '#06b6d4',
}

const { resources, weapons, canAfford } = useCombatLoadout(toRef(props, 'combat'), toRef(props, 'playerSheet'))

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

function weaponCostLabel(w: CombatWeapon): string {
  return `${w.cost} ${w.costType === 'mana' ? 'MP' : 'STA'}`
}

function weaponDisabled(w: CombatWeapon): boolean {
  return props.locked || !canAfford(w) || !props.targetName
}

function weaponEffectsLabel(w: CombatWeapon): string {
  return [`${w.dice} damage`, describeEffects(w.effects)].filter(Boolean).join(' · ')
}

function weaponTypeLine(w: CombatWeapon): string {
  const slot = w.slot && w.slot !== 'MainHand' ? ` · ${w.slot}` : ''
  return `Weapon — ${WEAPON_CATEGORY_META[w.category].label}${slot}`
}

function weaponTooltip(w: CombatWeapon): Record<string, unknown> {
  const onHit = describeEffects(w.effects)
  return {
    id: w.id || 'WEAPON_ATTACK',
    entity_type: 'ITEM',
    item_type: 'WEAPON',
    name: w.name,
    description: [
      w.slot ? `Equipped: ${w.slot}` : 'No weapon equipped.',
      `Cost: ${weaponCostLabel(w)} · Check: ${weaponCheckLabel(w.hitStat)}`,
      `Damage: ${w.dice}`,
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
  <div class="tw-ability-hand" role="toolbar" aria-label="Weapons and abilities">
    <!-- Equipped weapons first, then the special abilities. -->
    <AbilityCard
      v-for="w in weapons"
      :key="w.id || 'bare-fists'"
      :icon="WEAPON_CATEGORY_META[w.category].icon"
      :type-line="weaponTypeLine(w)"
      :title="w.name"
      :cost="weaponCostLabel(w)"
      :check="weaponCheckLabel(w.hitStat)"
      :effects="weaponEffectsLabel(w)"
      :footer="`→ ${targetName || 'no target'}`"
      :tone="TONE_HEX.weapon"
      :disabled="weaponDisabled(w)"
      @use="emit('attack', w.id)"
      @hover="(event) => emit('hover', weaponTooltip(w), event)"
      @leave="emit('leave')"
    />
    <span v-if="specials.length" class="tw-ability-divider" aria-hidden="true"></span>
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
