import { API_BASE, authHeaders } from '@/services/http'

/**
 * Debug inspector downloads (backend: api/routes/adventures/session_debug_exports.py):
 * every image of the session as a ZIP, or one session NPC / item as a .twe bundle.
 */

function filenameFrom(res: Response, fallback: string): string {
  const header = res.headers.get('content-disposition') || ''
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header)?.[1]
  if (encoded) return decodeURIComponent(encoded)
  const plain = /filename="?([^";]+)"?/i.exec(header)?.[1]
  return plain || fallback
}

async function download(url: string, fallbackName: string): Promise<void> {
  const res = await fetch(url, { headers: authHeaders() })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Download failed')
  }
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filenameFrom(res, fallbackName)
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}

export const sessionDebugExportService = {
  /** All scene, NPC, item and protagonist images of the session (incl. dynamic ones). */
  downloadSessionImages(gameId: string): Promise<void> {
    return download(
      `${API_BASE}/adventures/${encodeURIComponent(gameId)}/session-debug/images.zip`,
      'session_images.zip',
    )
  },

  /** One NPC or item of the session as a .twe bundle (importable in the editor). */
  exportSessionEntity(gameId: string, entityId: string): Promise<void> {
    return download(
      `${API_BASE}/adventures/${encodeURIComponent(gameId)}/session-debug/export/${encodeURIComponent(entityId)}`,
      `${entityId}.twe`,
    )
  },
}
