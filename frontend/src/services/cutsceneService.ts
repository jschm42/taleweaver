/**
 * Cut-scene library of an adventure (`AdventureTemplate.cutscenes`): editor calls and helpers.
 * Endpoints: backend/api/routes/adventures/editing/cutscene_routes.py.
 * Spec: docs/specs/cutscenes.md.
 */
import { API_BASE, authHeaders } from '@/services/http'
import type { CutsceneDefinition } from '@/types'

export { MAX_SLIDES, cutscenesOf, newCutscene, newSlide, suggestCutsceneId } from '@/services/cutsceneLibrary'

/** Image model of a slide image: the fast simple model or the high-fidelity one. */
export type SlideImageQuality = 'simple' | 'advanced'

export interface SlidePromptInfo {
  prompt: string
  /** Image style instruction that applies (the cut-scene's override or the adventure's). */
  style: string
  tone: string
}

function base(adventureId: string): string {
  return `${API_BASE}/adventures/${encodeURIComponent(adventureId)}/editor/cutscenes`
}

async function send<T>(url: string, init: RequestInit, fallback: string): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : fallback)
  }
  return await res.json() as T
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: authHeaders(true), body: JSON.stringify(body) }
}

export const cutsceneService = {
  saveCutscenes(adventureId: string, cutscenes: CutsceneDefinition[]): Promise<{ cutscenes: CutsceneDefinition[] }> {
    return send(base(adventureId), json('PUT', { cutscenes }), 'Failed to save the cut-scenes.')
  },

  /** The default prompt of a slide image plus the style and tone that apply. */
  slidePrompt(adventureId: string, title: string, text: string, imageStyle: string): Promise<SlidePromptInfo> {
    return send(
      `${base(adventureId)}/image-prompt`,
      json('POST', { title, text, image_style: imageStyle }),
      'Failed to load the image prompt.',
    )
  },

  /** Draws one slide image; the URL goes into the draft. `signal` cancels the request. */
  generateImage(
    adventureId: string,
    payload: { prompt: string, image_style: string, use_style: boolean, use_tone: boolean, quality: SlideImageQuality },
    signal?: AbortSignal,
  ): Promise<{ url: string, prompt: string }> {
    return send(`${base(adventureId)}/image`, { ...json('POST', payload), signal }, 'Failed to generate the image.')
  },

  uploadImage(adventureId: string, file: File): Promise<{ url: string }> {
    const form = new FormData()
    form.append('file', file)
    return send(
      `${base(adventureId)}/image/upload`,
      { method: 'POST', headers: authHeaders(false), body: form },
      'Failed to upload the image.',
    )
  },
}
