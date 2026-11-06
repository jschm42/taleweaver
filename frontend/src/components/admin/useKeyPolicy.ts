import { onMounted, ref, type Ref } from 'vue'
import { api, type KeyPolicy, type KeyPolicyMap } from '@/composables/useApi'

export const KEY_POLICY_OPTIONS: Array<{ value: KeyPolicy, label: string, hint: string }> = [
  { value: 'server', label: 'Server pays', hint: 'The server key is used for everyone.' },
  { value: 'user_optional', label: 'Own key optional', hint: "A player's own key is used when stored, else the server key." },
  { value: 'user_required', label: 'Own key required', hint: 'Players must bring their own key; the server key is not used.' },
  { value: 'disabled', label: 'Disabled', hint: 'Nobody can use this provider.' },
]

export interface KeyPolicyState {
  policy: Ref<KeyPolicyMap>
  isSaving: Ref<boolean>
  error: Ref<string>
  policyFor: (provider: string) => KeyPolicy
  setPolicy: (provider: string, value: KeyPolicy) => Promise<void>
}

/** Server-wide key policy (who pays per provider); every change is saved right away. */
export function useKeyPolicy(): KeyPolicyState {
  const policy = ref<KeyPolicyMap>({})
  const isSaving = ref(false)
  const error = ref('')

  function policyFor(provider: string): KeyPolicy {
    return policy.value[provider] || 'server'
  }

  async function setPolicy(provider: string, value: KeyPolicy): Promise<void> {
    const previous = { ...policy.value }
    const next = { ...policy.value, [provider]: value }
    if (value === 'server') delete next[provider]
    policy.value = next
    isSaving.value = true
    error.value = ''
    try {
      policy.value = (await api.updateKeyPolicy(next)).policy
    } catch (err: unknown) {
      policy.value = previous
      error.value = err instanceof Error && err.message ? err.message : 'Failed to save the key policy.'
    } finally {
      isSaving.value = false
    }
  }

  onMounted(async () => {
    try {
      policy.value = (await api.getKeyPolicy()).policy
    } catch (err: unknown) {
      error.value = err instanceof Error && err.message ? err.message : 'Failed to load the key policy.'
    }
  })

  return { policy, isSaving, error, policyFor, setPolicy }
}
