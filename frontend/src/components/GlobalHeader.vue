<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { authState, clearAuth } from '@/store/auth'
import { configState } from '@/store/config'
import ChangeCredentialsModal from '@/components/portal/ChangeCredentialsModal.vue'
import { isMobileSidebarOpen, openMobileSidebar } from '@/store/layout'

const router = useRouter()
const route = useRoute()
const isMenuOpen = ref(false)
const isChangeCredentialsOpen = ref(false)

function normalizeProfileImageUrl(url: string): string {
  let normalized = (url || '').replace(/\\\\/g, '/')
  while (normalized.startsWith('/data/data/')) {
    normalized = normalized.replace('/data/data/', '/data/')
  }
  return normalized
}

const userAvatar = computed(() => {
  const user = authState.user
  if (user?.profile_image_url) {
    const normalized = normalizeProfileImageUrl(user.profile_image_url)
    return normalized.startsWith('http') 
      ? normalized 
      : normalized
  }
  return `https://api.dicebear.com/7.x/avataaars/svg?seed=${user?.username || 'default'}`
})

function toggleMenu() {
  isMenuOpen.value = !isMenuOpen.value
}

function handleLogout() {
  clearAuth()
  router.push('/login')
}
</script>

<template>
  <header v-if="authState.isAuthenticated" class="h-12 bg-[#050b14] border-b border-white/5 px-6 my-1 flex items-center justify-between z-[100] relative">
    <!-- Left: Branding -->
    <div class="flex items-center gap-3">
      <!-- Mobile Sidebar Toggle -->
      <button
        v-if="route.name === 'portal'"
        @click="openMobileSidebar"
        class="lg:hidden w-8 h-8 rounded-lg bg-slate-800/60 border border-slate-700/50 hover:bg-emerald-500/10 hover:border-emerald-500/40 transition-all flex items-center justify-center cursor-pointer shadow-lg group/sidebar-btn"
        title="Open menu"
        aria-label="Open menu"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-slate-200 group-hover/sidebar-btn:text-emerald-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5M3.75 17.25h16.5" />
        </svg>
      </button>

      <router-link 
        to="/"
        class="flex items-center gap-3 select-none cursor-pointer group/logo decoration-none"
        title="Return to Portal"
      >
        <div class="w-12 h-12 flex items-center justify-center">
          <img 
            src="@/assets/svg/app-logo.svg" 
            class="w-10 h-10 drop-shadow-[0_0_8px_rgba(78,222,163,0.4)] group-hover/logo:drop-shadow-[0_0_12px_rgba(78,222,163,0.7)] transition-all" 
            alt="Logo" 
          />
        </div>
        <div class="flex items-baseline gap-2">
          <span class="text-sm font-black text-white font-display tracking-tight">TaleWeaver</span>
          <span class="text-[10px] font-bold text-slate-600 uppercase tracking-[0.2em]">v{{ configState.appVersion }}</span>
        </div>
      </router-link>
    </div>

    <!-- Right: User Profile -->
    <div class="relative">
      <button 
        @click="toggleMenu"
        class="flex items-center gap-3 hover:bg-white/5 px-2 py-1 rounded-lg transition-colors group"
      >
        <span class="text-[12px] font-black text-slate-400 group-hover:text-white uppercase tracking-widest hidden sm:block">
          {{ authState.user?.username }}
        </span>
        <div class="w-12 h-12 rounded-full bg-white/5 border border-white/10 overflow-hidden shadow-inner p-0.5">
          <img 
            :src="userAvatar" 
            class="w-full h-full rounded-full object-cover" 
            alt="User Avatar"
          />
        </div>
      </button>

      <!-- Dropdown Menu -->
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="transform scale-95 opacity-0"
        enter-to-class="transform scale-100 opacity-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="transform scale-100 opacity-100"
        leave-to-class="transform scale-95 opacity-0"
      >
        <div 
          v-if="isMenuOpen"
          class="absolute right-0 mt-2 w-48 bg-[#0a111c] border border-white/10 rounded-xl shadow-2xl overflow-hidden py-1 z-50"
        >
          <div class="px-4 py-3 border-b border-white/5 bg-white/[0.02]">
            <p class="text-xs font-black text-slate-500 uppercase tracking-widest mb-1">Account Role</p>
            <p class="text-xs font-bold text-aether-primary capitalize">{{ authState.user?.role }}</p>
          </div>

          <router-link 
            :to="{ name: 'portal', query: { section: 'profile' } }"
            @click="isMenuOpen = false"
            class="w-full flex items-center gap-3 px-4 py-2.5 text-xs font-bold text-slate-400 hover:text-white hover:bg-white/5 transition-colors decoration-none"
          >
            <i class="ra ra-person"></i>
            Edit Profile
          </router-link>

          <button 
            @click="isChangeCredentialsOpen = true; isMenuOpen = false"
            class="w-full flex items-center gap-3 px-4 py-2.5 text-xs font-bold text-slate-400 hover:text-white hover:bg-white/5 transition-colors text-left"
          >
            <i class="ra ra-gear"></i>
            Change Credentials
          </button>
          
          <button @click="handleLogout" class="w-full flex items-center gap-3 px-4 py-2.5 text-xs font-bold text-red-400 hover:text-red-300 hover:bg-red-500/5 transition-colors text-left">
            <i class="ra ra-cancel"></i>
            Logout
          </button>
        </div>
      </Transition>

      <!-- Click Overlay to close dropdown -->
      <div v-if="isMenuOpen" @click="isMenuOpen = false" class="fixed inset-0 z-[-1]"></div>
    </div>

    <!-- Change Credentials Modal -->
    <ChangeCredentialsModal 
      :is-open="isChangeCredentialsOpen"
      @close="isChangeCredentialsOpen = false"
    />
  </header>
</template>


