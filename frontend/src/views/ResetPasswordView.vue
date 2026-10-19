<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/composables/useApi'
import { usePasswordPolicy } from '@/composables/usePasswordPolicy'
import { authState, setToken } from '@/store/auth'
import { refreshConfig } from '@/store/config'

const route = useRoute()
const router = useRouter()
const { hint, validate } = usePasswordPolicy()

const token = computed(() => String(route.query.token || ''))
const newPassword = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const error = ref('')
const isSubmitting = ref(false)

const passwordError = computed(() => (newPassword.value ? validate(newPassword.value) : null))
const mismatch = computed(() => Boolean(confirmPassword.value) && confirmPassword.value !== newPassword.value)
const canSubmit = computed(() =>
  Boolean(token.value && newPassword.value)
  && !passwordError.value
  && confirmPassword.value === newPassword.value,
)

async function handleSubmit() {
  if (!canSubmit.value || isSubmitting.value) return
  isSubmitting.value = true
  error.value = ''
  try {
    const res = await api.resetPasswordWithToken({ token: token.value, new_password: newPassword.value })
    setToken(res.access_token)
    authState.user = await api.getMe()
    authState.isAuthenticated = true
    await refreshConfig().catch(() => {})
    router.replace('/')
  } catch (err: any) {
    error.value = err?.message || 'This reset link is invalid or has expired.'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-[#02060c] px-4">
    <div class="w-full max-w-md rounded-2xl border border-white/10 bg-[#0a111c] p-8 shadow-2xl">
      <div class="mb-6 flex items-center gap-3">
        <div class="rounded-xl border border-white/10 bg-white/5 p-2.5 text-aether-primary">
          <i class="ra ra-key text-lg"></i>
        </div>
        <div>
          <h1 class="text-xl font-black tracking-tight text-white">Choose a new password</h1>
          <p class="text-[11px] font-bold uppercase tracking-wider text-slate-500">One-time reset link</p>
        </div>
      </div>

      <div v-if="!token" class="space-y-4">
        <p class="text-sm text-slate-300">This link is missing its reset token. Ask your administrator for a new link.</p>
        <RouterLink to="/login" class="btn-primary inline-flex w-full justify-center !py-3">Back to sign in</RouterLink>
      </div>

      <form v-else class="space-y-5" @submit.prevent="handleSubmit">
        <label class="block space-y-2">
          <span class="ml-1 text-xxs font-black uppercase tracking-widest text-slate-500">New password</span>
          <input
            v-model="newPassword"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="new-password"
            required
            class="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-white transition-all focus:border-aether-primary/50 focus:outline-none focus:ring-1 focus:ring-aether-primary/20"
          />
          <span class="ml-1 block text-[11px]" :class="passwordError ? 'text-amber-400' : 'text-slate-500'">
            {{ passwordError || hint }}
          </span>
        </label>

        <label class="block space-y-2">
          <span class="ml-1 text-xxs font-black uppercase tracking-widest text-slate-500">Confirm new password</span>
          <input
            v-model="confirmPassword"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="new-password"
            required
            class="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-white transition-all focus:border-aether-primary/50 focus:outline-none focus:ring-1 focus:ring-aether-primary/20"
          />
          <span v-if="mismatch" class="ml-1 block text-[11px] text-amber-400">Passwords do not match.</span>
        </label>

        <label class="flex cursor-pointer select-none items-center gap-2 px-1 text-xxs font-bold uppercase tracking-wider text-slate-400">
          <input v-model="showPassword" type="checkbox" class="h-4 w-4 accent-aether-primary" />
          Show passwords
        </label>

        <div v-if="error" class="rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-center text-xs font-bold text-red-400">
          {{ error }}
        </div>

        <button
          type="submit"
          :disabled="!canSubmit || isSubmitting"
          class="btn-primary flex w-full items-center justify-center gap-3 !py-4 disabled:opacity-50"
        >
          <i v-if="isSubmitting" class="ra ra-cycle animate-spin"></i>
          <span v-else>Set password &amp; sign in</span>
        </button>
      </form>
    </div>
  </div>
</template>
