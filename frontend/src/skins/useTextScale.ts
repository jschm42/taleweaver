import { ref, watch } from 'vue'

/** Font size multipliers for the story feed, applied on top of the text density. */
export const TEXT_SCALES = [0.9, 1, 1.15, 1.3, 1.5] as const

export const DEFAULT_TEXT_SCALE = 1

const STORAGE_KEY = 'tw_text_scale'

function isTextScale(value: number): boolean {
  return (TEXT_SCALES as readonly number[]).includes(value)
}

function readScale(): number {
  try {
    const stored = Number(localStorage.getItem(STORAGE_KEY))
    return isTextScale(stored) ? stored : DEFAULT_TEXT_SCALE
  } catch {
    return DEFAULT_TEXT_SCALE
  }
}

// Shared across components: the settings dialog writes, the immersive view reads.
const textScale = ref<number>(readScale())

watch(textScale, (value) => {
  try {
    localStorage.setItem(STORAGE_KEY, String(value))
  } catch {
    /* storage unavailable (private mode) */
  }
})

export function useTextScale() {
  return { textScale }
}
