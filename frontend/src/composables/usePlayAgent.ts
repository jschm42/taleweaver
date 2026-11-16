/**
 * usePlayAgent — Controls for the autonomous Play-Agent.
 *
 * Auto mode keeps playing turns until the adventure is won or lost (or the agent is
 * paused/stopped). Between two turns it can wait for text-to-speech to finish and for a
 * configurable delay. Step mode only plays a turn when the player requests the next step.
 *
 * Any player can start the agent (Auto-Play card or `/playagent`). The control panel floats
 * over the stage and can be minimized to a small dock; that choice is remembered per browser.
 * Walkthrough guidance needs the current chapter unlocked with XP (always free in debug mode);
 * Monkey mode is a debug tool.
 *
 * The player can tell the agent what to do next (instruction field, `/instruct`, or plain chat
 * text while the agent plays). An instruction sent while a step is running waits on the client
 * and is saved before the next step starts, so it never races the running turn.
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

/** How much the agent talks with characters, from taciturn to full roleplay (slider order). */
export const PLAY_AGENT_DIALOGUE_LEVELS = [
  { id: 'taciturn', label: 'Taciturn', hint: 'Speaks only when needed, a few words at a time' },
  { id: 'normal', label: 'Normal', hint: 'Greets characters, asks what matters, then acts' },
  { id: 'talkative', label: 'Talkative', hint: 'Chats often, asks follow-up questions' },
  { id: 'roleplay', label: 'Full roleplay', hint: 'Long in-character conversations with everyone' },
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

const MINIMIZED_STORAGE_KEY = 'tw.playAgent.minimized'

function readMinimized(): boolean {
  try {
    return window.localStorage.getItem(MINIMIZED_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function storeMinimized(value: boolean): void {
  try {
    window.localStorage.setItem(MINIMIZED_STORAGE_KEY, value ? '1' : '0')
  } catch {
    // Private mode or blocked storage: the panel just opens expanded next time.
  }
}

// Shared between the auto loop (GameView) and the panel that displays its progress.
const autoLoopPhase = ref<AutoLoopPhase>('idle')
const nextStepAt = ref<number | null>(null)
const isMinimized = ref(readMinimized())
/** Instruction typed while a step was running; saved before the next step. */
const pendingInstruction = ref<string | null>(null)

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

export function usePlayAgent() {
  const socket = useGameSocket()
  const { sheet, status, agentPaused } = socket

  const isActive = computed(() => Boolean(sheet.value?.agent_active))
  const isStepMode = computed(() => Boolean(sheet.value?.agent_step_by_step))
  const stepDelay = computed(() => Number(sheet.value?.agent_step_delay) || 0)
  const waitForTts = computed(() => sheet.value?.agent_wait_for_tts ?? true)
  const personality = computed(() => sheet.value?.agent_personality || 'casual')
  const dialogueLevel = computed(() => sheet.value?.agent_dialogue_level || 'normal')
  const instruction = computed(() => sheet.value?.agent_instruction || '')
  const isBusy = computed(() => status.value === 'connecting' || status.value === 'loading')
  const canRunStep = computed(() => isActive.value && status.value === 'connected')
  /** The current chapter's walkthrough is unlocked (XP) or debug mode is on. */
  const walkthroughUnlocked = computed(() => Boolean(sheet.value?.agent_walkthrough_unlocked))
  /** Debug-only options (Monkey mode) are available. */
  const debugTools = computed(() => Boolean(sheet.value?.agent_debug_tools))
  const lastEntry = computed(() => socket.agentLog.value[socket.agentLog.value.length - 1] ?? null)

  function setMinimized(value: boolean): void {
    isMinimized.value = value
    storeMinimized(value)
  }

  /** Lets the agent take over; the panel opens expanded so the player sees what happens. */
  async function start(): Promise<void> {
    if (isActive.value) {
      setMinimized(false)
      return
    }
    if (await socket.updateAgentSettings({ active: true })) setMinimized(false)
  }

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

  async function saveInstruction(text: string): Promise<void> {
    pendingInstruction.value = null
    await socket.updateAgentSettings({ instruction: text })
  }

  /** Sets ("" clears) the agent's instruction; queued while a step is running. */
  async function sendInstruction(text: string): Promise<void> {
    const cleaned = text.trim()
    if (isBusy.value) {
      pendingInstruction.value = cleaned
      return
    }
    await saveInstruction(cleaned)
  }

  /** Saves a queued instruction; called before every agent step. */
  async function flushPendingInstruction(): Promise<void> {
    if (pendingInstruction.value === null || isBusy.value) return
    await saveInstruction(pendingInstruction.value)
  }

  async function setDialogueLevel(level: string): Promise<void> {
    await socket.updateAgentSettings({ dialogue_level: level })
  }

  /**
   * Switches the play style. "Custom" needs a description: without a saved one the full panel
   * opens so the player can write it.
   */
  async function changePlayStyle(style: string): Promise<void> {
    const customText = (sheet.value?.agent_custom_personality || '').trim()
    if (style === 'custom' && !customText) {
      setMinimized(false)
      return
    }
    await setPersonality(style, style === 'custom' ? customText : undefined)
  }

  async function setWaitForTts(enabled: boolean): Promise<void> {
    await socket.updateAgentSettings({ wait_for_tts: enabled })
  }

  async function nextStep(): Promise<void> {
    if (!canRunStep.value) return
    await flushPendingInstruction()
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
    personality,
    dialogueLevel,
    instruction,
    pendingInstruction,
    sendInstruction,
    flushPendingInstruction,
    isBusy,
    canRunStep,
    walkthroughUnlocked,
    debugTools,
    lastEntry,
    isMinimized,
    setMinimized,
    start,
    setStepMode,
    setPersonality,
    setWalkthroughAllowed,
    setMonkeyMode,
    setStepDelay,
    setWaitForTts,
    setDialogueLevel,
    changePlayStyle,
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
  const {
    isActive,
    isStepMode,
    agentPaused,
    status,
    stepDelay,
    waitForTts,
    flushPendingInstruction,
  } = usePlayAgent()
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
        await flushPendingInstruction()
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
  // A step finished (also in Step mode or while paused): save a queued instruction now.
  watch(status, (value) => {
    if (value === 'connected') void flushPendingInstruction()
  })
  onUnmounted(() => {
    disposed = true
  })
}

/**
 * Short status line for the control panel and its minimized dock
 * ("Waiting for next step", "Next step in 4 s", ...). Ticks once per second while mounted.
 */
export function usePlayAgentStatusLabel() {
  const { agentPaused, statusText, isStepMode, isBusy } = usePlayAgent()
  const now = ref(Date.now())
  const timer = window.setInterval(() => {
    now.value = Date.now()
  }, 1000)
  onUnmounted(() => window.clearInterval(timer))

  const secondsToNextStep = computed(() =>
    nextStepAt.value ? Math.max(0, Math.ceil((nextStepAt.value - now.value) / 1000)) : 0
  )

  return computed(() => {
    if (isBusy.value) return statusText.value || 'Thinking...'
    if (isStepMode.value) return 'Waiting for your next step'
    if (agentPaused.value) return 'Paused'
    if (autoLoopPhase.value === 'speech') return 'Listening to the narration...'
    if (autoLoopPhase.value === 'delay' && secondsToNextStep.value > 1) {
      return `Next step in ${secondsToNextStep.value} s`
    }
    return 'Playing for you'
  })
}
