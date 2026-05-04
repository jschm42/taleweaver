<script setup lang="ts">
import { ref, computed } from 'vue'
import { useGameSocket } from '@/composables/useGameSocket'

const triggerRef = ref<HTMLElement | null>(null)
const dropdownStyle = computed(() => {
  if (!triggerRef.value) return {}
  const rect = triggerRef.value.getBoundingClientRect()
  return {
    top: `${rect.bottom + 8}px`,
    right: `${window.innerWidth - rect.right}px`
  }
})

const { language } = useGameSocket()

const languages = [
  { code: '', name: 'Default', icon: 'ra-spear-head' },
  { code: 'German', name: 'Deutsch', icon: 'ra-castle' },
  { code: 'English', name: 'English', icon: 'ra-tower' },
  { code: 'French', name: 'Français', icon: 'ra-fleur-de-lis' },
  { code: 'Spanish', name: 'Español', icon: 'ra-shield' },
  { code: 'Italian', name: 'Italiano', icon: 'ra-scroll-unfurled' },
  { code: 'Japanese', name: '日本語', icon: 'ra-shinto-shrine' },
  { code: 'Chinese', name: '中文', icon: 'ra-dragon' },
  { code: 'Russian', name: 'Русский', icon: 'ra-hammer' },
  { code: 'Portuguese', name: 'Português', icon: 'ra-anchor' },
]

const isOpen = ref(false)
const showTooltip = ref(false)

const selectLanguage = (code: string) => {
  language.value = code
  isOpen.value = false
}

const currentLanguageName = () => {
  return languages.find(l => l.code === language.value)?.name || 'Default'
}
</script>

<template>
  <div class="bable-fish-container relative z-[100] animate-fade-in">
    <div class="flex items-center">
      <!-- Bable Fish Badge -->
      <div 
        ref="triggerRef"
        @click="isOpen = !isOpen"
        @mouseenter="showTooltip = true"
        @mouseleave="showTooltip = false"
        class="flex items-center gap-2 px-3 py-1 rounded-xl bg-slate-950/40 border border-slate-800/50 hover:border-cyan-500/50 hover:bg-cyan-500/10 transition-all duration-300 cursor-pointer backdrop-blur-sm shadow-inner group"
      >
        <div class="relative flex items-center justify-center">
          <i class="ra ra-fish text-base text-cyan-400 group-hover:scale-110 transition-transform duration-300"></i>
          <div v-if="language" class="absolute -top-1 -right-1 w-1.5 h-1.5 bg-cyan-400 rounded-full animate-pulse shadow-[0_0_8px_rgba(34,211,238,0.8)]"></div>
        </div>
        <div class="flex flex-col leading-tight">
          <span class="text-xs font-black uppercase tracking-[0.15em] text-cyan-400/80">Bable Fish</span>
          <span class="text-xs font-bold text-slate-300 uppercase tracking-wider truncate max-w-[60px]">{{ currentLanguageName() }}</span>
        </div>
      </div>
    </div>

    <!-- Cool Tooltip -->
    <Teleport to="body">
      <Transition name="fade">
        <div 
          v-if="showTooltip && !isOpen"
          class="fixed z-[9999] w-64 p-3 bg-slate-900/95 border border-cyan-500/30 rounded-xl shadow-[0_10px_30px_rgba(0,0,0,0.5)] backdrop-blur-md pointer-events-none animate-fade-in"
          :style="dropdownStyle"
        >
          <div class="flex items-center gap-2 mb-2">
            <i class="ra ra-fish text-cyan-400"></i>
            <span class="text-xxs font-black uppercase tracking-widest text-white">Bable Fish Translation</span>
          </div>
          <p class="text-xxs leading-relaxed text-slate-400 italic">
            "Small, yellow, and probably the oddest thing in the Universe. It automatically translates all narration and dialogue into your chosen tongue."
          </p>
        </div>
      </Transition>
    </Teleport>

    <!-- Dropdown Menu -->
    <Teleport to="body">
      <Transition name="dropdown">
        <div 
          v-if="isOpen" 
          class="fixed z-[9999] w-48 bg-[#0f172a] border border-slate-700 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.9)] overflow-hidden animate-tooltip-in"
          :style="dropdownStyle"
        >
          <div class="p-2 grid grid-cols-1 gap-1">
            <button 
              v-for="lang in languages" 
              :key="lang.code"
              @click="selectLanguage(lang.code)"
              class="flex items-center gap-3 px-3 py-2 rounded-xl transition-all duration-200 group"
              :class="language === lang.code ? 'bg-cyan-500/20 text-white' : 'hover:bg-slate-800 text-slate-400 hover:text-white'"
            >
              <span class="text-xs font-bold tracking-wide">{{ lang.name }}</span>
              <i v-if="language === lang.code" class="ra ra-circle text-xxs ml-auto text-cyan-400"></i>
            </button>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Overlay to close dropdown -->
    <div v-if="isOpen" @click="isOpen = false" class="fixed inset-0 z-[9998] bg-black/40"></div>
  </div>
</template>

<style scoped>
.dropdown-enter-active, .dropdown-leave-active, .fade-enter-active, .fade-leave-active {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.dropdown-enter-from, .dropdown-leave-to, .fade-enter-from, .fade-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.95);
}

.bable-fish-container {
  user-select: none;
}
</style>


