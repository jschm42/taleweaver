import { apiFetch } from '@/services/http'

/** Admin audio generation settings. Mirrors backend/core/audio_settings.py (workflow summarized). */
export interface AudioSettings {
  enabled: boolean
  provider: 'comfyui' | 'lyria'
  lyria_clip_model: string
  lyria_full_model: string
  lyria_timeout: number
  lyria_wav: boolean
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

export type AudioSettingsUpdate = Omit<
  AudioSettings,
  'comfyui_workflow_name' | 'has_workflow' | 'workflow_node_count'
>

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail || `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

export const audioSettingsService = {
  async load(): Promise<AudioSettings> {
    return readJson<AudioSettings>(await apiFetch('/settings/audio'))
  },

  async save(values: AudioSettingsUpdate): Promise<AudioSettings> {
    const res = await apiFetch('/settings/audio', {
      method: 'POST',
      includeJson: true,
      body: JSON.stringify(values),
    })
    return readJson<AudioSettings>(res)
  },

  /** Uploads an API-format ComfyUI workflow JSON that contains a {{prompt}} placeholder. */
  async uploadWorkflow(file: File): Promise<AudioSettings> {
    const body = new FormData()
    body.append('file', file)
    return readJson<AudioSettings>(await apiFetch('/settings/audio/workflow', { method: 'POST', body }))
  },

  async removeWorkflow(): Promise<AudioSettings> {
    return readJson<AudioSettings>(await apiFetch('/settings/audio/workflow', { method: 'DELETE' }))
  },

  /** Starts rendering one clip with the stored workflow; poll `testStatus` for the result. */
  async startTest(prompt: string, duration?: number): Promise<AudioTestRun> {
    const res = await apiFetch('/settings/audio/test', {
      method: 'POST',
      includeJson: true,
      body: JSON.stringify({ prompt, duration }),
    })
    return readJson<AudioTestRun>(res)
  },

  async testStatus(id: string): Promise<AudioTestRun> {
    return readJson<AudioTestRun>(await apiFetch(`/settings/audio/test/${encodeURIComponent(id)}`))
  },
}

/** A background test render; it can take minutes while ComfyUI loads the model. */
export interface AudioTestRun {
  id: string
  status: 'running' | 'done' | 'failed'
  /** Seconds since the run started (until it finished). */
  elapsed: number
  url?: string
  bytes?: number
  error?: string
}
