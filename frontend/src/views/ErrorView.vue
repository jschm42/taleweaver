<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { configState } from '@/store/config'
import { ServerCrash, RefreshCw, Home } from 'lucide-vue-next'

const router = useRouter()

const errorTitle = computed(() => {
  if (configState.lastErrorMessage.includes('Server Error')) return 'System Overload'
  return 'Connection Lost'
})

const errorMessage = computed(() => {
  if (configState.lastErrorMessage) return configState.lastErrorMessage
  return 'The TaleWeaver engine is currently unreachable. Please check if the backend is running.'
})

function retry() {
  // Reload the entire app to re-trigger initialization
  window.location.href = '/'
}

function goHome() {
  router.push('/')
}
</script>

<template>
  <div class="min-h-full flex items-center justify-center p-6 bg-[#050b14]">
    <div class="max-w-md w-full">
      <!-- Error Card -->
      <div class="relative group">
        <!-- Glow Effect -->
        <div class="absolute -inset-1 bg-gradient-to-r from-red-600 to-purple-600 rounded-2xl blur opacity-25 group-hover:opacity-40 transition duration-1000 group-hover:duration-200"></div>
        
        <div class="relative bg-[#0d1525]/80 backdrop-blur-xl border border-white/10 p-8 rounded-2xl shadow-2xl">
          <div class="flex flex-col items-center text-center">
            <!-- Icon -->
            <div class="w-20 h-20 bg-red-500/10 rounded-full flex items-center justify-center mb-6 border border-red-500/20 shadow-[0_0_20px_rgba(239,68,68,0.2)]">
              <ServerCrash class="w-10 h-10 text-red-500" />
            </div>

            <h1 class="text-3xl font-bold text-white mb-2 tracking-tight">{{ errorTitle }}</h1>
            <p class="text-slate-400 mb-8 leading-relaxed">
              {{ errorMessage }}
            </p>

            <!-- Actions -->
            <div class="flex flex-col gap-3 w-full">
              <button 
                @click="retry"
                class="flex items-center justify-center gap-2 w-full py-3.5 bg-gradient-to-r from-red-600 to-purple-600 hover:from-red-500 hover:to-purple-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-red-900/20 active:scale-[0.98]"
              >
                <RefreshCw class="w-5 h-5" />
                Reconnect to Engine
              </button>

              <button 
                @click="goHome"
                class="flex items-center justify-center gap-2 w-full py-3.5 bg-white/5 hover:bg-white/10 text-slate-300 font-semibold rounded-xl border border-white/5 transition-all active:scale-[0.98]"
              >
                <Home class="w-5 h-5" />
                Return to Portal
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer Info -->
      <p class="text-center mt-8 text-slate-600 text-sm">
        Error ID: {{ new Date().getTime().toString(16).toUpperCase() }}
      </p>
    </div>
  </div>
</template>

<style scoped>
@keyframes pulse {
  0%, 100% { opacity: 0.25; }
  50% { opacity: 0.5; }
}
.blur {
  animation: pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
</style>
