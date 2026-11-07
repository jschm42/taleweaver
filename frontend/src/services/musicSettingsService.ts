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

  /** Renders one clip with the stored workflow; resolves when ComfyUI finished. */
  async test(prompt: string, duration?: number): Promise<{ url: string; bytes: number }> {
    const res = await apiFetch('/settings/music/test', {
      method: 'POST',
      includeJson: true,
      body: JSON.stringify({ prompt, duration }),
    })
    return readJson<{ url: string; bytes: number }>(res)
  },
}
