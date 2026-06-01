import { API_BASE, authHeaders } from '@/services/http'

export interface EntityEditData {
  target_type: string
  target_id: string
  name?: string
  teaser?: string
  description?: string
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
  rule_to_unlock?: string
  exit_type?: 'one_way' | 'bidirectional'
  inventory?: any[]
  text_log_content?: string
  text_log_format?: string
}

export interface SceneCreateData {
  scene_id: string
  label: string
  description: string
  image_url?: string
}

export interface ExitCreateData {
  from_scene_id: string
  to_scene_id: string
  label: string
  exit_type?: 'one_way' | 'bidirectional'
  is_locked?: boolean
  lock_description?: string
  code_to_unlock?: string
  item_to_unlock?: string
  rule_to_unlock?: string
}

export interface EntityCreateData {
  entity_id: string
  entity_type: 'NPC' | 'OBJECT'
  scene_id: string
  name: string
  description: string
  image_url?: string
  item_type?: string
  is_portable?: boolean
  goal?: string
  character?: string
  hp?: number
  stamina?: number
  mana?: number
  is_killable?: boolean
  metadata_json?: Record<string, any>
}

export interface QuestCreateData {
  id: string
  title: string
  description?: string
  goal?: string
  impact?: string
  exp_reward?: number
  is_main?: boolean
}

export interface AwardCreateData {
  key: string
  title: string
  description?: string
  tier?: 'bronze' | 'silver' | 'gold'
  requirement?: string
  is_earned?: boolean
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

  async createScene(adventureId: string, data: SceneCreateData): Promise<any> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/scene`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify(data),
    })
    if (!res.ok) {
      const payload = await res.json()
      throw new Error(payload.detail || 'Failed to create scene')
    }
    return await res.json()
  },

  async deleteScene(adventureId: string, sceneId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/scene/${encodeURIComponent(sceneId)}`, {
      method: 'DELETE',
      headers: authHeaders(false),
    })
    if (!res.ok) {
      const payload = await res.json()
      throw new Error(payload.detail || 'Failed to delete scene')
    }
  },

  async createExit(adventureId: string, data: ExitCreateData): Promise<any> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/exit`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify(data),
    })
    if (!res.ok) {
      const payload = await res.json()
      throw new Error(payload.detail || 'Failed to create exit')
    }
    return await res.json()
  },

  async deleteExit(adventureId: string, exitId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/exit/${encodeURIComponent(exitId)}`, {
      method: 'DELETE',
      headers: authHeaders(false),
    })
    if (!res.ok) {
      const payload = await res.json()
      throw new Error(payload.detail || 'Failed to delete exit')
    }
  },

  async createEntity(adventureId: string, data: EntityCreateData): Promise<any> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/entity`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify(data),
    })
    if (!res.ok) {
      const payload = await res.json()
      throw new Error(payload.detail || 'Failed to create entity')
    }
    return await res.json()
  },

  async deleteEntity(adventureId: string, entityId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/entity/${encodeURIComponent(entityId)}`, {
      method: 'DELETE',
      headers: authHeaders(false),
    })
    if (!res.ok) {
      const payload = await res.json()
      throw new Error(payload.detail || 'Failed to delete entity')
    }
  },

  async createQuest(adventureId: string, data: QuestCreateData): Promise<any> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/quest`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify(data),
    })
    if (!res.ok) {
      const payload = await res.json()
      throw new Error(payload.detail || 'Failed to create quest')
    }
    return await res.json()
  },

  async deleteQuest(adventureId: string, questId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/quest/${encodeURIComponent(questId)}`, {
      method: 'DELETE',
      headers: authHeaders(false),
    })
    if (!res.ok) {
      const payload = await res.json()
      throw new Error(payload.detail || 'Failed to delete quest')
    }
  },

  async createAward(adventureId: string, data: AwardCreateData): Promise<any> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/award`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify(data),
    })
    if (!res.ok) {
      const payload = await res.json()
      throw new Error(payload.detail || 'Failed to create award')
    }
    return await res.json()
  },

  async deleteAward(adventureId: string, awardKey: string): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/award/${encodeURIComponent(awardKey)}`, {
      method: 'DELETE',
      headers: authHeaders(false),
    })
    if (!res.ok) {
      const payload = await res.json()
      throw new Error(payload.detail || 'Failed to delete award')
    }
  },
}

