import { ref, onMounted, onUnmounted } from 'vue'

export type WhisperStatus = 'not_loaded' | 'loading' | 'loaded' | 'error'

interface WhisperStatusResponse {
  model_name: string
  status: WhisperStatus
}

const POLL_INTERVAL_MS = 1500

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Tracks the load state of the backend faster-whisper model.
 *
 * Preloads the model on mount, so the first push-to-talk does not have to wait for the
 * download, and exposes the elapsed wait time so the UI can show progress instead of
 * looking frozen.
 */
export function useWhisperStatus() {
  const whisperStatus = ref<WhisperStatus>('not_loaded')
  const whisperModelName = ref('')
  const whisperWaitSeconds = ref(0)
  let pollPromise: Promise<void> | null = null
  let disposed = false

  function applyStatus(res: WhisperStatusResponse) {
    whisperStatus.value = res.status
    whisperModelName.value = res.model_name
  }

  async function refreshWhisperStatus(): Promise<boolean> {
    try {
      const { api } = await import('@/composables/useApi')
      applyStatus(await api.getSttStatus())
      return true
    } catch (err) {
      console.error('Failed to get STT status:', err)
      return false
    }
  }

  async function preloadWhisperModel(): Promise<boolean> {
    try {
      const { api } = await import('@/composables/useApi')
      applyStatus(await api.preloadSttModel())
      return true
    } catch (err) {
      console.error('Failed to preload STT model:', err)
      return false
    }
  }

  async function pollWhileLoading() {
    const startedAt = Date.now()
    whisperWaitSeconds.value = 0
    while (whisperStatus.value === 'loading' && !disposed) {
      await sleep(POLL_INTERVAL_MS)
      whisperWaitSeconds.value = Math.round((Date.now() - startedAt) / 1000)
      if (!(await refreshWhisperStatus())) return
    }
  }

  // Shares one polling loop between the mount preload and a waiting recording.
  function waitForLoadToSettle(): Promise<void> {
    pollPromise ??= pollWhileLoading().finally(() => {
      pollPromise = null
    })
    return pollPromise
  }

  // A function, not an inline comparison: TS would otherwise keep the narrowing from
  // before the await, although polling changes the status in between.
  function isLoaded() {
    return whisperStatus.value === 'loaded'
  }

  /** Starts loading the model if needed and resolves once it is usable (true) or failed (false). */
  async function ensureWhisperModelReady(): Promise<boolean> {
    if (whisperStatus.value === 'loaded') return true
    if (whisperStatus.value !== 'loading' && !(await preloadWhisperModel())) return false
    await waitForLoadToSettle()
    return isLoaded()
  }

  onMounted(async () => {
    if (!(await refreshWhisperStatus())) return
    if (whisperStatus.value === 'not_loaded') await preloadWhisperModel()
    if (whisperStatus.value === 'loading') void waitForLoadToSettle()
  })

  onUnmounted(() => {
    disposed = true
  })

  return {
    whisperStatus,
    whisperModelName,
    whisperWaitSeconds,
    ensureWhisperModelReady,
  }
}
