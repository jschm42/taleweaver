import { apiFetch } from '@/services/http'

/** How the GM narrates (diction, rhythm, attitude). Mirrors backend/core/narrator_voices.py. */
export interface NarratorVoice {
  id: string
  name: string
  description?: string
  instruction: string
  sample?: string
}

export interface NarratorVoiceCatalog {
  items: NarratorVoice[]
  /** Built-in voices, used by the admin's "Restore defaults". */
  defaults: NarratorVoice[]
}

export const CUSTOM_VOICE_ID = 'custom'
export const VOICE_INSTRUCTION_MAX = 1500
export const VOICE_SAMPLE_MAX = 500

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail || `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

export const narratorVoiceService = {
  async load(): Promise<NarratorVoiceCatalog> {
    return readJson<NarratorVoiceCatalog>(await apiFetch('/settings/narrator-voices'))
  },

  /** Replaces the admin catalog; an empty list restores the defaults. */
  async save(items: NarratorVoice[]): Promise<NarratorVoice[]> {
    const res = await apiFetch('/settings/narrator-voices', {
      method: 'POST',
      includeJson: true,
      body: JSON.stringify({ items }),
    })
    return (await readJson<{ items: NarratorVoice[] }>(res)).items
  },
}
