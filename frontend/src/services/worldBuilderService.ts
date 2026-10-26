import { API_BASE, authHeaders } from '@/services/http'
import type { FixProposal } from '@/services/adventureService'

export const WORLD_BUILDER_INSTRUCTION_MAX = 2000

export interface WorldBuilderSuggestionsResponse {
  instruction: string
  proposals: FixProposal[]
  note?: string | null
  generated_at: string
  error?: string | null
}

export interface WorldBuilderApplyResponse {
  status: 'applied' | 'no_op' | 'partial'
  applied_targets: string[]
  message?: string | null
}

async function postJson<T>(url: string, body: unknown, fallbackError: string): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: authHeaders(true),
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const respData = await res.json().catch(() => ({}))
    const detail = typeof respData.detail === 'string' ? respData.detail : null
    throw new Error(detail || fallbackError)
  }
  return res.json()
}

export const worldBuilderService = {
  requestSuggestions(
    adventureId: string,
    instruction: string,
  ): Promise<WorldBuilderSuggestionsResponse> {
    return postJson(
      `${API_BASE}/adventures/${adventureId}/editor/world-builder/suggest`,
      { instruction },
      'Failed to request World-Builder suggestions.',
    )
  },

  applyProposal(adventureId: string, proposal: FixProposal): Promise<WorldBuilderApplyResponse> {
    return postJson(
      `${API_BASE}/adventures/${adventureId}/editor/world-builder/apply`,
      { proposal },
      'Failed to apply the World-Builder proposal.',
    )
  },
}
