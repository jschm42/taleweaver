/**
 * Draft editing for Workbench pages: edit a local copy, save once.
 *
 * `draft` is a deep copy of the source. While it is unchanged, a new source value replaces
 * it (e.g. after a reload); while it has changes, the user's edits win. `commit` runs the
 * save function with the draft and makes the saved state the new baseline.
 */
import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'

export interface DraftApi<T> {
  draft: Ref<T>
  isDirty: ComputedRef<boolean>
  /** Top-level keys whose value differs from the saved state. */
  changedKeys: ComputedRef<string[]>
  changedCount: ComputedRef<number>
  isSaving: Ref<boolean>
  reset: () => void
  commit: (save: (value: T) => Promise<unknown> | unknown) => Promise<boolean>
}

export function cloneValue<T>(value: T): T {
  if (value === undefined) {
    return value
  }
  return JSON.parse(JSON.stringify(value)) as T
}

export function sameValue(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

export function changedTopLevelKeys(draft: unknown, baseline: unknown): string[] {
  if (!isRecord(draft) || !isRecord(baseline)) {
    return sameValue(draft, baseline) ? [] : ['value']
  }
  const keys = new Set([...Object.keys(draft), ...Object.keys(baseline)])
  return [...keys].filter((key) => !sameValue(draft[key], baseline[key]))
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function useDraft<T>(source: () => T): DraftApi<T> {
  const baseline = ref(cloneValue(source())) as Ref<T>
  const draft = ref(cloneValue(source())) as Ref<T>
  const isSaving = ref(false)

  const changedKeys = computed(() => changedTopLevelKeys(draft.value, baseline.value))
  const isDirty = computed(() => changedKeys.value.length > 0)
  const changedCount = computed(() => changedKeys.value.length)

  watch(
    source,
    (value) => {
      if (isDirty.value) {
        return
      }
      baseline.value = cloneValue(value)
      draft.value = cloneValue(value)
    },
    { deep: true },
  )

  function reset(): void {
    draft.value = cloneValue(baseline.value)
  }

  async function commit(save: (value: T) => Promise<unknown> | unknown): Promise<boolean> {
    if (isSaving.value) {
      return false
    }
    isSaving.value = true
    try {
      const saved = cloneValue(draft.value)
      await save(saved)
      baseline.value = saved
      return true
    } finally {
      isSaving.value = false
    }
  }

  return { draft, isDirty, changedKeys, changedCount, isSaving, reset, commit }
}
