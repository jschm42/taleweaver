import type { CharacterSheet } from '@/types'

/** Tabs of the hero dialog (CharacterSheetModal). */
export type SheetTabId = 'hero' | 'inventory' | 'equipment' | 'ailments' | 'specials'

/** The sheet fields the equipment panel reads; the companion page passes its own values. */
export type EquipmentSheet = Pick<
  CharacterSheet,
  'equipment' | 'inventory' | 'strength' | 'dexterity' | 'intelligence' | 'wisdom' | 'charisma' | 'armor_class' | 'rule_enforcement_mode'
>
