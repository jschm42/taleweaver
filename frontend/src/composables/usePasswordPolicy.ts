import { computed, ref } from 'vue'
import { api, type PasswordPolicy } from '@/composables/useApi'

const DEFAULT_POLICY: PasswordPolicy = { min_length: 10, requires_complexity: true }
const policy = ref<PasswordPolicy>(DEFAULT_POLICY)
let loadPromise: Promise<void> | null = null

function loadPolicy(): Promise<void> {
  loadPromise ??= api.getBootstrapStatus()
    .then((status) => {
      if (status.password_policy) policy.value = status.password_policy
    })
    .catch(() => {
      loadPromise = null
    })
  return loadPromise
}

/** Mirrors the backend password policy so forms can validate before submitting. */
export function usePasswordPolicy() {
  void loadPolicy()

  const hint = computed(() => policy.value.requires_complexity
    ? `At least ${policy.value.min_length} characters with upper- and lowercase letters, a digit and a symbol.`
    : `At least ${policy.value.min_length} characters.`)

  function validate(password: string): string | null {
    if (password.length < policy.value.min_length) {
      return `Password must be at least ${policy.value.min_length} characters long.`
    }
    if (!policy.value.requires_complexity) return null
    const checks = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/]
    if (checks.every(re => re.test(password))) return null
    return 'Password needs an uppercase letter, a lowercase letter, a digit and a symbol.'
  }

  return { policy, hint, validate }
}
