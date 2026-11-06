import { audioService } from '@/services/audioService'

/** How long to wait for queued speech to start before assuming nothing will be read. */
export const SPEECH_START_GRACE_MS = 4000
const POLL_INTERVAL_MS = 250

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

export function isSpeechBusy(): boolean {
  return audioService.isPlaying.value || audioService.isGenerating.value
}

/**
 * Resolves once the queued text-to-speech has been read aloud. Without auto-speech it returns
 * at once. Speech may start a moment after the text arrived, so it first waits up to `graceMs`
 * for it to begin. `keepWaiting` returning false ends the wait early (e.g. the player acted).
 */
export async function waitForSpeechToFinish(
  keepWaiting: () => boolean = () => true,
  graceMs: number = SPEECH_START_GRACE_MS,
): Promise<void> {
  if (!audioService.autoSpeechEnabled.value) return
  const startDeadline = Date.now() + graceMs
  while (keepWaiting() && !isSpeechBusy() && Date.now() < startDeadline) {
    await sleep(POLL_INTERVAL_MS)
  }
  while (keepWaiting() && isSpeechBusy()) {
    await sleep(POLL_INTERVAL_MS)
  }
}
