<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api, type BootstrapStatus } from '@/composables/useApi'
import { useBackendStatus } from '@/composables/useBackendStatus'
import { authState, setToken } from '@/store/auth'
import { configState, isAppVersionKnown, refreshConfig } from '@/store/config'
import BackgroundSlideshow from '@/components/common/BackgroundSlideshow.vue'
import RecoveryCodeForm from '@/components/auth/RecoveryCodeForm.vue'

const backgroundImages = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map(
  (n) => `${import.meta.env.BASE_URL}assets/background/background${n}.jpg`,
)

const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const isLoggingIn = ref(false)
const rememberMe = ref(false)
const showPassword = ref(false)
const isRecovering = ref(false)

const { status: backendStatus } = useBackendStatus(handleBackendOnline)

const backendStatusLabels = {
  checking: 'Checking engine...',
  online: 'Engine online',
  offline: 'Engine starting up...',
} as const

function handleBackendOnline(bootstrap: BootstrapStatus | null) {
  if (bootstrap?.app_version) {
    configState.appVersion = bootstrap.app_version
  }
  // The backend may come up as a fresh install while this page waits for it.
  if (bootstrap && !bootstrap.has_admin) {
    router.push('/setup')
  }
}

onMounted(() => {
  const savedUsername = localStorage.getItem('remembered_username')
  if (savedUsername) {
    username.value = savedUsername
    rememberMe.value = true
  }
})

async function handleLogin() {
  if (!username.value || !password.value) return
  
  isLoggingIn.value = true
  error.value = ''
  
  try {
    const res = await api.login(username.value, password.value)
    await completeSignIn(res.access_token)
  } catch (err: any) {
    error.value = err?.status === 429
      ? 'Too many failed attempts. Please wait a minute and try again.'
      : 'Invalid credentials. Please try again.'
    console.error('Login failed:', err)
  } finally {
    isLoggingIn.value = false
  }
}

async function completeSignIn(token: string) {
  setToken(token, rememberMe.value)

  if (rememberMe.value) {
    localStorage.setItem('remembered_username', username.value)
  } else {
    localStorage.removeItem('remembered_username')
  }

  authState.user = await api.getMe()
  authState.isAuthenticated = true
  authState.isInitialized = true

  // Fetch settings/config since we now have a token
  try {
    await refreshConfig()
  } catch (confErr) {
    console.error('Failed to refresh config after login:', confErr)
  }

  router.push('/')
}

async function handleRecovered(token: string, recoveredUsername: string) {
  username.value = recoveredUsername
  try {
    await completeSignIn(token)
  } catch (err) {
    console.error('Sign-in after recovery failed:', err)
    isRecovering.value = false
    error.value = 'Password was reset. Please sign in with your new password.'
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-[#02060c] relative overflow-hidden">
    <BackgroundSlideshow :images="backgroundImages" />

    <!-- Animated Background Orbs -->
    <div class="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-aether-primary/10 rounded-full blur-[120px] animate-pulse"></div>
    <div class="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-500/10 rounded-full blur-[120px] animate-pulse" style="animation-delay: 2s"></div>

    <div class="w-full max-w-md p-8 z-10">
      <div class="text-center mb-12">
        <div class="inline-block mb-8">
          <img src="@/assets/svg/app-logo.svg" class="w-40 h-40 drop-shadow-[0_0_20px_rgba(78,222,163,0.4)]" alt="Logo" />
        </div>
        <h1 class="text-5xl font-black text-white font-display tracking-tighter mb-2">TaleWeaver</h1>
        <p class="text-aether-primary/40 text-xxs font-bold uppercase tracking-[0.4em]">Chronicle Intelligence<span v-if="isAppVersionKnown()"> v{{ configState.appVersion }}</span></p>
        <div
          class="mt-6 inline-flex items-center gap-2 px-3 py-1.5 rounded-full border bg-black/40 text-xxs font-bold uppercase tracking-widest transition-colors"
          :class="{
            'border-aether-primary/30 text-aether-primary': backendStatus === 'online',
            'border-amber-400/30 text-amber-300': backendStatus === 'offline',
            'border-white/10 text-slate-400': backendStatus === 'checking',
          }"
          role="status"
          aria-live="polite"
          title="The login page checks the backend every few seconds."
        >
          <span
            class="w-2 h-2 rounded-full"
            :class="{
              'bg-aether-primary': backendStatus === 'online',
              'bg-amber-400 animate-pulse': backendStatus === 'offline',
              'bg-slate-400 animate-pulse': backendStatus === 'checking',
            }"
          ></span>
          {{ backendStatusLabels[backendStatus] }}
        </div>
      </div>

      <RecoveryCodeForm
        v-if="isRecovering"
        :initial-username="username"
        @recovered="handleRecovered"
        @cancel="isRecovering = false"
      />

      <form v-else @submit.prevent="handleLogin" class="space-y-6">
        <div class="space-y-2">
          <label class="text-xxs font-black text-slate-500 uppercase tracking-widest ml-1">Username</label>
          <div class="relative">
            <i class="ra ra-person absolute left-4 top-1/2 -translate-y-1/2 text-slate-500"></i>
            <input 
              v-model="username"
              type="text" 
              required
              class="w-full bg-black/50 border border-white/10 rounded-xl py-3.5 pl-12 pr-4 text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
              placeholder="Your chronicles name..."
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
              class="w-full bg-black/50 border border-white/10 rounded-xl py-3.5 pl-12 pr-4 text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
              placeholder="Your password..."
            />
          </div>
        </div>

        <!-- Remember Me & Show Password Checkboxes -->
        <div class="flex items-center justify-between px-1 text-xxs font-bold uppercase tracking-wider text-slate-400 select-none">
          <label class="flex items-center gap-2 cursor-pointer hover:text-aether-primary transition-colors">
            <input 
              v-model="rememberMe" 
              type="checkbox" 
              class="rounded border-white/10 bg-white/5 text-aether-primary focus:ring-0 focus:ring-offset-0 accent-aether-primary h-4 w-4 cursor-pointer"
            />
            Remember Me
          </label>
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
          :disabled="isLoggingIn || backendStatus !== 'online'"
          class="btn-primary w-full !py-4 flex items-center justify-center gap-3 shadow-ambient-emerald/20 disabled:opacity-50"
        >
          <i v-if="isLoggingIn" class="ra ra-cycle animate-spin"></i>
          <span v-else-if="backendStatus !== 'online'">Waiting for Engine...</span>
          <span v-else>Begin Journey</span>
        </button>

        <button
          type="button"
          class="w-full text-xxs font-black uppercase tracking-widest text-slate-500 hover:text-aether-primary transition-colors"
          @click="isRecovering = true; error = ''"
        >
          Forgot your password?
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

