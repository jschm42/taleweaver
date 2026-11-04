import { API_BASE, authHeaders } from '@/services/http'

export type VisualKind = 'cover' | 'protagonist' | 'scene' | 'npc' | 'object'

export interface VisualUploadSpec {
  maxWidth: number
  maxHeight: number
  maxBytes: number
  hint: string
}

export interface VisualUploadLimits {
  cover: VisualUploadSpec
  protagonist: VisualUploadSpec
  scene: VisualUploadSpec
  npc: VisualUploadSpec
  object: VisualUploadSpec
}

/**
 * Service for visual asset operations (generation, upload, regeneration)
 */
export const visualService = {
  UPLOAD_LIMITS: {
    cover: {
      maxWidth: 2048,
      maxHeight: 2048,
      maxBytes: 8 * 1024 * 1024,
      hint: 'Optimal: portrait 2:3 (1024x1536) or landscape 16:9, max 2048x2048. PNG, JPEG, or WEBP.',
    },
    protagonist: {
      maxWidth: 1536,
      maxHeight: 2048,
      maxBytes: 8 * 1024 * 1024,
      hint: 'Optimal: portrait 2:3 (1024x1536), max 1536x2048. PNG, JPEG, or WEBP.',
    },
    scene: {
      maxWidth: 2048,
      maxHeight: 1536,
      maxBytes: 8 * 1024 * 1024,
      hint: 'Optimal: landscape 16:9 / 3:2 (1536x1024), max 2048x1536. PNG, JPEG, or WEBP.',
    },
    npc: {
      maxWidth: 1536,
      maxHeight: 2048,
      maxBytes: 8 * 1024 * 1024,
      hint: 'Optimal: portrait 2:3 (1024x1536), max 1536x2048. PNG, JPEG, or WEBP.',
    },
    object: {
      maxWidth: 1536,
      maxHeight: 1536,
      maxBytes: 8 * 1024 * 1024,
      hint: 'Optimal: square 1:1 (1024x1024), max 1536x1536. PNG, JPEG, or WEBP.',
    },
  } as const,

  ALLOWED_MIME_TYPES: new Set(['image/png', 'image/jpeg', 'image/webp']),
  ALLOWED_EXTENSIONS: new Set(['png', 'jpg', 'jpeg', 'webp']),

  async quickRegenerateVisual(
    adventureId: string,
    kind: VisualKind,
    id: string,
    signal?: AbortSignal
  ): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/visuals/regenerate`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({ target_type: kind, target_id: id, prompt: null }),
      signal,
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || 'Generation failed')
    }
  },

  async regenerateVisual(
    adventureId: string,
    kind: VisualKind,
    id: string,
    prompt: string | null,
    useAdvancedModel: boolean,
    signal?: AbortSignal,
    applyStyle: boolean = true,
    applyAppearance: boolean = true
  ): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/visuals/regenerate`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({
        target_type: kind,
        target_id: id,
        prompt: prompt?.trim() || null,
        use_advanced_model: useAdvancedModel,
        apply_style: applyStyle,
        apply_appearance: applyAppearance,
      }),
      signal,
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || 'Failed to regenerate.')
    }
  },

  async suggestPrompt(
    adventureId: string,
    kind: VisualKind,
    id: string,
    applyAppearance: boolean = true
  ): Promise<string> {
    const res = await fetch(
      `${API_BASE}/adventures/${adventureId}/visuals/suggest-prompt`,
      {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify({
          target_type: kind,
          target_id: id,
          apply_appearance: applyAppearance,
        }),
      }
    )
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || 'Failed to suggest prompt')
    }
    const data = await res.json()
    return data?.suggested_prompt || ''
  },

  async enhancePrompt(
    adventureId: string,
    prompt: string,
    kind?: VisualKind,
    id?: string,
    applyAppearance: boolean = true,
    appearance?: string
  ): Promise<string> {
    const res = await fetch(
      `${API_BASE}/adventures/${adventureId}/visuals/enhance-prompt`,
      {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify({
          prompt,
          target_type: kind || null,
          target_id: id || null,
          apply_appearance: applyAppearance,
          appearance: applyAppearance ? (appearance || null) : null,
        }),
      }
    )
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || 'Failed to enhance prompt')
    }
    const data = await res.json()
    return data?.enhanced_prompt || ''
  },

  async uploadVisual(
    adventureId: string,
    kind: VisualKind,
    id: string,
    file: File
  ): Promise<void> {
    const payload = new FormData()
    payload.append('target_type', kind)
    payload.append('target_id', id)
    payload.append('file', file)

    const res = await fetch(`${API_BASE}/adventures/${adventureId}/visuals/upload`, {
      method: 'POST',
      headers: authHeaders(false),
      body: payload,
    })
    if (!res.ok) throw new Error('Upload failed.')
  },

  getImageDimensions(file: File): Promise<{ width: number; height: number }> {
    const objectUrl = URL.createObjectURL(file)
    return new Promise<{ width: number; height: number }>((resolve, reject) => {
      const image = new Image()
      image.onload = () => {
        URL.revokeObjectURL(objectUrl)
        resolve({ width: image.width, height: image.height })
      }
      image.onerror = () => {
        URL.revokeObjectURL(objectUrl)
        reject(new Error('Could not read image dimensions.'))
      }
      image.src = objectUrl
    })
  },

  validateFile(file: File): { valid: boolean; error?: string } {
    const ext = file.name.includes('.') ? file.name.split('.').pop()?.toLowerCase() || '' : ''

    if (!this.ALLOWED_MIME_TYPES.has(file.type)) {
      return { valid: false, error: 'Unsupported file type. Please use PNG, JPEG, or WEBP.' }
    }

    if (!this.ALLOWED_EXTENSIONS.has(ext)) {
      return { valid: false, error: 'Unsupported file extension.' }
    }

    return { valid: true }
  },

  validateDimensions(
    width: number,
    height: number,
    spec: VisualUploadSpec
  ): { valid: boolean; error?: string } {
    if (width > spec.maxWidth || height > spec.maxHeight) {
      return {
        valid: false,
        error: `Image too large: ${width}x${height}. Max is ${spec.maxWidth}x${spec.maxHeight}.`,
      }
    }
    return { valid: true }
  },

  buildImageUrl(imagePath: string | null | undefined, cacheVersion: number): string {
    if (!imagePath) return ''
    return `${imagePath}?v=${cacheVersion}`
  },
}
