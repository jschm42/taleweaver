/**
 * usePlayAgent — Controls for the autonomous Play-Agent.
 *
 * Auto mode keeps playing turns until the adventure is won or lost (or the agent is
 * paused/stopped). Step mode only plays a turn when the player requests the next step.
 */
import { computed, onUnmounted, watch } from 'vue'
import { useGameSocket } from '@/composables/useGameSocket'
import { useNotifications } from '@/composables/useNotifications'

const AUTO_STEP_DELAY_MS = 1500

export const PLAY_AGENT_PERSONALITIES = [
  { id: 'casual', label: 'Casual' },
  { id: 'bureaucrat', label: 'Bureaucrat' },
  { id: 'powerplayer', label: 'Powerplayer' },
  { id: 'custom', label: 'Custom' },
] as const

export function usePlayAgent() {
  const socket = useGameSocket()
  const { sheet, status, agentPaused } = socket

  const isActive = computed(() => Boolean(sheet.value?.agent_active))
  const isStepMode = computed(() => Boolean(sheet.value?.agent_step_by_step))
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
    isActive,
    isStepMode,
    isBusy,
    canRunStep,
    setStepMode,
    setPersonality,
    setWalkthroughAllowed,
    setMonkeyMode,
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
  const { isActive, isStepMode, agentPaused, status } = usePlayAgent()
  let running = false
  let disposed = false

  const shouldAutoRun = () =>
    !disposed && isActive.value && !isStepMode.value && !agentPaused.value && status.value === 'connected'

  async function drive(): Promise<void> {
    if (running) return
    running = true
    try {
      while (shouldAutoRun()) {
        // Short pause so the player can follow the gameplay progression.
        await new Promise(resolve => setTimeout(resolve, AUTO_STEP_DELAY_MS))
        if (!shouldAutoRun()) break
        const completed = await socket.runAgentTurn()
        if (completed || !isActive.value) continue
        // Avoid hammering the backend after a failed request; the player can resume manually.
        agentPaused.value = true
        addNotification('Play-Agent paused: the last turn did not finish. Press Resume to continue.', 'info')
      }
    } finally {
      running = false
    }
  }

  watch([isActive, isStepMode, agentPaused, status], () => void drive(), { immediate: true })
  onUnmounted(() => {
    disposed = true
  })
}
