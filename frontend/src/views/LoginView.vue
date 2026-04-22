<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/composables/useApi'
import { authState, setToken } from '@/store/auth'

const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const isLoggingIn = ref(false)

async function handleLogin() {
  if (!username.value || !password.value) return
  
  isLoggingIn.value = true
  error.value = ''
  
  try {
    const res = await api.login(username.value, password.value)
    setToken(res.access_token)
    
    // Fetch user details
    const user = await api.getMe()
    authState.user = user
    authState.isAuthenticated = true
    authState.isInitialized = true
    
    router.push('/')
  } catch (err: any) {
    error.value = 'Invalid credentials. Please try again.'
    console.error('Login failed:', err)
  } finally {
    isLoggingIn.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-[#02060c] relative overflow-hidden">
    <!-- Animated Background Orbs -->
    <div class="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-aether-primary/10 rounded-full blur-[120px] animate-pulse"></div>
    <div class="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-500/10 rounded-full blur-[120px] animate-pulse" style="animation-delay: 2s"></div>

    <div class="w-full max-w-md p-8 z-10">
      <div class="text-center mb-12">
        <div class="inline-block p-6 rounded-[2rem] bg-white/5 border border-white/10 mb-8 shadow-[0_0_80px_rgba(78,222,163,0.1)]">
          <img src="@/assets/svg/app-logo.svg" class="w-16 h-16 drop-shadow-[0_0_10px_rgba(78,222,163,0.4)]" alt="Logo" />
        </div>
        <h1 class="text-5xl font-black text-white font-display tracking-tighter mb-2">TaleWeaver</h1>
        <p class="text-aether-primary/40 text-[10px] font-bold uppercase tracking-[0.4em]">Chronicle Intelligence v2.4.0</p>
      </div>

      <form @submit.prevent="handleLogin" class="space-y-6">
        <div class="space-y-2">
          <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Username</label>
          <div class="relative">
            <i class="ra ra-person absolute left-4 top-1/2 -translate-y-1/2 text-slate-500"></i>
            <input 
              v-model="username"
              type="text" 
              required
              class="w-full bg-white/5 border border-white/10 rounded-xl py-3.5 pl-12 pr-4 text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
              placeholder="Your chronicles name..."
            />
          </div>
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Password</label>
          <div class="relative">
            <i class="ra ra-hood absolute left-4 top-1/2 -translate-y-1/2 text-slate-500"></i>
            <input 
              v-model="password"
              type="password" 
              required
              class="w-full bg-white/5 border border-white/10 rounded-xl py-3.5 pl-12 pr-4 text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
              placeholder="••••••••"
            />
          </div>
        </div>

        <div v-if="error" class="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-bold text-center animate-shake">
          {{ error }}
        </div>

        <button 
          type="submit" 
          :disabled="isLoggingIn"
          class="btn-primary w-full !py-4 flex items-center justify-center gap-3 shadow-ambient-emerald/20 disabled:opacity-50"
        >
          <i v-if="isLoggingIn" class="ra ra-cycle animate-spin"></i>
          <span v-else>Begin Journey</span>
        </button>
      </form>

      <div class="mt-12 text-center">
        <span class="text-[10px] font-bold text-slate-600 uppercase tracking-widest">Powered by Advanced Agentic Intelligence</span>
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
