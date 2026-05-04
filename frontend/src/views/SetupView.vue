<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/composables/useApi'
import { configState } from '@/store/config'

const router = useRouter()
const username = ref('admin')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const isSettingUp = ref(false)

async function handleSetup() {
  if (!username.value || !password.value) return
  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match.'
    return
  }
  
  isSettingUp.value = true
  error.value = ''
  
  try {
    await api.setupRootAdmin({
      username: username.value,
      password: password.value
    })
    router.push('/login')
  } catch (err: any) {
    error.value = 'Setup failed. Maybe an admin already exists?'
    console.error('Setup failed:', err)
  } finally {
    isSettingUp.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex flex-col items-center justify-center bg-[#050b14] relative p-6">
    <!-- App Branding -->
    <div class="flex flex-col items-center gap-6 mb-12 select-none animate-fade-in">
      <div class="w-24 h-24 bg-aether-primary/10 rounded-[2rem] flex items-center justify-center border border-aether-primary/20 shadow-[0_0_100px_rgba(78,222,163,0.15)]">
        <img src="@/assets/svg/app-logo.svg" class="w-16 h-16 drop-shadow-[0_0_15px_rgba(78,222,163,0.5)]" alt="Logo" />
      </div>
      <div class="text-center">
        <h1 class="text-6xl font-black text-white font-display tracking-tighter leading-none mb-2">TaleWeaver</h1>
        <span class="text-xs font-bold text-aether-primary/40 tracking-[0.5em] uppercase">Chronicle Intelligence v{{ configState.appVersion }}</span>
      </div>
    </div>

    <div class="w-full max-w-lg p-10 bg-white/5 border border-white/10 rounded-[2rem] backdrop-blur-2xl shadow-2xl relative overflow-hidden">
      <!-- Glow Effect -->
      <div class="absolute -top-24 -left-24 w-48 h-48 bg-aether-primary/20 rounded-full blur-[80px]"></div>

      <div class="relative z-10">
        <div class="flex items-center gap-4 mb-8">
          <div class="p-3 rounded-2xl bg-aether-primary/10 border border-aether-primary/20">
            <i class="ra ra-gear text-2xl text-aether-primary"></i>
          </div>
          <div>
            <h1 class="text-2xl font-black text-white font-display">Root Admin Setup</h1>
            <p class="text-slate-500 text-xs font-bold uppercase tracking-widest">Initialize your TaleWeaver Instance</p>
          </div>
        </div>

        <p class="text-slate-400 text-sm mb-8 leading-relaxed">
          Welcome to your new TaleWeaver instance. Before we can weave chronicles, you must establish a **Root Administrator**. This account will have full control over the system.
        </p>

        <form @submit.prevent="handleSetup" class="space-y-6">
          <div class="space-y-2">
            <label class="text-xxs font-black text-slate-500 uppercase tracking-widest">Admin Username</label>
            <input 
              v-model="username"
              type="text" 
              required
              class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white focus:outline-none focus:border-aether-primary/50 transition-all"
            />
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-2">
              <label class="text-xxs font-black text-slate-500 uppercase tracking-widest">Master Password</label>
              <input 
                v-model="password"
                type="password" 
                required
                class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white focus:outline-none focus:border-aether-primary/50 transition-all"
              />
            </div>
            <div class="space-y-2">
              <label class="text-xxs font-black text-slate-500 uppercase tracking-widest">Confirm Password</label>
              <input 
                v-model="confirmPassword"
                type="password" 
                required
                class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white focus:outline-none focus:border-aether-primary/50 transition-all"
              />
            </div>
          </div>

          <div v-if="error" class="text-red-400 text-xs font-bold bg-red-500/10 border border-red-500/20 p-4 rounded-xl flex flex-col gap-2">
            <span>{{ error }}</span>
            <router-link to="/login" class="text-aether-primary hover:underline uppercase tracking-widest text-xxs">Go to Login &rarr;</router-link>
          </div>

          <button 
            type="submit" 
            :disabled="isSettingUp"
            class="btn-primary w-full !py-4 shadow-ambient-emerald/20 flex items-center justify-center gap-2"
          >
             <span>{{ isSettingUp ? 'Initializing...' : 'Create admin user' }}</span>
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

