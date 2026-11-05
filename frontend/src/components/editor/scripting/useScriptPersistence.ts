import { computed, onBeforeUnmount, ref, type Ref } from 'vue'

/** Largest script file accepted by "Load"; scripts are small, anything bigger is a mistake. */
export const MAX_SCRIPT_FILE_BYTES = 512 * 1024

const SAVE_SUCCESS_MS = 2000
const ALLOWED_EXTENSIONS = ['.py', '.txt']

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback
}

function validateScriptFile(file: File): string | null {
  const name = file.name.toLowerCase()
  if (!ALLOWED_EXTENSIONS.some(ext => name.endsWith(ext))) {
    return `Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`
  }
  if (file.size > MAX_SCRIPT_FILE_BYTES) {
    return `File is too large (max ${MAX_SCRIPT_FILE_BYTES / 1024} KB).`
  }
  return null
}

export function useScriptPersistence(code: Ref<string>) {
  const savedCode = ref(code.value)
  const isDirty = computed(() => code.value !== savedCode.value)
  const isSaving = ref(false)
  const isLoading = ref(false)
  const saveError = ref<string | null>(null)
  const loadError = ref<string | null>(null)
  const saveSuccess = ref(false)
  const showUnsavedModal = ref(false)
  const pendingLoadFn = ref<(() => void | Promise<void>) | null>(null)

  let successTimer: ReturnType<typeof setTimeout> | null = null

  function markSaved(value: string) {
    savedCode.value = value
  }

  function flashSuccess() {
    saveSuccess.value = true
    if (successTimer) clearTimeout(successTimer)
    successTimer = setTimeout(() => {
      saveSuccess.value = false
    }, SAVE_SUCCESS_MS)
  }

  async function requestSave(
    currentCode: string,
    onSaveCallback?: (code: string) => Promise<void> | void
  ): Promise<boolean> {
    if (isSaving.value) return false
    isSaving.value = true
    saveError.value = null
    try {
      await onSaveCallback?.(currentCode)
      markSaved(currentCode)
      flashSuccess()
      return true
    } catch (err) {
      saveError.value = errorMessage(err, 'Failed to save script.')
      return false
    } finally {
      isSaving.value = false
    }
  }

  async function runLoader(loader: () => void | Promise<void>) {
    loadError.value = null
    try {
      await loader()
    } catch (err) {
      loadError.value = errorMessage(err, 'Failed to load script.')
    }
  }

  function requestLoad(loader: () => void | Promise<void>) {
    if (!isDirty.value) {
      void runLoader(loader)
      return
    }
    pendingLoadFn.value = loader
    showUnsavedModal.value = true
  }

  function confirmDiscardAndLoad() {
    const loader = pendingLoadFn.value
    pendingLoadFn.value = null
    showUnsavedModal.value = false
    if (loader) void runLoader(loader)
  }

  function cancelLoad() {
    pendingLoadFn.value = null
    showUnsavedModal.value = false
  }

  function exportScriptToFile(value: string, filename = 'script.py') {
    const blob = new Blob([value], { type: 'text/x-python;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  }

  function loadScriptFromFile(file: File, setCode: (value: string) => void) {
    loadError.value = validateScriptFile(file)
    if (loadError.value) return
    isLoading.value = true
    file
      .text()
      .then(text => setCode(text.replace(/\r\n?/g, '\n')))
      .catch(err => {
        loadError.value = errorMessage(err, 'Could not read the selected file.')
      })
      .finally(() => {
        isLoading.value = false
      })
  }

  onBeforeUnmount(() => {
    if (successTimer) clearTimeout(successTimer)
  })

  return {
    savedCode,
    isDirty,
    isSaving,
    isLoading,
    saveError,
    loadError,
    saveSuccess,
    showUnsavedModal,
    pendingLoadFn,
    requestSave,
    requestLoad,
    confirmDiscardAndLoad,
    cancelLoad,
    exportScriptToFile,
    loadScriptFromFile,
    markSaved
  }
}

export type ScriptPersistence = ReturnType<typeof useScriptPersistence>
