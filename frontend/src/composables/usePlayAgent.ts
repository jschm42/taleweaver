/**
 * usePlayAgent — Controls for the autonomous Play-Agent.
 *
 * Auto mode keeps playing turns until the adventure is won or lost (or the agent is
 * paused/stopped). Between two turns it can wait for text-to-speech to finish and for a
 * configurable delay. Step mode only plays a turn when the player requests the next step.
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { useGameSocket } from '@/composables/useGameSocket'
import { useNotifications } from '@/composables/useNotifications'
import { audioService } from '@/services/audioService'
import { waitForSpeechToFinish } from '@/services/speechWait'

/** Shortest pause between two auto-mode turns, so the player can follow along. */
const MIN_STEP_DELAY_MS = 1500
/** Narration is read once its turn has ended; this long the loop waits for speech to start. */
const POLL_INTERVAL_MS = 250

export const PLAY_AGENT_PERSONALITIES = [
  { id: 'casual', label: 'Casual' },
  { id: 'bureaucrat', label: 'Bureaucrat' },
  { id: 'powerplayer', label: 'Powerplayer' },
  { id: 'custom', label: 'Custom' },
] as const

export const PLAY_AGENT_STEP_DELAYS = [
  { seconds: 0, label: 'None' },
  { seconds: 3, label: '3 seconds' },
  { seconds: 5, label: '5 seconds' },
  { seconds: 10, label: '10 seconds' },
  { seconds: 20, label: '20 seconds' },
  { seconds: 30, label: '30 seconds' },
  { seconds: 60, label: '1 minute' },
] as const

export type AutoLoopPhase = 'idle' | 'speech' | 'delay'

// Shared between the auto loop (GameView) and the panel that displays its progress.
const autoLoopPhase = ref<AutoLoopPhase>('idle')
const nextStepAt = ref<number | null>(null)

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

export function usePlayAgent() {
  const socket = useGameSocket()
  const { sheet, status, agentPaused } = socket

  const isActive = computed(() => Boolean(sheet.value?.agent_active))
  const isStepMode = computed(() => Boolean(sheet.value?.agent_step_by_step))
  const stepDelay = computed(() => Number(sheet.value?.agent_step_delay) || 0)
  const waitForTts = computed(() => Boolean(sheet.value?.agent_wait_for_tts))
  const isBusy = computed(() => status.value === 'connecting' || status.value === 'loading')
  const canRunStep = computed(() => isActive.value && status.value === 'connected')

  async function setStepMode(enabled: boolean): Promise<void> {
    await socket.updateAgentSettings({ step_by_step: enabled })
  }

  async function setPersonality(personality: string, customText?: string): Promise<void> {
    await socket.updateAgentSettings({ personality, custom_personality: customText })
  }

  async function setWalkthroughAllowed(allowed: boolean): Promise<void> {
    await socket.updateAgentSettings({ allow_walkthrough: allowed })
  }

  async function setMonkeyMode(enabled: boolean): Promise<void> {
    await socket.updateAgentSettings({ monkey_mode: enabled })
  }

  async function setStepDelay(seconds: number): Promise<void> {
    await socket.updateAgentSettings({ step_delay: seconds })
  }

  async function setWaitForTts(enabled: boolean): Promise<void> {
    await socket.updateAgentSettings({ wait_for_tts: enabled })
  }

  async function nextStep(): Promise<void> {
    if (!canRunStep.value) return
    await socket.runAgentTurn()
  }

  function togglePause(): void {
    agentPaused.value = !agentPaused.value
  }

  async function stop(): Promise<void> {
    await socket.sendMessage('/playagent off')
  }

  return {
    sheet,
    status,
    agentPaused,
    agentLog: socket.agentLog,
    statusText: socket.statusText,
    autoLoopPhase,
    nextStepAt,
    isActive,
    isStepMode,
    stepDelay,
    waitForTts,
    isBusy,
    canRunStep,
    setStepMode,
    setPersonality,
    setWalkthroughAllowed,
    setMonkeyMode,
    setStepDelay,
    setWaitForTts,
    nextStep,
    togglePause,
    stop,
  }
}

/**
 * Drives the agent in auto mode. Mount once per game view.
 */
export function usePlayAgentAutoLoop(): void {
  const socket = useGameSocket()
  const { addNotification } = useNotifications()
  const { isActive, isStepMode, agentPaused, status, stepDelay, waitForTts } = usePlayAgent()
  let running = false
  let disposed = false

  const shouldAutoRun = (): boolean =>
    !disposed && isActive.value && !isStepMode.value && !agentPaused.value && status.value === 'connected'

  /** Waits until the narration of the last turn has been read aloud (when auto-speech is on). */
  async function waitForSpeech(): Promise<void> {
    if (!waitForTts.value || !audioService.autoSpeechEnabled.value) return
    autoLoopPhase.value = 'speech'
    await waitForSpeechToFinish(shouldAutoRun)
  }

  /** The configured pause; checked in short slices so Pause and Stop take effect at once. */
  async function waitForDelay(): Promise<void> {
    const delayMs = Math.max(MIN_STEP_DELAY_MS, stepDelay.value * 1000)
    autoLoopPhase.value = 'delay'
    nextStepAt.value = Date.now() + delayMs
    while (shouldAutoRun() && Date.now() < nextStepAt.value) {
      await sleep(Math.min(POLL_INTERVAL_MS, nextStepAt.value - Date.now()))
    }
  }

  async function drive(): Promise<void> {
    if (running) return
    running = true
    try {
      while (shouldAutoRun()) {
        await waitForSpeech()
        if (!shouldAutoRun()) break
        await waitForDelay()
        if (!shouldAutoRun()) break
        autoLoopPhase.value = 'idle'
        nextStepAt.value = null
        const completed = await socket.runAgentTurn()
        if (completed || !isActive.value) continue
        // Avoid hammering the backend after a failed request; the player can resume manually.
        agentPaused.value = true
        addNotification('Play-Agent paused: the last turn did not finish. Press Resume to continue.', 'info')
      }
    } finally {
      running = false
      autoLoopPhase.value = 'idle'
      nextStepAt.value = null
    }
  }

  watch([isActive, isStepMode, agentPaused, status], () => void drive(), { immediate: true })
  onUnmounted(() => {
    disposed = true
  })
}
