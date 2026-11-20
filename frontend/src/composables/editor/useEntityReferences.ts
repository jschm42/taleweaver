/**
 * Items, scenes and characters of the adventure as pick-list references (id, name, type), e.g.
 * for completion rules of chapters, side quests and awards (`HardRuleTriggersEditor`).
 */
import { computed, type ComputedRef } from 'vue'
import type { EditorContext } from '@/composables/editor/editorContext'

export interface EntityReference {
  id: string
  name: string
  type: 'OBJECT' | 'SCENE' | 'NPC'
}

export interface EntityReferences {
  items: ComputedRef<EntityReference[]>
  scenes: ComputedRef<EntityReference[]>
  npcs: ComputedRef<EntityReference[]>
  /** Items, scenes and characters in one list. */
  all: ComputedRef<EntityReference[]>
}

function toReferences(list: any[], type: EntityReference['type'], fallback: string): EntityReference[] {
  return list
    .map((entry) => ({
      id: String(entry.id || entry.entity_id || '').trim(),
      name: String(entry.label || entry.name || entry.id || fallback),
      type,
    }))
    .filter((entry) => Boolean(entry.id))
}

export function useEntityReferences(editor: EditorContext): EntityReferences {
  const adventure = computed(() => editor.adventure as Record<string, any> | null)
  const pick = (editorList: unknown, fallbackKey: string): any[] =>
    Array.isArray(editorList) && editorList.length ? editorList : (adventure.value?.[fallbackKey] ?? [])

  const items = computed(() => toReferences(pick(editor.editorAllItems, 'objects'), 'OBJECT', 'Unnamed item'))
  const scenes = computed(() => toReferences(pick(editor.editorScenes, 'scenes'), 'SCENE', 'Unnamed scene'))
  const npcs = computed(() => toReferences(pick(editor.editorNpcs, 'npcs'), 'NPC', 'Unnamed character'))
  const all = computed(() => [...items.value, ...scenes.value, ...npcs.value])

  return { items, scenes, npcs, all }
}
