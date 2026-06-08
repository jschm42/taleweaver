<script setup lang="ts">
import { X } from 'lucide-vue-next'

const props = defineProps<{
  isAdmin: boolean
  activeSection: 'templates' | 'sessions' | 'profile'
  isMobileOpen?: boolean
}>()

const emit = defineEmits<{
  (e: 'section', section: 'templates' | 'sessions' | 'profile'): void
  (e: 'admin'): void
  (e: 'about'): void
  (e: 'close-mobile'): void
}>()

function selectSection(section: 'templates' | 'sessions' | 'profile') {
  emit('section', section)
  emit('close-mobile')
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
      'bg-aether-background/95 backdrop-blur-2xl border-r border-white/5 flex flex-col z-50 overflow-y-auto transition-transform duration-300 ease-in-out shrink-0',
      // Mobile/Tablet: drawer behavior; Desktop: always visible sidebar
      props.isMobileOpen
        ? 'fixed inset-y-0 left-0 w-72 max-w-[85vw] translate-x-0'
        : 'fixed inset-y-0 left-0 w-72 max-w-[85vw] -translate-x-full lg:translate-x-0 lg:relative lg:inset-y-0 lg:left-0 lg:w-72'
    ]"
  >
    <div class="p-6 lg:p-8 pb-4 flex-1">
      <div class="flex items-center justify-between mb-6 lg:hidden">
        <span class="text-[10px] font-black uppercase tracking-[0.3em] text-aether-primary">Menu</span>
        <button
          @click="emit('close-mobile')"
          class="w-8 h-8 rounded-lg bg-white/5 border border-white/10 text-slate-300 hover:text-white hover:bg-white/10 transition-all flex items-center justify-center"
          title="Close menu"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <nav class="space-y-1">
        <button
          @click="selectSection('sessions')"
          class="w-full flex items-center gap-4 px-4 py-3 rounded-xl transition-all"
          :class="props.activeSection === 'sessions' ? 'bg-aether-primary/10 text-aether-primary border-l-4 border-aether-primary' : 'text-slate-400 hover:bg-white/5 hover:text-white'"
        >
          <span class="text-base font-bold tracking-wide text-xl text-emerald-500/80 uppercase">Sessions</span>
        </button>
        <button
          @click="selectSection('templates')"
          class="w-full flex items-center gap-4 px-4 py-3 rounded-xl transition-all"
          :class="props.activeSection === 'templates' ? 'bg-aether-primary/10 text-aether-primary border-l-4 border-aether-primary' : 'text-slate-400 hover:bg-white/5 hover:text-white'"
        >
          <span class="text-base font-bold tracking-wide text-xl text-emerald-500/80 uppercase">Library</span>
        </button>
        <button
          @click="selectSection('profile')"
          class="w-full flex items-center gap-4 px-4 py-3 rounded-xl transition-all"
          :class="props.activeSection === 'profile' ? 'bg-aether-primary/10 text-aether-primary border-l-4 border-aether-primary' : 'text-slate-400 hover:bg-white/5 hover:text-white'"
        >
          <span class="text-base font-bold tracking-wide text-xl text-emerald-500/80 uppercase">Profile</span>
        </button>
        <button
          v-if="props.isAdmin"
          @click="emit('admin'); emit('close-mobile')"
          class="w-full flex items-center gap-4 px-4 py-3 rounded-xl text-slate-400 hover:bg-white/5 hover:text-white transition-all"
        >
          <span class="text-base font-bold tracking-wide text-xl text-emerald-500/80 uppercase">Administration</span>
        </button>
      </nav>
    </div>

    <!-- Sidebar Bottom: About -->
    <div class="p-6 lg:p-8 pt-4 border-t border-white/5">
      <button
        @click="emit('about'); emit('close-mobile')"
        class="w-full flex items-center gap-4 px-4 py-3 rounded-xl text-slate-500 hover:bg-white/5 hover:text-white transition-all group"
      >
        <i class="ra ra-scroll-unfurled text-xl group-hover:text-aether-primary"></i>
        <span class="text-xs font-black uppercase tracking-widest">About Archive</span>
      </button>
    </div>
  </aside>
</template>
