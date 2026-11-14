import { reactive } from 'vue'
import { api } from '@/composables/useApi'
import { authState } from '@/store/auth'

/**
 * First-login onboarding for regular users (admins get the setup wizard instead).
 * It shares the per-user setup-wizard state on the backend: `pending` opens it once.
 */
export const onboardingState = reactive({
  isLoaded: false,
  isOpen: false,
})

/** Loads the onboarding state once per login and opens it for a user who never handled it. */
export async function loadOnboarding(): Promise<void> {
  const user = authState.user
  if (!user || user.role === 'admin' || onboardingState.isLoaded) {
    return
  }
  try {
    const status = await api.getSetupWizard()
    onboardingState.isLoaded = true
    onboardingState.isOpen = status.state === 'pending'
  } catch (error) {
    console.error('[Onboarding] Failed to load state:', error)
  }
}

export async function finishOnboarding(state: 'completed' | 'skipped'): Promise<void> {
  onboardingState.isOpen = false
  try {
    await api.updateSetupWizard({ state })
  } catch (error) {
    console.error('[Onboarding] Failed to save state:', error)
  }
}

/** Called on logout so the next user starts fresh. */
export function resetOnboarding(): void {
  onboardingState.isLoaded = false
  onboardingState.isOpen = false
}
