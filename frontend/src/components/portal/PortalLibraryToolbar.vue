<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { MoreVertical } from 'lucide-vue-next'

const props = defineProps<{
  activeSection: 'templates' | 'sessions'
  templateCount?: number
  isDeletingTemplates?: boolean
  sessionCount?: number
  isDeletingSessions?: boolean
}>()

const emit = defineEmits<{
  (e: 'changeSection', section: 'templates' | 'sessions'): void
  (e: 'import'): void
  (e: 'restore-defaults'): void
  (e: 'delete-all-adventures'): void
  (e: 'delete-all-sessions'): void
}>()

const isMenuOpen = ref(false)
const menuRef = ref<HTMLElement | null>(null)

function toggleMenu() {
  isMenuOpen.value = !isMenuOpen.value
}

function handleClickOutside(event: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(event.target as Node)) {
    isMenuOpen.value = false
  }
}

onMounted(() => {
  window.addEventListener('mousedown', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('mousedown', handleClickOutside)
})

function runAndClose(action: 'import' | 'restore' | 'delete-all') {
  isMenuOpen.value = false
  if (action === 'import') emit('import')
  else if (action === 'restore') emit('restore-defaults')
  else if (action === 'delete-all') {
    if (props.activeSection === 'templates') emit('delete-all-adventures')
    else emit('delete-all-sessions')
  }
}
</script>

<template>
  <div class="flex items-end justify-between gap-3 mb-6 sm:mb-8 lg:mb-12">
    <div class="min-w-0 flex-1">
      <h2 class="text-2xl sm:text-3xl lg:text-5xl font-black text-white font-display tracking-tight mb-1 sm:mb-2">
        {{ props.activeSection === 'templates' ? 'Library' : 'Game sessions' }}
      </h2>
      <p class="text-xs sm:text-sm lg:text-lg text-slate-500 font-narrative italic opacity-80 line-clamp-2">
        {{ props.activeSection === 'templates' ? 'Manage your world blueprints.' : 'Manage your active playthroughs.' }}
      </p>
    </div>

    <!-- Desktop / Tablet: inline action buttons -->
    <div class="hidden sm:flex items-center gap-3 shrink-0">
      <div v-if="props.activeSection === 'templates'" class="flex gap-2">
        <button
          class="px-3 lg:px-4 py-2 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-[10px] lg:text-xs font-bold uppercase tracking-widest hover:bg-red-500/20 transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="(props.templateCount || 0) === 0 || !!props.isDeletingTemplates"
          @click="emit('delete-all-adventures')"
        >
          <i class="ra ra-burning-embers"></i>
          <span class="hidden lg:inline">{{ props.isDeletingTemplates ? 'Deleting...' : 'Delete All Adventures' }}</span>
          <span class="lg:hidden">{{ props.isDeletingTemplates ? 'Deleting...' : 'Delete All' }}</span>
        </button>
        <button
          class="px-3 lg:px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-300 text-[10px] lg:text-xs font-bold uppercase tracking-widest hover:bg-white/10 transition-all flex items-center gap-2"
          @click="emit('import')"
        >
          <i class="ra ra-download"></i>
          <span class="hidden lg:inline">Import Adventure</span>
          <span class="lg:hidden">Import</span>
        </button>
        <button
          class="px-3 lg:px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-300 text-[10px] lg:text-xs font-bold uppercase tracking-widest hover:bg-white/10 transition-all flex items-center gap-2"
          title="Restore default adventures"
          @click="emit('restore-defaults')"
        >
          <i class="ra ra-recycle"></i>
          <span class="hidden lg:inline">Restore Defaults</span>
          <span class="lg:hidden">Restore</span>
        </button>
      </div>
      <div v-else-if="props.activeSection === 'sessions'" class="flex gap-2">
        <button
          class="px-3 lg:px-4 py-2 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-[10px] lg:text-xs font-bold uppercase tracking-widest hover:bg-red-500/20 transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="(props.sessionCount || 0) === 0 || !!props.isDeletingSessions"
          @click="emit('delete-all-sessions')"
        >
          <i class="ra ra-trash"></i>
          <span class="hidden lg:inline">{{ props.isDeletingSessions ? 'Deleting...' : 'Delete All Sessions' }}</span>
          <span class="lg:hidden">{{ props.isDeletingSessions ? 'Deleting...' : 'Delete All' }}</span>
        </button>
        <button
          class="px-3 lg:px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-300 text-[10px] lg:text-xs font-bold uppercase tracking-widest hover:bg-white/10 transition-all flex items-center gap-2"
          @click="emit('import')"
        >
          <i class="ra ra-download"></i>
          <span class="hidden lg:inline">Import Session</span>
          <span class="lg:hidden">Import</span>
        </button>
      </div>
    </div>

    <!-- Mobile: overflow menu -->
    <div class="relative sm:hidden shrink-0" ref="menuRef">
      <button
        @click="toggleMenu"
        class="w-10 h-10 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:text-white hover:bg-white/10 transition-all flex items-center justify-center"
        title="Actions"
        aria-label="Actions"
      >
        <MoreVertical class="w-5 h-5" />
      </button>

      <Transition
        enter-active-class="transition duration-100 ease-out"
        enter-from-class="transform scale-95 opacity-0"
        enter-to-class="transform scale-100 opacity-100"
        leave-active-class="transition duration-75 ease-in"
        leave-from-class="transform scale-100 opacity-100"
        leave-to-class="transform scale-95 opacity-0"
      >
        <div
          v-if="isMenuOpen"
          class="absolute right-0 top-12 z-30 w-52 bg-[#0d1117] border border-white/10 rounded-xl shadow-[0_12px_40px_rgba(0,0,0,0.6)] overflow-hidden backdrop-blur-xl"
        >
          <button
            class="w-full text-left px-4 py-3 text-[11px] font-black uppercase tracking-widest text-slate-300 hover:text-white hover:bg-white/5 flex items-center gap-3"
            @click="runAndClose('import')"
          >
            <i class="ra ra-download text-sm"></i>
            {{ props.activeSection === 'templates' ? 'Import Adventure' : 'Import Session' }}
          </button>
          <button
            v-if="props.activeSection === 'templates'"
            class="w-full text-left px-4 py-3 text-[11px] font-black uppercase tracking-widest text-slate-300 hover:text-white hover:bg-white/5 flex items-center gap-3"
            @click="runAndClose('restore')"
          >
            <i class="ra ra-recycle text-sm"></i>
            Restore Defaults
          </button>
          <div class="h-[1px] bg-white/5 mx-2 my-1"></div>
          <button
            class="w-full text-left px-4 py-3 text-[11px] font-black uppercase tracking-widest text-red-400/80 hover:text-red-400 hover:bg-red-500/10 flex items-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="(props.activeSection === 'templates' ? (props.templateCount || 0) === 0 : (props.sessionCount || 0) === 0) || (props.activeSection === 'templates' ? !!props.isDeletingTemplates : !!props.isDeletingSessions)"
            @click="runAndClose('delete-all')"
          >
            <i :class="props.activeSection === 'templates' ? 'ra ra-burning-embers text-sm' : 'ra ra-trash text-sm'"></i>
            <span v-if="props.activeSection === 'templates'">
              {{ props.isDeletingTemplates ? 'Deleting...' : 'Delete All Adventures' }}
            </span>
            <span v-else>
              {{ props.isDeletingSessions ? 'Deleting...' : 'Delete All Sessions' }}
            </span>
          </button>
        </div>
      </Transition>
    </div>
  </div>
</template>
