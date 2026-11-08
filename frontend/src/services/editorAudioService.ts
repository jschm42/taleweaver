import { apiFetch } from '@/services/http'

/** A track of the adventure's audio library. Mirrors backend/engine/audio/audio_library.py. */
export interface AudioTrack {
  id: string
  name: string
  prompt: string
  /** Null for a planned track (prompt only, not rendered yet). */
  url: string | null
  source: 'generated' | 'uploaded' | 'planned'
  reference_scene_id: string | null
  created_at: string | null
}

/** A background render; it can take minutes while the provider loads its model. */
export interface AudioJob {
  id: string
  status: 'running' | 'done' | 'failed'
  elapsed: number
  url?: string
  bytes?: number
  error?: string
  track_id?: string
}

export interface AudioLibrary {
  tracks: AudioTrack[]
  /** track id -> ids of the scenes that play it */
  scene_usage: Record<string, string[]>
  /** track id -> latest render job */
  jobs: Record<string, AudioJob>
  audio_enabled: boolean
  /** Track played on the adventure's library tile; null = no title track. */
  title_track_id: string | null
  generation: { enabled: boolean; provider: 'comfyui' | 'lyria' }
}

export interface NewTrack {
  /** Empty: suggested from the name. */
  id?: string
  name: string
  prompt: string
  reference_scene_id?: string | null
  duration?: number | null
}

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail || `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

function base(adventureId: string): string {
  return `/adventures/${encodeURIComponent(adventureId)}/audio`
}

function send(path: string, method: string, body?: unknown): Promise<Response> {
  return apiFetch(path, {
    method,
    includeJson: body !== undefined,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export const editorAudioService = {
  async load(adventureId: string): Promise<AudioLibrary> {
    return readJson<AudioLibrary>(await apiFetch(base(adventureId)))
  },

  /** AI prompt from the adventure tone and the reference scene (or the premise); always loopable. */
  async suggestPrompt(adventureId: string, referenceSceneId?: string | null): Promise<string> {
    const res = await send(`${base(adventureId)}/suggest-prompt`, 'POST', {
      reference_scene_id: referenceSceneId || null,
    })
    return (await readJson<{ suggested_prompt: string }>(res)).suggested_prompt
  },

  async generate(adventureId: string, track: NewTrack): Promise<{ track: AudioTrack; job: AudioJob }> {
    return readJson(await send(`${base(adventureId)}/tracks`, 'POST', track))
  },

  async render(adventureId: string, trackId: string, duration?: number | null): Promise<AudioJob> {
    const res = await send(`${base(adventureId)}/tracks/${encodeURIComponent(trackId)}/render`, 'POST', {
      duration: duration || null,
    })
    return readJson<AudioJob>(res)
  },

  async upload(adventureId: string, file: File, name: string, trackId = ''): Promise<AudioTrack> {
    const body = new FormData()
    body.append('file', file)
    body.append('name', name)
    body.append('track_id', trackId)
    // Uploads of large files can take longer than the default request timeout.
    const res = await apiFetch(`${base(adventureId)}/tracks/upload`, { method: 'POST', body, timeoutMs: 300000 })
    return (await readJson<{ track: AudioTrack }>(res)).track
  },

  async update(adventureId: string, trackId: string, changes: Partial<Pick<AudioTrack, 'id' | 'name' | 'prompt'>>): Promise<AudioTrack> {
    const res = await send(`${base(adventureId)}/tracks/${encodeURIComponent(trackId)}`, 'PATCH', changes)
    return (await readJson<{ track: AudioTrack }>(res)).track
  },

  async remove(adventureId: string, trackId: string): Promise<AudioLibrary> {
    return readJson<AudioLibrary>(await send(`${base(adventureId)}/tracks/${encodeURIComponent(trackId)}`, 'DELETE'))
  },

  async jobStatus(adventureId: string, jobId: string): Promise<AudioJob> {
    return readJson<AudioJob>(await apiFetch(`${base(adventureId)}/jobs/${encodeURIComponent(jobId)}`))
  },

  /** The scene's track; null makes the scene silent (the previous audio fades out). */
  async setSceneTrack(adventureId: string, sceneId: string, trackId: string | null): Promise<void> {
    await readJson(await send(`${base(adventureId)}/scenes/${encodeURIComponent(sceneId)}/track`, 'POST', { track_id: trackId }))
  },

  /** The adventure's title track (library tile preview); null removes it. */
  async setTitleTrack(adventureId: string, trackId: string | null): Promise<void> {
    await readJson(await send(`${base(adventureId)}/title`, 'POST', { track_id: trackId }))
  },

  /** Author switch for scene audio (script audio via tw.audio is not affected). */
  async setEnabled(adventureId: string, enabled: boolean): Promise<void> {
    await readJson(await send(`/adventures/${encodeURIComponent(adventureId)}`, 'PATCH', { audio_enabled: enabled }))
  },
}
