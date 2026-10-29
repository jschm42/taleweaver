import type { SpecialEffect, SuccessStat } from '@/types'
import { AMOUNT_PATTERN, EFFECT_STATS, STAT_SHORT, SUCCESS_STATS } from '@/utils/specialAttacks'

/** Mirrors backend/engine/combat/weapons.py. */
export type WeaponCategory = 'MELEE' | 'RANGED' | 'MAGIC'
export const WEAPON_CATEGORIES: WeaponCategory[] = ['MELEE', 'RANGED', 'MAGIC']
export const WEAPON_CATEGORY_META: Record<WeaponCategory, { label: string; icon: string }> = {
  MELEE: { label: 'Melee', icon: 'ra-sword' },
  RANGED: { label: 'Ranged', icon: 'ra-crossbow' },
  MAGIC: { label: 'Magic', icon: 'ra-crystal-wand' },
}
/** Every weapon rolled DEX before the setting existed; keep that as the default. */
export const DEFAULT_WEAPON_HIT_STAT: SuccessStat = 'dexterity'
export const MAX_WEAPON_EFFECTS = 4
export const DICE_PATTERN = /^\d+d\d+([+-]\d+)?$/i

/** Editor state of a WEAPON item's combat settings (stored in its metadata_json). */
export interface WeaponConfig {
  damage_dice: string
  cost_type: 'stamina' | 'mana'
  cost_value: number
  category: WeaponCategory
  /** null = default (DEX). */
  hit_stat: SuccessStat | null
  effects: SpecialEffect[]
}

/** Combat profile the fight UI shows for an equipped weapon. */
export interface WeaponProfile {
  category: WeaponCategory
  hitStat: SuccessStat
  effects: SpecialEffect[]
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

function validEffects(raw: unknown): SpecialEffect[] {
  if (!Array.isArray(raw)) return []
  return raw
    .map(asRecord)
    .filter((e) => (e.target === 'target' || e.target === 'self')
      && EFFECT_STATS.includes(e.stat as SpecialEffect['stat'])
      && AMOUNT_PATTERN.test(String(e.amount ?? '')))
    .map((e) => ({ target: e.target, stat: e.stat, amount: String(e.amount) }) as SpecialEffect)
    .slice(0, MAX_WEAPON_EFFECTS)
}

function category(raw: unknown): WeaponCategory {
  const value = String(raw ?? '').toUpperCase() as WeaponCategory
  return WEAPON_CATEGORIES.includes(value) ? value : 'MELEE'
}

function hitStat(raw: unknown): SuccessStat | null {
  const value = String(raw ?? '').toLowerCase() as SuccessStat
  return SUCCESS_STATS.includes(value) ? value : null
}

/** Reads the weapon settings from an item's metadata (or top-level manifest fields). */
export function readWeaponConfig(...sources: unknown[]): WeaponConfig {
  const pick = (key: string): unknown => sources.map(asRecord).map((s) => s[key]).find((v) => v !== undefined && v !== null && v !== '')
  const cost = Number(pick('weapon_cost_value'))
  return {
    damage_dice: String(pick('damage_dice') || '1d8'),
    cost_type: pick('weapon_cost_type') === 'mana' ? 'mana' : 'stamina',
    cost_value: Number.isFinite(cost) ? cost : 20,
    category: category(pick('weapon_category')),
    hit_stat: hitStat(pick('weapon_hit_stat')),
    effects: validEffects(pick('weapon_effects')),
  }
}

/** Entity update request fields for a weapon config. */
export function weaponPayload(config: WeaponConfig | undefined): Record<string, unknown> {
  if (!config) return {}
  return {
    damage_dice: config.damage_dice.replace(/\s/g, '').toLowerCase(),
    weapon_cost_type: config.cost_type,
    weapon_cost_value: Math.max(0, Number(config.cost_value) || 0),
    weapon_category: config.category,
    weapon_hit_stat: config.hit_stat ?? DEFAULT_WEAPON_HIT_STAT,
    weapon_effects: config.effects.map((e) => ({ ...e, amount: e.amount.replace(/\s/g, '') })),
  }
}

export function weaponProfile(metadata: unknown): WeaponProfile {
  const meta = asRecord(metadata)
  return {
    category: category(meta.weapon_category),
    hitStat: hitStat(meta.weapon_hit_stat) ?? DEFAULT_WEAPON_HIT_STAT,
    effects: validEffects(meta.weapon_effects),
  }
}

export function weaponCheckLabel(stat: SuccessStat): string {
  return `${STAT_SHORT[stat]} vs AC`
}
