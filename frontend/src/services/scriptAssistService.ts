import { API_BASE, authHeaders } from '@/services/http'

export const SCRIPT_ASSIST_INSTRUCTION_MAX = 2000

export type ScriptAssistMode = 'optimize' | 'generate'

export interface ScriptAssistRequest {
  mode: ScriptAssistMode
  code: string
  instruction?: string
  /** Trigger context of the editor, e.g. 'on_pickup' or 'guard_expression'. */
  context: string
  label?: string
}

export interface ScriptAssistResponse {
  code: string | null
  summary?: string | null
  /** Sandbox errors the proposal still has; empty when it passed the check. */
  syntax_errors: string[]
  error?: string | null
}

export const scriptAssistService = {
  async requestProposal(adventureId: string, body: ScriptAssistRequest): Promise<ScriptAssistResponse> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/scripts/assist`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const respData = await res.json().catch(() => ({}))
      const detail = typeof respData.detail === 'string' ? respData.detail : null
      throw new Error(detail || 'Failed to request an AI proposal for the script.')
    }
    return res.json()
  },
}
