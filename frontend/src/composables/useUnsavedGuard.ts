/**
 * Asks before leaving a page with unsaved changes: route changes through `confirmDialog`,
 * tab close / reload through the browser's own `beforeunload` prompt (the only case where
 * the browser does not allow a custom dialog).
 */
import { onBeforeUnmount, onMounted, type Ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { confirmDialog } from '@/composables/useDialogs'

export function useUnsavedGuard(isDirty: Readonly<Ref<boolean>>): void {
  const handleBeforeUnload = (event: BeforeUnloadEvent): void => {
    if (!isDirty.value) {
      return
    }
    event.preventDefault()
  }

  onMounted(() => window.addEventListener('beforeunload', handleBeforeUnload))
  onBeforeUnmount(() => window.removeEventListener('beforeunload', handleBeforeUnload))

  onBeforeRouteLeave(async () => {
    if (!isDirty.value) {
      return true
    }
    return confirmDialog({
      title: 'Discard unsaved changes?',
      message: 'You have changes on this page that are not saved yet.',
      confirmLabel: 'Discard changes',
      cancelLabel: 'Keep editing',
      danger: true,
    })
  })
}
