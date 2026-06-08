<script setup lang="ts">
import { ref, computed, onUnmounted, onMounted } from 'vue'
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
const hasActiveLanguage = computed(() => !!language.value)

let tooltipTimer: number | null = null
let outsideClickHandler: ((e: MouseEvent) => void) | null = null

function clearTooltipTimer() {
  if (tooltipTimer !== null) {
    window.clearTimeout(tooltipTimer)
    tooltipTimer = null
  }
}

function showWithAutoHide() {
  showTooltip.value = true
  clearTooltipTimer()
  tooltipTimer = window.setTimeout(() => {
    showTooltip.value = false
    tooltipTimer = null
  }, 2000)
}

function cancelTooltip() {
  showTooltip.value = false
  clearTooltipTimer()
}

function toggleDropdown() {
  isOpen.value = !isOpen.value
  cancelTooltip()
  if (isOpen.value) {
    registerOutsideClick()
  } else {
    unregisterOutsideClick()
  }
}

function closeDropdown() {
  isOpen.value = false
  unregisterOutsideClick()
}

function registerOutsideClick() {
  unregisterOutsideClick()
  // Defer registration so the click that opened the dropdown doesn't immediately close it
  setTimeout(() => {
    outsideClickHandler = (e: MouseEvent) => {
      const target = e.target as Node | null
      if (!target) return
      const inContainer = triggerRef.value?.contains(target)
      const inDropdown = !!(target as HTMLElement).closest?.('[data-bable-fish-dropdown]')
      if (!inContainer && !inDropdown) {
        closeDropdown()
      }
    }
    document.addEventListener('mousedown', outsideClickHandler)
    document.addEventListener('touchstart', outsideClickHandler as EventListener, { passive: true })
  }, 0)
}

function unregisterOutsideClick() {
  if (outsideClickHandler) {
    document.removeEventListener('mousedown', outsideClickHandler)
    document.removeEventListener('touchstart', outsideClickHandler as EventListener)
    outsideClickHandler = null
  }
}

const selectLanguage = (code: string) => {
  language.value = code
  closeDropdown()
}

onMounted(() => {
  // nothing to do
})

onUnmounted(() => {
  clearTooltipTimer()
  unregisterOutsideClick()
})
</script>

<template>
  <div class="bable-fish-container relative z-[100] animate-fade-in">
    <!-- Fish Button -->
    <button
      ref="triggerRef"
      @click="toggleDropdown"
      @mouseenter="showWithAutoHide"
      @mouseleave="cancelTooltip"
      class="relative flex items-center justify-center w-9 h-9 rounded-xl bg-slate-950/40 border border-slate-800/50 hover:border-cyan-500/50 transition-all duration-300 cursor-pointer backdrop-blur-sm shadow-inner group"
      :class="hasActiveLanguage ? 'bable-fish-active' : 'hover:bg-cyan-500/10'"
      :title="hasActiveLanguage ? `Translation: ${languages.find(l => l.code === language)?.name || 'Default'}` : 'Bable Fish Translation'"
      :aria-label="hasActiveLanguage ? `Translation active: ${languages.find(l => l.code === language)?.name || 'Default'}` : 'Open Bable Fish translation'"
    >
      <i
        :class="[
          'ra ra-fish text-base transition-all duration-300',
          hasActiveLanguage
            ? 'text-cyan-300 group-hover:scale-110'
            : 'text-slate-500 group-hover:text-cyan-400 group-hover:scale-110'
        ]"
      ></i>
      <div
        v-if="hasActiveLanguage"
        class="absolute -top-1 -right-1 w-1.5 h-1.5 bg-cyan-400 rounded-full animate-pulse shadow-[0_0_8px_rgba(34,211,238,0.8)]"
      ></div>
    </button>

    <!-- Tooltip -->
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
          data-bable-fish-dropdown
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

.bable-fish-active {
  border-color: rgba(34, 211, 238, 0.4);
  background: rgba(34, 211, 238, 0.08);
  box-shadow: inset 0 0 0 1px rgba(34, 211, 238, 0.05), 0 0 14px -2px rgba(34, 211, 238, 0.35);
  animation: bable-fish-pulse 2.4s ease-in-out infinite;
}

.bable-fish-active:hover {
  border-color: rgba(34, 211, 238, 0.6);
  background: rgba(34, 211, 238, 0.12);
}

@keyframes bable-fish-pulse {
  0%, 100% {
    box-shadow: inset 0 0 0 1px rgba(34, 211, 238, 0.05), 0 0 10px -2px rgba(34, 211, 238, 0.3);
  }
  50% {
    box-shadow: inset 0 0 0 1px rgba(34, 211, 238, 0.1), 0 0 18px -2px rgba(34, 211, 238, 0.55);
  }
}
</style>
