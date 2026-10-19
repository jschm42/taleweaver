<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '@/composables/useApi'
import { usePasswordPolicy } from '@/composables/usePasswordPolicy'

const props = defineProps<{ initialUsername?: string }>()
const emit = defineEmits<{
  (e: 'recovered', token: string, username: string): void
  (e: 'cancel'): void
}>()

const { hint, validate } = usePasswordPolicy()

const username = ref(props.initialUsername || '')
const recoveryCode = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const error = ref('')
const isSubmitting = ref(false)

const passwordError = computed(() => (newPassword.value ? validate(newPassword.value) : null))
const mismatch = computed(() => Boolean(confirmPassword.value) && confirmPassword.value !== newPassword.value)
const canSubmit = computed(() =>
  Boolean(username.value.trim() && recoveryCode.value.trim() && newPassword.value)
  && !passwordError.value
  && !mismatch.value
  && confirmPassword.value === newPassword.value,
)

async function handleSubmit() {
  if (!canSubmit.value || isSubmitting.value) return
  isSubmitting.value = true
  error.value = ''
  try {
    const res = await api.recoverPasswordWithCode({
      username: username.value.trim(),
      recovery_code: recoveryCode.value.trim(),
      new_password: newPassword.value,
    })
    emit('recovered', res.access_token, username.value.trim())
  } catch (err: any) {
    error.value = err?.message || 'Recovery failed. Check your username and code.'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <form class="space-y-5" @submit.prevent="handleSubmit">
    <div class="text-center space-y-1">
      <h2 class="text-lg font-black text-white tracking-tight">Recover your account</h2>
      <p class="text-xs text-slate-400">
        Enter one of the recovery codes you saved from your profile. Each code works once.
      </p>
    </div>

    <label class="block space-y-2">
      <span class="text-xxs font-black text-slate-500 uppercase tracking-widest ml-1">Username</span>
      <input
        v-model="username"
        type="text"
        autocomplete="username"
        required
        class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
      />
    </label>

    <label class="block space-y-2">
      <span class="text-xxs font-black text-slate-500 uppercase tracking-widest ml-1">Recovery code</span>
      <input
        v-model="recoveryCode"
        type="text"
        autocomplete="one-time-code"
        spellcheck="false"
        required
        placeholder="XXXXX-XXXXX"
        class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white font-mono tracking-[0.2em] uppercase focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
      />
    </label>

    <label class="block space-y-2">
      <span class="text-xxs font-black text-slate-500 uppercase tracking-widest ml-1">New password</span>
      <input
        v-model="newPassword"
        :type="showPassword ? 'text' : 'password'"
        autocomplete="new-password"
        required
        class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
      />
      <span class="block text-[11px] ml-1" :class="passwordError ? 'text-amber-400' : 'text-slate-500'">
        {{ passwordError || hint }}
      </span>
    </label>

    <label class="block space-y-2">
      <span class="text-xxs font-black text-slate-500 uppercase tracking-widest ml-1">Confirm new password</span>
      <input
        v-model="confirmPassword"
        :type="showPassword ? 'text' : 'password'"
        autocomplete="new-password"
        required
        class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
      />
      <span v-if="mismatch" class="block text-[11px] ml-1 text-amber-400">Passwords do not match.</span>
    </label>

    <label class="flex items-center gap-2 px-1 text-xxs font-bold uppercase tracking-wider text-slate-400 cursor-pointer select-none">
      <input v-model="showPassword" type="checkbox" class="accent-aether-primary h-4 w-4" />
      Show passwords
    </label>

    <div v-if="error" class="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-bold text-center">
      {{ error }}
    </div>

    <button
      type="submit"
      :disabled="!canSubmit || isSubmitting"
      class="btn-primary w-full !py-4 flex items-center justify-center gap-3 disabled:opacity-50"
    >
      <i v-if="isSubmitting" class="ra ra-cycle animate-spin"></i>
      <span v-else>Reset password &amp; sign in</span>
    </button>

    <p class="text-center text-xs text-slate-500">
      No recovery codes? Ask an administrator for a password reset link.
    </p>

    <button
      type="button"
      class="w-full text-xxs font-black uppercase tracking-widest text-slate-500 hover:text-aether-primary transition-colors"
      @click="emit('cancel')"
    >
      Back to sign in
    </button>
  </form>
</template>
