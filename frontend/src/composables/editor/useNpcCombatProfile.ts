/**
 * State of an NPC's combat profile: attributes, armor class and main attack. They are stored
 * together (PUT editor/npc-profile), so the entity form keeps one instance for its Stats tab
 * (attributes) and its Combat tab (main attack). Registers with the entity form's subforms, so
 * "Save changes" stores it; outside the form the caller shows its own save button.
 */
import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import type { NpcMainAttack, SuccessStat } from '@/types'
import { specialAttackService } from '@/services/specialAttackService'
import { useEntitySubform } from '@/components/editor/entity/entitySubforms'
import { AMOUNT_PATTERN, SUCCESS_STATS } from '@/utils/specialAttacks'
import { DEFAULT_WEAPON_HIT_STAT, DICE_PATTERN, type WeaponConfig } from '@/utils/weaponConfig'

/** Mirrors backend/engine/combat/npc_attack.py (stats stored as absolute values, AC as offset to 10). */
export const BASE_AC = 10
export const STAT_RANGE = { min: 1, max: 30 }
export const AC_RANGE = { min: 1, max: 40 }

export type NpcProfileSource = {
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

export interface NpcCombatProfileState {
  stats: Ref<Record<SuccessStat, number>>
  armorClass: Ref<number>
  hasAttack: Ref<boolean>
  attackName: Ref<string>
  attack: Ref<WeaponConfig>
  /** Deprecated weapon / armor items the NPC still references. */
  legacyItems: ComputedRef<string[]>
  problems: ComputedRef<string[]>
  isDirty: () => boolean
  /** Saves through the profile endpoint; throws on validation or request errors. */
  persist: () => Promise<void>
  /** True when an entity form saves the profile (no own save button needed). */
  embedded: boolean
}

export function emptyAttack(): WeaponConfig {
  return { damage_dice: '1d6', cost_type: 'stamina', cost_value: 0, category: 'MELEE', hit_stat: null, effects: [] }
}

function statValue(value: number | null | undefined): number {
  return typeof value === 'number' ? value : 10
}

function inRange(value: number, range: { min: number; max: number }): boolean {
  return Number.isInteger(value) && value >= range.min && value <= range.max
}

export function useNpcCombatProfile(
  adventureId: () => string | undefined | null,
  npc: () => NpcProfileSource | null | undefined,
): NpcCombatProfileState {
  const stats = ref<Record<SuccessStat, number>>({ strength: 10, dexterity: 10, intelligence: 10, wisdom: 10, charisma: 10 })
  const armorClass = ref(BASE_AC)
  const hasAttack = ref(false)
  const attackName = ref('')
  const attack = ref<WeaponConfig>(emptyAttack())
  // Last loaded state, to tell whether the profile changed.
  const loaded = ref('')

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

  function profilePayload() {
    return { ...stats.value, armor_class: Number(armorClass.value), main_attack: mainAttackPayload() }
  }

  function load(source: NpcProfileSource): void {
    stats.value = {
      strength: statValue(source.stat_modifier_strength),
      dexterity: statValue(source.stat_modifier_dexterity),
      intelligence: statValue(source.stat_modifier_intelligence),
      wisdom: statValue(source.stat_modifier_wisdom),
      charisma: statValue(source.stat_modifier_charisma),
    }
    armorClass.value = BASE_AC + (source.stat_modifier_armor_class ?? 0)
    const stored = source.metadata_json?.main_attack
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
    loaded.value = JSON.stringify(profilePayload())
  }

  watch(
    () => {
      const source = npc()
      return source ? `${source.id}:${JSON.stringify(source)}` : ''
    },
    () => {
      const source = npc()
      if (source) load(source)
    },
    { immediate: true },
  )

  const legacyItems = computed(() => {
    const meta = npc()?.metadata_json ?? {}
    return [meta.equipped_weapon_id, meta.equipped_armor_id].filter(Boolean) as string[]
  })

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

  const isDirty = (): boolean => !!npc() && JSON.stringify(profilePayload()) !== loaded.value

  async function persist(): Promise<void> {
    const source = npc()
    const adventure = adventureId()
    if (!source || !adventure) return
    if (problems.value.length) throw new Error(problems.value[0])
    await specialAttackService.saveNpcProfile(adventure, source.id, profilePayload())
    loaded.value = JSON.stringify(profilePayload())
  }

  const embedded = useEntitySubform({
    label: 'Combat profile',
    isDirty,
    error: () => problems.value[0] ?? null,
    save: persist,
  })

  return { stats, armorClass, hasAttack, attackName, attack, legacyItems, problems, isDirty, persist, embedded }
}
