/** Shapes shared by the protagonist page panels (`components/editor/protagonist/`). */
import type { SpecialAttack, Talent } from '@/types'

export type ItemRef = string | { id?: string | null } | null | undefined

export interface ProtagonistData {
  id: string
  name?: string
  role?: string
  description?: string
  goal?: string
  character?: string
  appearance?: string
  voice?: string | null
  profile_image?: string | null
  hp?: number | null
  stamina?: number | null
  mana?: number | null
  strength?: number | null
  dexterity?: number | null
  intelligence?: number | null
  wisdom?: number | null
  charisma?: number | null
  armor_class?: number | null
  exp?: number | null
  inventory?: ItemRef[] | null
  equipment?: Record<string, ItemRef> | null
  stats?: { special_actions?: SpecialAttack[]; talents?: Talent[] } | null
  on_hp_change_script?: string | null
  on_hp_change_text?: string | null
  on_status_change_script?: string | null
  on_status_change_text?: string | null
}

export type { ReferenceOption } from '@/components/editor/EntityReferenceCombobox.vue'

export type CreateItemTarget = { type: 'equipment' | 'inventory'; key?: string; index?: number }

/** Item id of an inventory entry or equipment slot (stored as id or as item object). */
export function itemRefId(item: ItemRef): string {
  if (!item) return ''
  return typeof item === 'string' ? item : item.id || ''
}
