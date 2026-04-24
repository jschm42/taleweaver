<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authState, clearAuth } from '@/store/auth'

const router = useRouter()
const isMenuOpen = ref(false)

function toggleMenu() {
  isMenuOpen.value = !isMenuOpen.value
}

function handleLogout() {
  clearAuth()
  router.push('/login')
}

function openProfile() {
  // We'll emit an event or use a global modal for this
  window.dispatchEvent(new CustomEvent('open-profile-modal'))
  isMenuOpen.value = false
}
</script>

<template>
  <header v-if="authState.isAuthenticated" class="h-12 bg-[#050b14] border-b border-white/5 px-6 my-1 flex items-center justify-between z-[100] relative">
    <!-- Left: Branding -->
    <div 
      class="flex items-center gap-3 select-none cursor-pointer group/logo"
      @click="router.push({ name: 'portal' })"
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
        <span class="text-[8px] font-bold text-slate-600 uppercase tracking-[0.2em]">v2.4.0-Aether</span>
      </div>
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
            v-if="authState.user?.profile_image_url" 
            :src="authState.user.profile_image_url" 
            class="w-full h-full rounded-full object-cover" 
          />
          <div v-else class="w-full h-full rounded-full bg-aether-primary/10 flex items-center justify-center">
            <i class="ra ra-hood text-xs text-aether-primary"></i>
          </div>
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
            <p class="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Account Role</p>
            <p class="text-xs font-bold text-aether-primary capitalize">{{ authState.user?.role }}</p>
          </div>

          <button @click="openProfile" class="w-full flex items-center gap-3 px-4 py-2.5 text-xs font-bold text-slate-400 hover:text-white hover:bg-white/5 transition-colors">
            <i class="ra ra-person"></i>
            Edit Profile
          </button>
          
          <button @click="handleLogout" class="w-full flex items-center gap-3 px-4 py-2.5 text-xs font-bold text-red-400 hover:text-red-300 hover:bg-red-500/5 transition-colors">
            <i class="ra ra-cancel"></i>
            Logout
          </button>
        </div>
      </Transition>

      <!-- Click Overlay to close dropdown -->
      <div v-if="isMenuOpen" @click="isMenuOpen = false" class="fixed inset-0 z-[-1]"></div>
    </div>
  </header>
</template>
