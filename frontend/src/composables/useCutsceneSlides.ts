/**
 * useCutsceneSlides — the timing of a cut-scene's slide show.
 *
 * A slide shows its passages one after another over the same picture. Each passage stays until
 * it was read aloud (auto-speech on) or for a reading time based on its length (auto-speech
 * off), at least `MIN_SLIDE_MS`. Holding the mouse button or Space for `HOLD_TO_SKIP_MS` skips
 * the current passage (after a slide's last passage: to the next slide); Escape ends the whole
 * cut-scene. After the last slide `onDone` runs once.
 */
import { onBeforeUnmount, ref, type Ref } from 'vue'
import { audioService } from '@/services/audioService'
import type { Cutscene } from '@/types'

const MIN_SLIDE_MS = 2500
/** The overlay fades in first; speech starting at once would talk over the fade. */
const START_DELAY_MS = 450
const AFTER_SPEECH_MS = 700
const READ_BASE_MS = 2500
const READ_MS_PER_CHAR = 55
const MAX_READ_MS = 15000
export const HOLD_TO_SKIP_MS = 600

export interface CutsceneSlides {
  index: Ref<number>
  /** Position of the shown passage within the current slide. */
  passage: Ref<number>
  holdProgress: Ref<number>
  start: (cutscene: Cutscene) => void
  stop: () => void
  skipSlide: () => void
  skipAll: () => void
  beginHold: () => void
  endHold: () => void
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

export function readingTimeMs(text: string): number {
  return Math.min(MAX_READ_MS, Math.max(MIN_SLIDE_MS, READ_BASE_MS + text.length * READ_MS_PER_CHAR))
}

export function useCutsceneSlides(autoSpeech: () => boolean, onDone: () => void): CutsceneSlides {
  const index = ref(0)
  const passage = ref(0)
  const holdProgress = ref(0)
  let cutscene: Cutscene | null = null
  // Bumped on every slide change: a running slide timer sees it and stops.
  let generation = 0
  let holdStartedAt = 0
  let holdFrame = 0

  function passageCount(slideIndex: number): number {
    return Math.max(1, cutscene?.slides[slideIndex]?.passages.length ?? 0)
  }

  /** The step after (slide, passage): the next passage, else the next slide's first. */
  function nextStep(slideIndex: number, passageIndex: number): [number, number] {
    return passageIndex + 1 < passageCount(slideIndex) ? [slideIndex, passageIndex + 1] : [slideIndex + 1, 0]
  }

  async function showStep(slideIndex: number, passageIndex: number, gen: number): Promise<void> {
    const slide = cutscene?.slides[slideIndex]
    if (!slide) {
      finish()
      return
    }
    index.value = slideIndex
    passage.value = passageIndex
    const startedAt = Date.now()
    const text = (slide.passages[passageIndex] || '').trim()
    if (text && autoSpeech()) {
      await audioService.speak(text, { interruptCurrent: true })
      if (gen !== generation) return
      await sleep(Math.max(AFTER_SPEECH_MS, MIN_SLIDE_MS - (Date.now() - startedAt)))
    } else {
      await sleep(readingTimeMs(text))
    }
    if (gen !== generation) return
    void showStep(...nextStep(slideIndex, passageIndex), ++generation)
  }

  function finish(): void {
    if (!cutscene) return
    cutscene = null
    generation += 1
    endHold()
    audioService.stop()
    onDone()
  }

  function start(next: Cutscene): void {
    cutscene = next
    index.value = 0
    passage.value = 0
    const gen = ++generation
    void sleep(START_DELAY_MS).then(() => {
      if (gen === generation) void showStep(0, 0, gen)
    })
  }

  function stop(): void {
    cutscene = null
    generation += 1
    endHold()
  }

  function skipSlide(): void {
    if (!cutscene) return
    audioService.stop()
    void showStep(...nextStep(index.value, passage.value), ++generation)
  }

  function tickHold(): void {
    holdProgress.value = Math.min(1, (Date.now() - holdStartedAt) / HOLD_TO_SKIP_MS)
    if (holdProgress.value >= 1) {
      endHold()
      skipSlide()
      return
    }
    holdFrame = requestAnimationFrame(tickHold)
  }

  function beginHold(): void {
    if (!cutscene || holdFrame) return
    holdStartedAt = Date.now()
    holdFrame = requestAnimationFrame(tickHold)
  }

  function endHold(): void {
    if (holdFrame) cancelAnimationFrame(holdFrame)
    holdFrame = 0
    holdProgress.value = 0
  }

  onBeforeUnmount(stop)

  return { index, passage, holdProgress, start, stop, skipSlide, skipAll: finish, beginHold, endHold }
}
