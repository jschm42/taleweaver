/**
 * Side quests (`AdventureTemplate.quests` without `is_main`): list, AI drafts and save. Saving a
 * quest or deleting one stores the whole quest list at once (`handleUpdateQuests`).
 */
import { computed, ref, type ComputedRef, type Ref } from 'vue'
import type { EditorContext } from '@/composables/editor/editorContext'
import { entityService } from '@/services/entityService'
import { MAX_EDITOR_ID_LENGTH, generateEditorId } from '@/utils/editor_utils'

/** One quest as stored in the template. */
export type Quest = Record<string, any>

export const QUEST_TITLE_MAX = 100
export const QUEST_DESCRIPTION_MAX = 1000

export interface SideQuests {
  quests: ComputedRef<Quest[]>
  isGeneratingQuest: Ref<boolean>
  isGeneratingDescription: Ref<boolean>
  blankQuest: (title?: string, description?: string) => Quest
  editableCopy: (quest: Quest) => Quest
  /** Drafts a whole new quest with the LLM; null on error (shown as toast). */
  draftQuest: (exceptId?: string) => Promise<{ title: string; description: string } | null>
  /** Writes an AI description for the quest's title into the draft. */
  draftDescription: (quest: Quest) => Promise<void>
  save: (quest: Quest, isNew: boolean) => void
  remove: (id: string) => void
}

function parseQuests(raw: unknown): Quest[] {
  if (Array.isArray(raw)) return raw
  if (typeof raw !== 'string') return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

export function useSideQuests(editor: EditorContext): SideQuests {
  const adventure = computed(() => editor.adventure as Record<string, any> | null)
  const allQuests = computed(() => parseQuests(adventure.value?.quests))
  const quests = computed(() => allQuests.value.filter((q) => !q.is_main))
  const isGeneratingQuest = ref(false)
  const isGeneratingDescription = ref(false)

  function blankQuest(title = '', description = ''): Quest {
    return {
      id: generateEditorId({
        prefix: 'QUEST_',
        sourceName: title,
        takenIds: quests.value.map((q) => String(q.id || '')),
        maxLen: MAX_EDITOR_ID_LENGTH,
      }),
      title,
      description,
      goal: '',
      impact: '',
      exp_reward: 50,
      is_main: false,
      status: 'open',
      required_item_id: '',
      required_scene_id: '',
      required_defeated_npc_id: '',
      guard_expression: '',
    }
  }

  function editableCopy(quest: Quest): Quest {
    return {
      id: quest.id,
      title: quest.title || '',
      description: quest.description || '',
      goal: quest.goal || '',
      impact: quest.impact || '',
      exp_reward: quest.exp_reward ?? 50,
      is_main: false,
      status: quest.status || 'open',
      required_item_id: quest.required_item_id || '',
      required_scene_id: quest.required_scene_id || '',
      required_defeated_npc_id: quest.required_defeated_npc_id || '',
      guard_expression: quest.guard_expression || quest.completion_guard_expression || '',
    }
  }

  async function draftQuest(exceptId?: string): Promise<{ title: string; description: string } | null> {
    if (!adventure.value?.id) return null
    isGeneratingQuest.value = true
    try {
      const others = quests.value.filter((q) => q.id !== exceptId)
      return await entityService.generateNewQuest(adventure.value.id, false, others)
    } catch (error) {
      editor.addNotification(errorText(error, 'Failed to generate a quest.'), 'error')
      return null
    } finally {
      isGeneratingQuest.value = false
    }
  }

  async function draftDescription(quest: Quest): Promise<void> {
    if (!adventure.value?.id || !quest.title) return
    isGeneratingDescription.value = true
    try {
      const others = quests.value.filter((q) => q.id !== quest.id)
      const result = await entityService.generateQuestDescription(adventure.value.id, quest.title, false, others)
      quest.description = result.description
    } catch (error) {
      editor.addNotification(errorText(error, 'Failed to generate the quest description.'), 'error')
    } finally {
      isGeneratingDescription.value = false
    }
  }

  function save(quest: Quest, isNew: boolean): void {
    const list = [...allQuests.value]
    const next = { ...quest, is_main: false }
    const index = isNew ? -1 : list.findIndex((q) => q.id === quest.id)
    if (index === -1) list.push(next)
    else list[index] = next
    editor.handleUpdateQuests(list)
  }

  function remove(id: string): void {
    editor.handleUpdateQuests(allQuests.value.filter((q) => q.id !== id))
  }

  return {
    quests,
    isGeneratingQuest,
    isGeneratingDescription,
    blankQuest,
    editableCopy,
    draftQuest,
    draftDescription,
    save,
    remove,
  }
}
