<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { authState, clearAuth } from '@/store/auth'
import { configState, refreshConfig } from '@/store/config'
import { api } from '@/composables/useApi'
import GlobalHeader from '@/components/GlobalHeader.vue'

const router = useRouter()
const route = useRoute()

async function checkAuth() {
  if (!authState.token) {
    authState.isInitialized = true
    try {
      const bootstrap = await api.getBootstrapStatus()
      if (!bootstrap.has_admin) {
        router.push('/setup')
      } else {
        router.push('/login')
      }
    } catch (e) {
      // Fallback safely to login if bootstrap status cannot be determined.
      if (route.name !== 'setup') router.push('/login')
    }
    return
  }

  try {
    const user = await api.getMe()
    authState.user = user
    authState.isAuthenticated = true
  } catch (err: any) {
    console.error('Initial auth check failed:', err)
    clearAuth()
    router.push('/login')
  } finally {
    authState.isInitialized = true
  }
}

onMounted(() => {
  checkAuth()
  refreshConfig()
  
  // Listen for 401 events from useApi
  window.addEventListener('auth-unauthorized', () => {
    clearAuth()
    router.push('/login')
  })
})
</script>

<template>
  <div class="h-screen flex flex-col bg-[#050b14] overflow-hidden">
    <GlobalHeader />
    <main class="flex-1 min-h-0 relative overflow-hidden">
      <RouterView />
    </main>
  </div>
</template>

<style>
/* Global Tailwind-like and RPG styles could go here if not in main.css */
@import '@/assets/main.css';

/* Custom scrollbars for a premium feel */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.02);
}
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
