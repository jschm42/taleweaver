<script setup lang="ts">
import { ref, watch } from 'vue'
import { X, ChevronsLeft, ChevronsRight } from 'lucide-vue-next'

type Section = 'templates' | 'sessions' | 'leaderboard' | 'profile'

const props = defineProps<{
  isAdmin: boolean
  activeSection: Section
  isMobileOpen?: boolean
}>()

const emit = defineEmits<{
  (e: 'section', section: Section): void
  (e: 'admin'): void
  (e: 'about'): void
  (e: 'close-mobile'): void
}>()

const COLLAPSE_KEY = 'tw_portal_sidebar_collapsed'

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === 'true'
  } catch {
    return false
  }
}

/** Desktop-only icon rail; the mobile drawer always shows labels. */
const isCollapsed = ref(readCollapsed())

watch(isCollapsed, (value) => {
  try {
    localStorage.setItem(COLLAPSE_KEY, String(value))
  } catch {
    // Storage unavailable (private mode); the toggle still works for this visit.
  }
})

const navItems: ReadonlyArray<{ section: Section; label: string; icon: string }> = [
  { section: 'templates', label: 'Library', icon: 'ra-book' },
  { section: 'sessions', label: 'Sessions', icon: 'ra-hourglass' },
  { section: 'leaderboard', label: 'Leaderboard', icon: 'ra-trophy' },
  { section: 'profile', label: 'Profile', icon: 'ra-hood' },
]

function selectSection(section: Section): void {
  emit('section', section)
  emit('close-mobile')
}

function itemClass(active: boolean): string {
  const base = 'w-full flex items-center gap-4 px-4 py-3 rounded-xl transition-all'
  return active ? `${base} rune-active` : `${base} text-slate-400 hover:bg-white/5 hover:text-white`
}
</script>

<template>
  <!-- Backdrop for mobile drawer -->
  <div
    v-if="props.isMobileOpen"
    class="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-40 lg:hidden animate-fade-in"
    @click="emit('close-mobile')"
  ></div>

  <aside
    :class="[
      'bg-[#060d18]/90 backdrop-blur-2xl border-r border-amber-200/5 flex flex-col z-50 overflow-y-auto overflow-x-hidden transition-all duration-300 ease-in-out shrink-0',
      props.isMobileOpen
        ? 'fixed inset-y-0 left-0 w-72 max-w-[85vw] translate-x-0'
        : 'fixed inset-y-0 left-0 w-72 max-w-[85vw] -translate-x-full lg:translate-x-0 lg:relative lg:inset-y-0 lg:left-0',
      isCollapsed ? 'lg:w-20' : 'lg:w-64'
    ]"
  >
    <div class="p-6 pb-4 flex-1" :class="isCollapsed ? 'lg:px-3' : 'lg:px-5'">
      <div class="flex items-center justify-between mb-6 lg:hidden">
        <span class="text-[10px] font-bold uppercase tracking-[0.3em] text-aether-primary">Menu</span>
        <button
          @click="emit('close-mobile')"
          class="w-8 h-8 rounded-lg bg-white/5 border border-white/10 text-slate-300 hover:text-white hover:bg-white/10 transition-all flex items-center justify-center"
          title="Close menu"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <nav class="space-y-1.5">
        <button
          v-for="item in navItems"
          :key="item.section"
          :class="[itemClass(props.activeSection === item.section), isCollapsed ? 'lg:justify-center lg:px-0' : '']"
          :title="isCollapsed ? item.label : undefined"
          :aria-current="props.activeSection === item.section ? 'page' : undefined"
          @click="selectSection(item.section)"
        >
          <i :class="['ra', item.icon]" class="text-lg w-5 text-center"></i>
          <span class="font-fantasy font-bold text-[15px] tracking-wider" :class="isCollapsed ? 'lg:hidden' : ''">{{ item.label }}</span>
        </button>
        <button
          v-if="props.isAdmin"
          :class="[itemClass(false), isCollapsed ? 'lg:justify-center lg:px-0' : '']"
          :title="isCollapsed ? 'Administration' : undefined"
          @click="emit('admin'); emit('close-mobile')"
        >
          <i class="ra ra-cog text-lg w-5 text-center"></i>
          <span class="font-fantasy font-bold text-[15px] tracking-wider" :class="isCollapsed ? 'lg:hidden' : ''">Administration</span>
        </button>
      </nav>
    </div>

    <div class="p-6 pt-4 border-t border-white/5 space-y-1" :class="isCollapsed ? 'lg:px-3' : 'lg:px-5'">
      <button
        @click="emit('about'); emit('close-mobile')"
        class="w-full flex items-center gap-4 px-4 py-2.5 rounded-xl text-slate-500 hover:bg-white/5 hover:text-white transition-all"
        :class="isCollapsed ? 'lg:justify-center lg:px-0' : ''"
        :title="isCollapsed ? 'About' : undefined"
      >
        <i class="ra ra-scroll-unfurled w-5 text-center"></i>
        <span class="text-xs font-bold uppercase tracking-widest" :class="isCollapsed ? 'lg:hidden' : ''">About Archive</span>
      </button>
      <button
        @click="isCollapsed = !isCollapsed"
        class="hidden lg:flex w-full items-center gap-4 px-4 py-2.5 rounded-xl text-slate-500 hover:bg-white/5 hover:text-white transition-all"
        :class="isCollapsed ? 'justify-center px-0' : ''"
        :title="isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
        :aria-label="isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
      >
        <ChevronsRight v-if="isCollapsed" class="w-4 h-4" />
        <template v-else>
          <ChevronsLeft class="w-4 h-4" />
          <span class="text-xs font-bold uppercase tracking-widest">Collapse</span>
        </template>
      </button>
    </div>
  </aside>
</template>
