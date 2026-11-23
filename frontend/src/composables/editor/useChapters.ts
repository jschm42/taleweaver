/**
 * Chapters (story sequences) of the adventure: sorted list, references for the pickers and the
 * list actions. Every change saves the whole list at once (`handleUpdateSequences`).
 */
import { computed, type ComputedRef } from 'vue'
import type { EditorContext } from '@/composables/editor/editorContext'
import { useEntityReferences, type EntityReference } from '@/composables/editor/useEntityReferences'
import { EDITOR_ID_PREFIXES, MAX_EDITOR_ID_LENGTH, generateEditorId, isValidEditorId } from '@/utils/editor_utils'

export const MAX_CHAPTERS = 15

export type ProgressionMode = 'linear' | 'dynamic'

/** One chapter as stored in `AdventureTemplate.sequences`. */
export type Chapter = Record<string, any>

export type ChapterReference = EntityReference

export interface Chapters {
  chapters: ComputedRef<Chapter[]>
  mode: ComputedRef<ProgressionMode>
  scenes: ComputedRef<ChapterReference[]>
  items: ComputedRef<ChapterReference[]>
  npcs: ComputedRef<ChapterReference[]>
  newChapter: () => Chapter
  editableCopy: (chapter: Chapter) => Chapter
  validate: (draft: Chapter, isNew: boolean) => string | null
  save: (draft: Chapter, isNew: boolean) => boolean
  move: (index: number, step: -1 | 1) => void
  remove: (id: string) => void
  setMode: (mode: ProgressionMode) => void
}

function parseSequences(raw: unknown): Chapter[] {
  let list: unknown = raw
  if (typeof raw === 'string') {
    try {
      list = JSON.parse(raw)
    } catch {
      return []
    }
  }
  if (!Array.isArray(list)) return []
  return [...list].sort((a, b) => (Number(a.order) || 0) - (Number(b.order) || 0))
}

function renumber(list: Chapter[]): Chapter[] {
  return list.map((item, i) => ({ ...item, order: i + 1 }))
}

export function useChapters(editor: EditorContext): Chapters {
  const adventure = computed(() => editor.adventure as Record<string, any> | null)
  const chapters = computed(() => parseSequences(adventure.value?.sequences))
  const mode = computed<ProgressionMode>(() => {
    const raw = adventure.value?.sequence_progression_mode || adventure.value?.original_manifest?.sequence_progression_mode
    return raw === 'dynamic' ? 'dynamic' : 'linear'
  })

  const { scenes, items, npcs } = useEntityReferences(editor)

  function newChapter(): Chapter {
    return editableCopy({
      id: generateEditorId({
        prefix: EDITOR_ID_PREFIXES.SEQUENCE,
        takenIds: chapters.value.map((s) => String(s.id || '')),
        maxLen: MAX_EDITOR_ID_LENGTH,
      }),
      order: chapters.value.length + 1,
    })
  }

  function editableCopy(seq: Chapter): Chapter {
    return {
      id: seq.id || `SEQ_${seq.order || 1}`,
      order: seq.order || 1,
      title: seq.title || '',
      description: seq.description || '',
      walkthrough: seq.walkthrough || '',
      end_condition: seq.end_condition || '',
      required_item_id: seq.required_item_id || '',
      required_scene_id: seq.required_scene_id || '',
      required_defeated_npc_id: seq.required_defeated_npc_id || '',
      activation_scene_id: seq.activation_scene_id || '',
      companions_allowed: seq.companions_allowed !== false,
      respawn_allowed: seq.respawn_allowed !== false,
      fast_travel_allowed: seq.fast_travel_allowed !== false,
      guard_expression: seq.guard_expression || seq.completion_guard_expression || '',
      exp_reward: seq.exp_reward ?? 50,
      on_start_sequence_script: seq.on_start_sequence_script || '',
      on_start_sequence_text: seq.on_start_sequence_text || '',
      start_cutscene_id: seq.start_cutscene_id || '',
      on_end_sequence_script: seq.on_end_sequence_script || '',
      on_end_sequence_text: seq.on_end_sequence_text || '',
      helpers_script: seq.helpers_script || '',
      soft_rules: seq.soft_rules ? JSON.parse(JSON.stringify(seq.soft_rules)) : [],
      scripts: seq.scripts ? JSON.parse(JSON.stringify(seq.scripts)) : [],
    }
  }

  function validate(draft: Chapter, isNew: boolean): string | null {
    if (!String(draft.title || '').trim()) return 'The chapter needs a title.'
    const id = String(draft.id || '').trim().toUpperCase()
    if (isNew && !isValidEditorId(id, MAX_EDITOR_ID_LENGTH)) {
      return `The ID may use A–Z, 0–9 and _ only (up to ${MAX_EDITOR_ID_LENGTH} characters).`
    }
    if (isNew && chapters.value.some((s) => String(s.id || '').toUpperCase() === id)) {
      return `A chapter with the ID "${id}" already exists.`
    }
    const rules: any[] = draft.soft_rules || []
    const ruleIds = rules.map((rule) => String(rule.id || '').trim())
    if (rules.some((rule) => !String(rule.condition || '').trim()) || ruleIds.some((ruleId) => !ruleId)) {
      return 'Every soft rule needs an ID and a condition.'
    }
    if (new Set(ruleIds).size !== ruleIds.length) return 'Soft rule IDs must be unique within the chapter.'
    const scriptIds: string[] = (draft.scripts || []).map((script: any) => String(script.id || '').trim())
    if (scriptIds.some((scriptId) => !scriptId) || new Set(scriptIds).size !== scriptIds.length) {
      return 'Every chapter script needs a unique ID.'
    }
    return null
  }

  /** Validates and saves; returns false (with a toast) when the draft is invalid. */
  function save(draft: Chapter, isNew: boolean): boolean {
    const problem = validate(draft, isNew)
    if (problem) {
      editor.addNotification(problem, 'error')
      return false
    }
    const list = [...chapters.value]
    if (isNew) {
      list.push({ ...draft, id: String(draft.id).trim().toUpperCase() })
    } else {
      const index = list.findIndex((s) => s.id === draft.id)
      if (index !== -1) list[index] = { ...draft }
    }
    editor.handleUpdateSequences(renumber(list))
    return true
  }

  function move(index: number, step: -1 | 1): void {
    const target = index + step
    if (target < 0 || target >= chapters.value.length) return
    const list = [...chapters.value]
    ;[list[index], list[target]] = [list[target], list[index]]
    editor.handleUpdateSequences(renumber(list))
  }

  function remove(id: string): void {
    editor.handleUpdateSequences(renumber(chapters.value.filter((s) => s.id !== id)))
  }

  function setMode(next: ProgressionMode): void {
    if (next === mode.value || editor.isSaving) return
    editor.handleUpdateProgressionMode(next)
  }

  return { chapters, mode, scenes, items, npcs, newChapter, editableCopy, validate, save, move, remove, setMode }
}
