/**
 * Awards (achievements) of the adventure: list, validation and save. Saving an award or deleting
 * one stores the whole award list at once (`handleUpdateAwards`).
 */
import { computed, type ComputedRef } from 'vue'
import type { EditorContext } from '@/composables/editor/editorContext'
import { EDITOR_ID_PREFIXES, MAX_EDITOR_ID_LENGTH, generateEditorId, isValidEditorId } from '@/utils/editor_utils'

/** `negative` marks a penalty award (e.g. for a blunder), see docs/world-builder-syntax.md. */
export type AwardTier = 'bronze' | 'silver' | 'gold' | 'negative'

/** One award as stored in the template. */
export type Award = Record<string, any>

export const AWARD_TITLE_MAX = 100
export const AWARD_DESCRIPTION_MAX = 1000

export interface Awards {
  awards: ComputedRef<Award[]>
  blankAward: () => Award
  editableCopy: (award: Award) => Award
  /** Validates and saves; returns false (with a toast) when the award is invalid. */
  save: (award: Award, isNew: boolean) => boolean
  remove: (key: string) => void
}

function parseAwards(raw: unknown): Award[] {
  if (Array.isArray(raw)) return raw
  if (typeof raw !== 'string') return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function hasHardRules(award: Award): boolean {
  return Boolean(
    award.required_item_id ||
      award.required_scene_id ||
      award.required_defeated_npc_id ||
      String(award.guard_expression || '').trim(),
  )
}

export function useAwards(editor: EditorContext): Awards {
  const awards = computed(() => parseAwards((editor.adventure as Record<string, any> | null)?.awards))

  function editableCopy(award: Award): Award {
    return {
      key: award.key || '',
      title: award.title || '',
      description: award.description || '',
      tier: award.tier || 'bronze',
      requirement: award.requirement || '',
      is_earned: award.is_earned || false,
      required_item_id: award.required_item_id || '',
      required_scene_id: award.required_scene_id || '',
      required_defeated_npc_id: award.required_defeated_npc_id || '',
      guard_expression: award.guard_expression || '',
    }
  }

  function blankAward(): Award {
    return editableCopy({
      key: generateEditorId({
        prefix: EDITOR_ID_PREFIXES.AWARD,
        takenIds: awards.value.map((a) => String(a.key || '')),
        maxLen: MAX_EDITOR_ID_LENGTH,
      }),
    })
  }

  function validate(award: Award, isNew: boolean): string | null {
    if (!String(award.title || '').trim() || !String(award.description || '').trim()) {
      return 'The award needs a title and a description.'
    }
    if (!isNew) return null
    const key = String(award.key || '').trim().toUpperCase()
    if (!isValidEditorId(key, MAX_EDITOR_ID_LENGTH)) {
      return `The key may use A–Z, 0–9 and _ only (up to ${MAX_EDITOR_ID_LENGTH} characters).`
    }
    if (awards.value.some((a) => String(a.key || '').toUpperCase() === key)) {
      return `An award with the key "${key}" already exists.`
    }
    return null
  }

  function save(award: Award, isNew: boolean): boolean {
    const problem = validate(award, isNew)
    if (problem) {
      editor.addNotification(problem, 'error')
      return false
    }
    const list = [...awards.value]
    if (isNew) {
      list.push({ ...award, key: String(award.key).trim().toUpperCase() })
    } else {
      const index = list.findIndex((a) => String(a.key) === String(award.key))
      if (index !== -1) list[index] = { ...award }
    }
    editor.handleUpdateAwards(list)
    return true
  }

  function remove(key: string): void {
    editor.handleUpdateAwards(awards.value.filter((a) => String(a.key) !== key))
  }

  return { awards, blankAward, editableCopy, save, remove }
}
