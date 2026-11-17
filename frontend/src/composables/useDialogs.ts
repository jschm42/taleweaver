/**
 * App-wide question dialogs that replace `window.confirm` / `window.prompt`.
 *
 * Every call queues a dialog and returns a promise; `UiDialogHost` (mounted once in
 * App.vue) shows the first queued dialog and settles it. The state lives at module level,
 * so services and composables can ask too, not only components.
 */
import { reactive } from 'vue'

export interface ConfirmOptions {
  title: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
  /** Destructive action: red confirm button. */
  danger?: boolean
}

export interface PromptOptions {
  title: string
  message?: string
  label?: string
  initial?: string
  placeholder?: string
  confirmLabel?: string
  cancelLabel?: string
  multiline?: boolean
  /** Returns an error text for an invalid value, or null when the value is fine. */
  validate?: (value: string) => string | null
}

export type PendingDialog =
  | { id: number; kind: 'confirm'; options: ConfirmOptions; resolve: (value: boolean) => void }
  | { id: number; kind: 'prompt'; options: PromptOptions; resolve: (value: string | null) => void }

export const dialogQueue = reactive<{ items: PendingDialog[] }>({ items: [] })

let nextId = 1

/** Asks a yes/no question. Resolves `true` on confirm, `false` on cancel or Esc. */
export function confirmDialog(options: ConfirmOptions): Promise<boolean> {
  return new Promise((resolve) => {
    dialogQueue.items.push({ id: nextId++, kind: 'confirm', options, resolve })
  })
}

/** Asks for a single value. Resolves the entered text, or `null` on cancel or Esc. */
export function promptDialog(options: PromptOptions): Promise<string | null> {
  return new Promise((resolve) => {
    dialogQueue.items.push({ id: nextId++, kind: 'prompt', options, resolve })
  })
}

/** Settles a queued dialog and removes it. Unknown ids are ignored. */
export function settleDialog(id: number, value: boolean | string | null): void {
  const index = dialogQueue.items.findIndex((item) => item.id === id)
  if (index < 0) {
    return
  }
  const [item] = dialogQueue.items.splice(index, 1)
  if (item.kind === 'confirm') {
    item.resolve(value === true)
    return
  }
  item.resolve(typeof value === 'string' ? value : null)
}

export function useConfirm(): typeof confirmDialog {
  return confirmDialog
}

export function usePrompt(): typeof promptDialog {
  return promptDialog
}
