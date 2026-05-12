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

  async runAIEdit(adventureId: string, prompt: string, autoVisualize: boolean): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/ai-edit`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({
        prompt,
        auto_visualize: autoVisualize,
      }),
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || 'Failed to apply AI changes')
    }
  },
}
