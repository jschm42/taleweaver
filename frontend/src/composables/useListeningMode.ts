/**
 * Listening mode: the hero keeps quiet and the NPCs present keep talking with each other.
 *
 * While it is on, the client sends `/listen` (a normal turn: the clock ticks), waits until the
 * narration has been read aloud (`waitForSpeechToFinish`), then sends the next `/listen`. The
 * backend lets the same pair go on with its talk (engine/conversations/chatter.py). Without
 * auto-speech the next step waits a short reading pause instead.
 *
 * It switches itself off when the player acts, a dialog or fight starts, the game cannot take
 * input, nobody here can hold a conversation (`sheet.npc_chatter.listen_possible`) or after
 * `MAX_LISTEN_STEPS` steps (cost guard; switching it on again goes on). Every switch on or off
 * is reported with `/listen_mode <code>`, which saves a system message in the story.
 */
import { ref, type Ref } from 'vue'
import { audioService } from '@/services/audioService'
import { waitForSpeechToFinish } from '@/services/speechWait'

export const LISTEN_COMMAND = '/listen'
export const MAX_LISTEN_STEPS = 12
/** Reading time between two steps when nothing is read aloud. */
export const LISTEN_READ_PAUSE_MS = 7000

/** Switch reasons; the backend saves the matching system message (listen_mode_command.py). */
export type ListenModeCode = 'on' | 'off' | 'nobody' | 'interrupted' | 'limit'
export const LISTEN_MODE_COMMAND = '/listen_mode'

export interface ListeningModeOptions {
  sendMessage: (content: string) => Promise<void>
  /** True while the game can take the next step (connected, no dialog, fight or lock). */
  canListen: () => boolean
  /** False once the backend reported that fewer than two NPCs can talk here. */
  listenPossible: () => boolean
}

export interface ListeningMode {
  active: Ref<boolean>
  toggle: () => void
  /** Switches the mode off (no-op when it is off) after the running step and reports `code`. */
  stop: (code?: ListenModeCode) => Promise<void>
  /** Switches the mode on (no-op when it is on). */
  start: () => void
}

function pause(ms: number, keepWaiting: () => boolean): Promise<void> {
  return new Promise((resolve) => {
    const end = Date.now() + ms
    const tick = (): void => {
      if (!keepWaiting() || Date.now() >= end) {
        resolve()
        return
      }
      setTimeout(tick, 250)
    }
    tick()
  })
}

export function useListeningMode(options: ListeningModeOptions): ListeningMode {
  const active = ref(false)
  let run = 0
  // The step that is being sent; a switch report waits for it, since a new message aborts it.
  let inFlight: Promise<void> = Promise.resolve()

  function report(code: ListenModeCode): Promise<void> {
    return options.sendMessage(`${LISTEN_MODE_COMMAND} ${code}`)
  }

  async function stop(code: ListenModeCode = 'off'): Promise<void> {
    if (!active.value) return
    active.value = false
    run += 1
    await inFlight
    await report(code)
  }

  async function waitBeforeNextStep(runId: number): Promise<void> {
    const keepWaiting = (): boolean => active.value && run === runId
    if (audioService.autoSpeechEnabled.value) {
      await waitForSpeechToFinish(keepWaiting)
      return
    }
    await pause(LISTEN_READ_PAUSE_MS, keepWaiting)
  }

  /** Why the loop ends before the next step; null when it may go on. */
  function stopCode(steps: number): ListenModeCode | null {
    if (!options.listenPossible()) return 'nobody'
    if (!options.canListen()) return 'interrupted'
    if (steps >= MAX_LISTEN_STEPS) return 'limit'
    return null
  }

  async function loop(runId: number): Promise<void> {
    let steps = 0
    const current = (): boolean => active.value && run === runId
    while (current()) {
      if (!options.canListen()) {
        await stop('interrupted')
        return
      }
      inFlight = options.sendMessage(LISTEN_COMMAND)
      await inFlight
      steps += 1
      if (!current()) return
      await waitBeforeNextStep(runId)
      if (!current()) return
      const code = stopCode(steps)
      if (code) {
        await stop(code)
        return
      }
    }
  }

  function start(): void {
    if (active.value) return
    active.value = true
    run += 1
    const runId = run
    // The report goes first, so the story shows the switch before the first conversation.
    inFlight = report('on')
    void inFlight.then(() => loop(runId))
  }

  function toggle(): void {
    if (active.value) {
      void stop()
      return
    }
    start()
  }

  return { active, toggle, stop, start }
}
