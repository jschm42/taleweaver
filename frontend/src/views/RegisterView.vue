<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/composables/useApi'
import { configState, isAppVersionKnown } from '@/store/config'
import BackgroundSlideshow from '@/components/common/BackgroundSlideshow.vue'
import BackgroundMusic from '@/components/common/BackgroundMusic.vue'

const backgroundImages = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map(
  (n) => `${import.meta.env.BASE_URL}assets/background/background${n}.jpg`,
)
const backgroundMusic = `${import.meta.env.BASE_URL}assets/audio/${encodeURIComponent('Clockwork Tension.mp3')}`

const DEFAULT_MIN_PASSWORD_LENGTH = 8

const router = useRouter()
const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const minPasswordLength = ref(DEFAULT_MIN_PASSWORD_LENGTH)
const error = ref('')
const isSubmitting = ref(false)
const successMessage = ref('')

const passwordMismatch = computed(
  () => confirmPassword.value.length > 0 && password.value !== confirmPassword.value,
)
const passwordTooShort = computed(
  () => password.value.length > 0 && password.value.length < minPasswordLength.value,
)

onMounted(async () => {
  try {
    const bootstrap = await api.getBootstrapStatus()
    if (bootstrap.app_version) {
      configState.appVersion = bootstrap.app_version
    }
    if (bootstrap.password_policy?.min_length) {
      minPasswordLength.value = bootstrap.password_policy.min_length
    }
  } catch (err) {
    console.error('Failed to load password policy:', err)
  }
})

function registerErrorMessage(err: any): string {
  if (err?.status === 429) {
    return 'Too many registration attempts. Please try again later.'
  }
  if (err?.status === 400 && err.message) {
    return err.message
  }
  return 'Registration failed. Please try again.'
}

async function handleRegister(): Promise<void> {
  if (passwordMismatch.value || passwordTooShort.value) return

  isSubmitting.value = true
  error.value = ''

  try {
    const res = await api.register({
      username: username.value.trim(),
      email: email.value.trim(),
      password: password.value,
    })
    successMessage.value = res?.message
      || 'Your account must be approved by an administrator before you can sign in for the first time.'
  } catch (err: any) {
    error.value = registerErrorMessage(err)
    console.error('Registration failed:', err)
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-[#02060c] relative overflow-hidden">
    <BackgroundSlideshow :images="backgroundImages" />
    <BackgroundMusic :src="backgroundMusic" />

    <!-- Animated Background Orbs -->
    <div class="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-aether-primary/10 rounded-full blur-[120px] animate-pulse"></div>
    <div class="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-500/10 rounded-full blur-[120px] animate-pulse" style="animation-delay: 2s"></div>

    <div class="w-full max-w-md p-8 z-10">
      <div class="text-center mb-10">
        <div class="inline-block mb-6">
          <img src="@/assets/svg/app-logo.svg" class="w-32 h-32 drop-shadow-[0_0_20px_rgba(78,222,163,0.4)]" alt="Logo" />
        </div>
        <h1 class="text-5xl font-black text-white font-display tracking-tighter mb-2">TaleWeaver</h1>
        <p class="text-aether-primary/40 text-xxs font-bold uppercase tracking-[0.4em]">Chronicle Intelligence<span v-if="isAppVersionKnown()"> v{{ configState.appVersion }}</span></p>
      </div>

      <div v-if="successMessage" class="space-y-6 text-center">
        <div class="p-6 rounded-xl bg-black/50 border border-aether-primary/20 space-y-3">
          <i class="ra ra-scroll-unfurled text-3xl text-aether-primary"></i>
          <h2 class="text-xl font-black text-white tracking-tight">Account created</h2>
          <p class="text-sm text-slate-400 leading-relaxed">{{ successMessage }}</p>
        </div>
        <button
          type="button"
          class="btn-primary w-full !py-4 flex items-center justify-center gap-3 shadow-ambient-emerald/20"
          @click="router.push('/login')"
        >
          Back to sign in
        </button>
      </div>

      <form v-else @submit.prevent="handleRegister" class="space-y-5">
        <div class="space-y-2">
          <label class="text-xxs font-black text-slate-500 uppercase tracking-widest ml-1">Username</label>
          <div class="relative">
            <i class="ra ra-person absolute left-4 top-1/2 -translate-y-1/2 text-slate-500"></i>
            <input
              v-model="username"
              type="text"
              required
              minlength="3"
              maxlength="50"
              autocomplete="username"
              class="w-full bg-black/50 border border-white/10 rounded-xl py-3.5 pl-12 pr-4 text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
              placeholder="Your chronicles name..."
            />
          </div>
        </div>

        <div class="space-y-2">
          <label class="text-xxs font-black text-slate-500 uppercase tracking-widest ml-1">Email</label>
          <div class="relative">
            <i class="ra ra-quill-ink absolute left-4 top-1/2 -translate-y-1/2 text-slate-500"></i>
            <input
              v-model="email"
              type="email"
              required
              autocomplete="email"
              class="w-full bg-black/50 border border-white/10 rounded-xl py-3.5 pl-12 pr-4 text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
              placeholder="you@example.com"
            />
          </div>
        </div>

        <div class="space-y-2">
          <label class="text-xxs font-black text-slate-500 uppercase tracking-widest ml-1">Password</label>
          <div class="relative">
            <i class="ra ra-hood absolute left-4 top-1/2 -translate-y-1/2 text-slate-500"></i>
            <input
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              required
              autocomplete="new-password"
              class="w-full bg-black/50 border border-white/10 rounded-xl py-3.5 pl-12 pr-4 text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
              :placeholder="`At least ${minPasswordLength} characters...`"
            />
          </div>
          <p v-if="passwordTooShort" class="text-xxs font-bold text-amber-400 ml-1">
            Password must be at least {{ minPasswordLength }} characters long.
          </p>
        </div>

        <div class="space-y-2">
          <label class="text-xxs font-black text-slate-500 uppercase tracking-widest ml-1">Confirm password</label>
          <div class="relative">
            <i class="ra ra-hood absolute left-4 top-1/2 -translate-y-1/2 text-slate-500"></i>
            <input
              v-model="confirmPassword"
              :type="showPassword ? 'text' : 'password'"
              required
              autocomplete="new-password"
              class="w-full bg-black/50 border border-white/10 rounded-xl py-3.5 pl-12 pr-4 text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
              placeholder="Repeat your password..."
            />
          </div>
          <p v-if="passwordMismatch" class="text-xxs font-bold text-red-400 ml-1">
            Passwords do not match.
          </p>
        </div>

        <div class="flex items-center justify-end px-1 text-xxs font-bold uppercase tracking-wider text-slate-400 select-none">
          <label class="flex items-center gap-2 cursor-pointer hover:text-aether-primary transition-colors">
            <input
              v-model="showPassword"
              type="checkbox"
              class="rounded border-white/10 bg-white/5 text-aether-primary focus:ring-0 focus:ring-offset-0 accent-aether-primary h-4 w-4 cursor-pointer"
            />
            Show Password
          </label>
        </div>

        <div v-if="error" class="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-bold text-center animate-shake">
          {{ error }}
        </div>

        <button
          type="submit"
          :disabled="isSubmitting || passwordMismatch || passwordTooShort"
          class="btn-primary w-full !py-4 flex items-center justify-center gap-3 shadow-ambient-emerald/20 disabled:opacity-50"
        >
          <i v-if="isSubmitting" class="ra ra-cycle animate-spin"></i>
          <span v-else>Create Account</span>
        </button>

        <button
          type="button"
          class="w-full text-xxs font-black uppercase tracking-widest text-slate-500 hover:text-aether-primary transition-colors"
          @click="router.push('/login')"
        >
          Already have an account? Sign in
        </button>
      </form>

      <div class="mt-12 text-center">
        <p class="text-xs font-medium text-slate-600 tracking-wide">
          © 2026 Jean Schmitz • Released under MIT License
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-shake {
  animation: shake 0.5s cubic-bezier(.36,.07,.19,.97) both;
}

@keyframes shake {
  10%, 90% { transform: translate3d(-1px, 0, 0); }
  20%, 80% { transform: translate3d(2px, 0, 0); }
  30%, 50%, 70% { transform: translate3d(-4px, 0, 0); }
  40%, 60% { transform: translate3d(4px, 0, 0); }
}
</style>
