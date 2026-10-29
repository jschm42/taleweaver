import { computed, type Ref } from 'vue'
import type { CharacterSheet, CombatState, InventoryItem } from '@/types'

function num(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

/** Current protagonist resources and equipped weapon profile during a fight. */
export function useCombatLoadout(combat: Ref<CombatState>, playerSheet: Ref<CharacterSheet | null>) {
  const resources = computed(() => ({
    mana: num(combat.value.player?.mana, num(playerSheet.value?.mana)),
    stamina: num(combat.value.player?.stamina, num(playerSheet.value?.stamina)),
  }))

  const weapon = computed(() => {
    const eq = playerSheet.value?.equipment || {}
    const item = (eq.MainHand || eq.main_hand || null) as InventoryItem | null
    const meta = ((item?.metadata_json as Record<string, unknown>) || {}) as Record<string, unknown>
    const costType = meta.weapon_cost_type === 'mana' ? 'mana' : 'stamina'
    return {
      name: item?.name || 'Bare Fists',
      dice: String(meta.damage_dice || item?.damage_dice || '1d8'),
      costType,
      cost: num(meta.weapon_cost_value, 20),
    } as const
  })

  const canAffordWeapon = computed(() => resources.value[weapon.value.costType] >= weapon.value.cost)

  return { resources, weapon, canAffordWeapon }
}
