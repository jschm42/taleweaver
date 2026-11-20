import { API_BASE, authHeaders } from '@/services/http'

export type CompanionTactics = 'BALANCED' | 'OFFENSIVE' | 'DEFENSIVE' | 'SUPPORT'
export type CompanionBanter = 'NORMAL' | 'QUIET' | 'CHATTY'
/** SCRIPT: only tw.party.recruit; INSTANT: Recruit action; ITEM: Recruit dialog wants an item. */
export type CompanionRecruitMode = 'SCRIPT' | 'INSTANT' | 'ITEM'

/** The `companion` block of an NPC (see backend/engine/party/companion_config.py). */
export interface CompanionSettings {
  recruitable: boolean
  starts_in_party: boolean
  tactics: CompanionTactics
  banter: CompanionBanter
  downed_recovery: number
  recruit_mode: CompanionRecruitMode
  recruit_item_id: string
  recruit_hint: string
}

export const DEFAULT_COMPANION: CompanionSettings = {
  recruitable: true,
  starts_in_party: false,
  tactics: 'BALANCED',
  banter: 'NORMAL',
  downed_recovery: 0.25,
  recruit_mode: 'SCRIPT',
  recruit_item_id: '',
  recruit_hint: '',
}

function formatError(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : String(d)))
      .join('; ')
  }
  return 'Failed to save companion settings'
}

export const companionService = {
  /** Stores the NPC's companion settings; `null` makes it an ordinary NPC again. */
  async saveNpcCompanion(
    adventureId: string,
    npcId: string,
    companion: CompanionSettings | null,
  ): Promise<CompanionSettings | null> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/npc-companion`, {
      method: 'PUT',
      headers: authHeaders(true),
      body: JSON.stringify({ npc_id: npcId, companion }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      throw new Error(formatError(data?.detail))
    }
    return (data?.companion ?? null) as CompanionSettings | null
  },
}
