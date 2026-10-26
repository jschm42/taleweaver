/**
 * Streaming speech (ElevenLabs): the backend relays audio while it is generated, and an
 * <audio> element plays it progressively. The element cannot send the auth header, so a
 * single-use token is requested first (see backend/api/routes/tts_stream_api.py).
 */
import { api } from '@/composables/useApi'
import { buildApiUrl } from '@/services/http'

/** The active provider does not stream (Gemini); callers fall back to whole-file playback. */
export class StreamingUnavailableError extends Error {}

function errorStatus(err: unknown): number | undefined {
  const status = (err as { status?: unknown } | null)?.status
  return typeof status === 'number' ? status : undefined
}

/** Prepares a stream and returns an <audio> element that starts buffering right away. */
export async function prepareStreamElement(text: string, voiceOverride?: string): Promise<HTMLAudioElement> {
  let token: string
  try {
    ;({ token } = await api.prepareTtsStream({ text, voice_override: voiceOverride }))
  } catch (err) {
    if (errorStatus(err) === 409) throw new StreamingUnavailableError('Streaming is not used by this provider.')
    throw err
  }
  const element = new Audio()
  element.preload = 'auto'
  element.src = buildApiUrl(`/tts/stream/${encodeURIComponent(token)}`)
  return element
}

/** Stops buffering and frees the element (a paused element would keep downloading). */
export function releaseStreamElement(element: HTMLAudioElement): void {
  element.pause()
  element.removeAttribute('src')
  element.load()
}

/**
 * Plays the element to the end. `register` receives a settle callback so stop() can end the
 * promise (a paused element never fires 'ended').
 */
export function playStreamElement(
  element: HTMLAudioElement,
  playbackRate: number,
  register: (settle: () => void) => void,
): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    register(resolve)
    element.playbackRate = playbackRate
    element.onended = () => resolve()
    element.onerror = () => {
      reject(new Error(`Audio stream failed - code:${element.error?.code ?? '?'} msg:${element.error?.message ?? '?'}`))
    }
    element.play().catch(reject)
  })
}
