import { apiFetch } from '@/services/http'

/** Admin music generation settings. Mirrors backend/core/music_settings.py (workflow summarized). */
export interface MusicSettings {
  enabled: boolean
  provider: 'comfyui'
  comfyui_url: string
  comfyui_timeout: number
  comfyui_workflow_name: string
  comfyui_output_node_id: string
  default_duration: number
  max_duration: number
  max_generations_per_session: number
  has_workflow: boolean
  workflow_node_count: number
}

export type MusicSettingsUpdate = Omit<
  MusicSettings,
  'provider' | 'comfyui_workflow_name' | 'has_workflow' | 'workflow_node_count'
>

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail || `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

export const musicSettingsService = {
  async load(): Promise<MusicSettings> {
    return readJson<MusicSettings>(await apiFetch('/settings/music'))
  },

  async save(values: MusicSettingsUpdate): Promise<MusicSettings> {
    const res = await apiFetch('/settings/music', {
      method: 'POST',
      includeJson: true,
      body: JSON.stringify(values),
    })
    return readJson<MusicSettings>(res)
  },

  /** Uploads an API-format ComfyUI workflow JSON that contains a {{prompt}} placeholder. */
  async uploadWorkflow(file: File): Promise<MusicSettings> {
    const body = new FormData()
    body.append('file', file)
    return readJson<MusicSettings>(await apiFetch('/settings/music/workflow', { method: 'POST', body }))
  },

  async removeWorkflow(): Promise<MusicSettings> {
    return readJson<MusicSettings>(await apiFetch('/settings/music/workflow', { method: 'DELETE' }))
  },

  /** Starts rendering one clip with the stored workflow; poll `testStatus` for the result. */
  async startTest(prompt: string, duration?: number): Promise<MusicTestRun> {
    const res = await apiFetch('/settings/music/test', {
      method: 'POST',
      includeJson: true,
      body: JSON.stringify({ prompt, duration }),
    })
    return readJson<MusicTestRun>(res)
  },

  async testStatus(id: string): Promise<MusicTestRun> {
    return readJson<MusicTestRun>(await apiFetch(`/settings/music/test/${encodeURIComponent(id)}`))
  },
}

/** A background test render; it can take minutes while ComfyUI loads the model. */
export interface MusicTestRun {
  id: string
  status: 'running' | 'done' | 'failed'
  /** Seconds since the run started (until it finished). */
  elapsed: number
  url?: string
  bytes?: number
  error?: string
}
