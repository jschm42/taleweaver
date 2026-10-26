import { computed, ref, type Ref } from 'vue'
import type { FixProposal } from '@/services/adventureService'
import { worldBuilderService } from '@/services/worldBuilderService'

type NotifyFn = (message: string, type: 'error' | 'success' | 'info') => void

/**
 * State for the editor's World-Builder prompt: send a free-text instruction,
 * receive up to three proposals, and apply the one the author picks.
 */
export function useWorldBuilderInstructions(
  templateId: Ref<string>,
  notify: NotifyFn,
  onApplied: () => void,
) {
  const instruction = ref('')
  const submittedInstruction = ref('')
  const proposals = ref<FixProposal[]>([])
  const note = ref<string | null>(null)
  const errorMessage = ref<string | null>(null)
  const selectedIndex = ref(-1)
  const backupConfirmed = ref(false)
  const modalOpen = ref(false)
  const loading = ref(false)
  const applying = ref(false)

  const canSubmit = computed(
    () => instruction.value.trim().length >= 3 && !loading.value && !applying.value,
  )

  async function requestSuggestions(text: string) {
    loading.value = true
    errorMessage.value = null
    note.value = null
    proposals.value = []
    selectedIndex.value = -1
    try {
      const resp = await worldBuilderService.requestSuggestions(templateId.value, text)
      proposals.value = resp.proposals ?? []
      note.value = resp.note ?? null
      errorMessage.value = resp.error ?? null
      selectedIndex.value = proposals.value.length > 0 ? 0 : -1
    } catch (err: any) {
      errorMessage.value = err?.message || 'World-Builder request failed. See server logs for details.'
    } finally {
      loading.value = false
    }
  }

  async function submit() {
    if (!canSubmit.value) return
    submittedInstruction.value = instruction.value.trim()
    backupConfirmed.value = false
    modalOpen.value = true
    await requestSuggestions(submittedInstruction.value)
  }

  function retry() {
    if (loading.value || applying.value || !submittedInstruction.value) return
    void requestSuggestions(submittedInstruction.value)
  }

  function close() {
    if (applying.value) return
    modalOpen.value = false
  }

  async function applySelected() {
    const proposal = proposals.value[selectedIndex.value]
    if (!proposal) return
    if (!backupConfirmed.value) {
      notify('Please confirm you made a backup first.', 'error')
      return
    }
    applying.value = true
    errorMessage.value = null
    try {
      const resp = await worldBuilderService.applyProposal(templateId.value, proposal)
      if (resp.status === 'no_op') {
        errorMessage.value = resp.message || 'No changes were applied.'
        return
      }
      notify(
        resp.message || `World-Builder changes applied to ${resp.applied_targets.length} target(s).`,
        resp.status === 'applied' ? 'success' : 'info',
      )
      modalOpen.value = false
      instruction.value = ''
      onApplied()
    } catch (err: any) {
      errorMessage.value = err?.message || 'Failed to apply the proposal. See server logs for details.'
    } finally {
      applying.value = false
    }
  }

  return {
    instruction,
    submittedInstruction,
    proposals,
    note,
    errorMessage,
    selectedIndex,
    backupConfirmed,
    modalOpen,
    loading,
    applying,
    canSubmit,
    submit,
    retry,
    close,
    applySelected,
  }
}
