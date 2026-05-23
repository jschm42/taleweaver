import { API_BASE, authHeaders } from '@/services/http'

export interface EntityEditData {
  target_type: string
  target_id: string
  name: string
  teaser?: string
  description: string
  voice?: string
  hp?: number
  stamina?: number
  mana?: number
  goal?: string
  character?: string
  is_killable?: boolean
  item_type?: string
  is_portable?: boolean
  locked?: boolean
  code_to_unlock?: string
  item_to_unlock?: string
  inventory?: any[]
  text_log_content?: string
}

/**
 * Service for entity editing operations
 */
export const entityService = {
  async saveEntityText(adventureId: string, data: EntityEditData): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/entity`, {
      method: 'PATCH',
      headers: authHeaders(true),
      body: JSON.stringify(data),
    })
    if (!res.ok) {
      const respData = await res.json()
      throw new Error(respData.detail || 'Failed to save entity text')
    }
  },

  async generateTraits(adventureId: string, name: string, description: string, targetType: string, targetField?: 'goal' | 'character'): Promise<{ goal: string, character: string }> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/generate-traits`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({
        name,
        description,
        target_type: targetType,
        target_field: targetField
      }),
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || 'Failed to generate traits')
    }
    return await res.json()
  },

  async generateQuestDescription(adventureId: string, title: string, isMain: boolean, otherQuests: any[]): Promise<{ description: string }> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/generate-quest-description`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({
        title,
        is_main: isMain,
        other_quests: otherQuests
      }),
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || 'Failed to generate quest description')
    }
    return await res.json()
  },

  async generateNewQuest(adventureId: string, isMain: boolean, otherQuests: any[]): Promise<{ title: string, description: string }> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/generate-new-quest`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({
        is_main: isMain,
        other_quests: otherQuests
      }),
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || 'Failed to generate new quest')
    }
    return await res.json()
  },
}

