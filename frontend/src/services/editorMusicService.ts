import { apiFetch } from '@/services/http'

/** Music of a scene (`scene` + scene id) or the adventure's main theme (`theme`). */
export interface MusicTarget {
  target_type: 'scene' | 'theme'
  target_id?: string | null
}

export interface MusicFields {
  music_prompt?: string | null
  music_url?: string | null
}

/** A background render; it can take minutes while the provider loads its model. */
export interface MusicJob {
  id: string
  status: 'running' | 'done' | 'failed'
  elapsed: number
  url?: string
  bytes?: number
  error?: string
}

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail || `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

function post(path: string, body: unknown): Promise<Response> {
  return apiFetch(path, { method: 'POST', includeJson: true, body: JSON.stringify(body) })
}

function base(adventureId: string): string {
  return `/adventures/${encodeURIComponent(adventureId)}/music`
}

export const editorMusicService = {
  /** AI prompt from the adventure tone and the scene; always ends with a loop instruction. */
  async suggestPrompt(adventureId: string, target: MusicTarget): Promise<string> {
    const res = await post(`${base(adventureId)}/suggest-prompt`, target)
    return (await readJson<{ suggested_prompt: string }>(res)).suggested_prompt
  },

  async savePrompt(adventureId: string, target: MusicTarget, prompt: string): Promise<MusicFields> {
    return readJson<MusicFields>(await post(`${base(adventureId)}/prompt`, { ...target, prompt }))
  },

  async generate(adventureId: string, target: MusicTarget, prompt: string, duration?: number): Promise<MusicJob> {
    const res = await post(`${base(adventureId)}/generate`, { ...target, prompt, duration })
    return readJson<MusicJob>(res)
  },

  async jobStatus(adventureId: string, jobId: string): Promise<MusicJob> {
    return readJson<MusicJob>(await apiFetch(`${base(adventureId)}/jobs/${encodeURIComponent(jobId)}`))
  },

  async remove(adventureId: string, target: MusicTarget): Promise<MusicFields> {
    return readJson<MusicFields>(await post(`${base(adventureId)}/remove`, target))
  },

  /** Author switch for scene and theme music (script music is not affected). */
  async setEnabled(adventureId: string, enabled: boolean): Promise<void> {
    const res = await apiFetch(`/adventures/${encodeURIComponent(adventureId)}`, {
      method: 'PATCH',
      includeJson: true,
      body: JSON.stringify({ music_enabled: enabled }),
    })
    await readJson<unknown>(res)
  },
}
