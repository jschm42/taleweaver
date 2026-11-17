/**
 * Draft model for the adventure settings (`editor.form`): every editor page edits the form
 * directly; this composable knows the last saved state, counts the changed settings, and saves
 * or discards them all at once through the shell's save bar (docs/specs/workbench_ui.md, 6.1).
 *
 * The saved state is taken again whenever `fetchAdventure` replaced `editor.adventure`, which
 * happens on load and after every successful `saveChanges`.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch, type ComputedRef } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { confirmDialog } from '@/composables/useDialogs'
import type { EditorContext } from '@/composables/editor/editorContext'

/** Character limits of the text settings (mirrors the backend template schema). */
export const FORM_LIMITS: Record<string, number> = {
  title: 50,
  version: 15,
  creator: 100,
  copyright: 100,
  license: 100,
  license_url: 500,
  teaser: 300,
  plot: 5000,
  rules: 5000,
  intro_text: 20000,
  completed_condition: 2000,
  gameover_condition: 2000,
  completed_guard_expression: 2000,
  gameover_guard_expression: 2000,
  tts_director_notes: 5000,
}

const URL_PATTERN = /^(https?:\/\/)[^\s/$.?#].[^\s]*$/i

type FormRecord = Record<string, unknown>

function snapshot(form: unknown): Record<string, string> {
  const result: Record<string, string> = {}
  for (const [key, value] of Object.entries((form ?? {}) as FormRecord)) {
    result[key] = JSON.stringify(value ?? null)
  }
  return result
}

/** Error text of one form field, or null. */
export function formFieldError(form: FormRecord, field: string): string | null {
  const value = String(form[field] ?? '')
  if (field === 'title' && !value.trim()) return 'A title is required.'
  const limit = FORM_LIMITS[field]
  if (limit !== undefined && value.length > limit) return `At most ${limit} characters.`
  if (field === 'license_url' && value.trim() && !URL_PATTERN.test(value.trim())) {
    return 'Use a full http:// or https:// address.'
  }
  return null
}

export interface EditorFormDraft {
  isDirty: ComputedRef<boolean>
  changedFields: ComputedRef<string[]>
  errorCount: ComputedRef<number>
  discard: () => void
  save: () => Promise<void>
}

export function useEditorFormDraft(editor: EditorContext): EditorFormDraft {
  const saved = ref<Record<string, string>>(snapshot(editor.form))

  watch(
    () => editor.adventure,
    () => {
      saved.value = snapshot(editor.form)
    },
    { flush: 'post' },
  )

  const changedFields = computed(() => {
    const current = snapshot(editor.form)
    return Object.keys(current).filter((key) => current[key] !== saved.value[key])
  })
  const isDirty = computed(() => changedFields.value.length > 0)
  const errorCount = computed(
    () => Object.keys(FORM_LIMITS).filter((field) => formFieldError(editor.form as FormRecord, field)).length,
  )

  function discard(): void {
    const form = editor.form as FormRecord
    for (const [key, json] of Object.entries(saved.value)) {
      form[key] = JSON.parse(json)
    }
  }

  async function save(): Promise<void> {
    if (errorCount.value > 0 || editor.isSaving) return
    await editor.saveChanges()
  }

  const handleBeforeUnload = (event: BeforeUnloadEvent): void => {
    if (isDirty.value) event.preventDefault()
  }
  onMounted(() => window.addEventListener('beforeunload', handleBeforeUnload))
  onBeforeUnmount(() => window.removeEventListener('beforeunload', handleBeforeUnload))

  // All editor routes share one view; only leaving the editor of this adventure asks.
  onBeforeRouteLeave((to, from) => {
    const staysInEditor =
      String(to.name ?? '').startsWith('adventure-editor') && to.params.adventureId === from.params.adventureId
    if (staysInEditor || !isDirty.value) return true
    return confirmDialog({
      title: 'Discard unsaved changes?',
      message: 'The adventure settings have changes that are not saved yet.',
      confirmLabel: 'Discard changes',
      cancelLabel: 'Keep editing',
      danger: true,
    })
  })

  return { isDirty, changedFields, errorCount, discard, save }
}
