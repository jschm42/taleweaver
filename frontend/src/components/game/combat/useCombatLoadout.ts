import { computed, type Ref } from 'vue'
import type { CharacterSheet, CombatState, InventoryItem } from '@/types'
import { weaponProfile, type WeaponProfile } from '@/utils/weaponConfig'

/** Mirrors equipped_weapons() in backend/engine/combat/weapons.py. */
const WEAPON_SLOT_ORDER = ['MainHand', 'OffHand']

export interface CombatWeapon extends WeaponProfile {
  /** Item id sent as `--with`; null for Bare Fists. */
  id: string | null
  slot: string | null
  name: string
  dice: string
  costType: 'mana' | 'stamina'
  cost: number
}

function num(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function toWeapon(slot: string | null, item: InventoryItem | null): CombatWeapon {
  const meta = ((item?.metadata_json as Record<string, unknown>) || {}) as Record<string, unknown>
  return {
    id: item?.id ?? null,
    slot,
    name: item?.name || 'Bare Fists',
    dice: String(meta.damage_dice || item?.damage_dice || '1d8'),
    costType: meta.weapon_cost_type === 'mana' ? 'mana' : 'stamina',
    cost: num(meta.weapon_cost_value, 20),
    ...weaponProfile(meta),
  }
}

function equippedWeapons(equipment: Record<string, unknown>): CombatWeapon[] {
  const legacyMainHand = equipment.main_hand && !equipment.MainHand ? { MainHand: equipment.main_hand } : {}
  const slots = { ...equipment, ...legacyMainHand } as Record<string, unknown>
  const order = [...WEAPON_SLOT_ORDER, ...Object.keys(slots).filter((s) => !WEAPON_SLOT_ORDER.includes(s) && s !== 'main_hand')]
  const seen = new Set<string>()
  const weapons: CombatWeapon[] = []
  for (const slot of order) {
    const item = slots[slot] as InventoryItem | null | undefined
    if (!item || typeof item !== 'object') continue
    const isWeapon = String(item.item_type || '').toUpperCase() === 'WEAPON'
    const key = String(item.id || item.name || slot)
    // MainHand always counts (anything held there is swung); other slots only for weapons.
    if ((slot !== 'MainHand' && !isWeapon) || seen.has(key)) continue
    seen.add(key)
    weapons.push(toWeapon(slot, item))
  }
  return weapons
}

/** Current protagonist resources and the weapons they can attack with during a fight. */
export function useCombatLoadout(combat: Ref<CombatState>, playerSheet: Ref<CharacterSheet | null>) {
  const resources = computed(() => ({
    mana: num(combat.value.player?.mana, num(playerSheet.value?.mana)),
    stamina: num(combat.value.player?.stamina, num(playerSheet.value?.stamina)),
  }))

  const weapons = computed<CombatWeapon[]>(() => {
    const held = equippedWeapons((playerSheet.value?.equipment || {}) as Record<string, unknown>)
    return held.length ? held : [toWeapon(null, null)]
  })

  /** The default weapon (what a plain `/attack` uses). */
  const weapon = computed(() => weapons.value[0])

  function canAfford(w: CombatWeapon): boolean {
    return resources.value[w.costType] >= w.cost
  }

  const canAffordWeapon = computed(() => canAfford(weapon.value))

  return { resources, weapons, weapon, canAfford, canAffordWeapon }
}
