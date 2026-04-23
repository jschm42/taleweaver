<script setup lang="ts">
import { ref } from 'vue'
import type { GameSession } from '@/types'

const props = defineProps<{
  session: GameSession
}>()

const emit = defineEmits<{
  (e: 'resume', gameId: string): void
  (e: 'pause', templateId: string): void
  (e: 'resumeHeartbeat', templateId: string): void
  (e: 'reset', templateId: string): void
  (e: 'delete', gameId: string, title: string): void
}>()

function templateIdOfSession(): string {
  return props.session.template_id || props.session.adventure_id
}

const isMenuOpen = ref(false)

function toggleMenu(): void {
  isMenuOpen.value = !isMenuOpen.value
}

function closeMenu(): void {
  isMenuOpen.value = false
}

function runAction(action: 'resume' | 'pause' | 'unpause' | 'reset' | 'delete'): void {
  if (action === 'resume') {
    emit('resume', props.session.game_id)
  } else if (action === 'pause') {
    emit('pause', templateIdOfSession())
  } else if (action === 'unpause') {
    emit('resumeHeartbeat', templateIdOfSession())
  } else if (action === 'reset') {
    emit('reset', templateIdOfSession())
  } else {
    emit('delete', props.session.game_id, props.session.adventure_title)
  }
  closeMenu()
}
</script>

<template>
  <article class="rounded-xl border border-white/10 bg-[#0d1524] p-4 flex flex-col gap-4 relative">
    <div class="flex items-start justify-between gap-3">
      <div class="flex items-center gap-3 min-w-0">
        <div class="w-12 h-12 rounded-full overflow-hidden border border-white/10 bg-black/30 shrink-0">
          <img
            v-if="props.session.profile_image"
            :src="props.session.profile_image"
            class="w-full h-full object-cover"
            alt="Profile"
          />
          <div v-else class="w-full h-full flex items-center justify-center text-slate-500 text-[10px] font-bold uppercase">
            N/A
          </div>
        </div>
        <div class="min-w-0">
        <h3 class="text-lg font-black text-white leading-tight">{{ props.session.adventure_title }}</h3>
        <p class="text-[11px] uppercase tracking-widest text-slate-400 mt-1">
          Scene: {{ props.session.current_scene_name || 'Unknown' }}
        </p>
        </div>
      </div>
      <div class="relative">
        <button
          @click.stop="toggleMenu"
          class="w-8 h-8 rounded-full border border-white/10 bg-black/30 text-slate-300 hover:text-white hover:bg-black/50 transition-colors text-lg font-bold leading-none"
          title="Session actions"
        >
          <span class="mb-0.5">...</span>
        </button>

        <div v-if="isMenuOpen" class="fixed inset-0 z-20" @click="closeMenu"></div>
        <div
          v-if="isMenuOpen"
          class="absolute right-0 top-9 z-30 w-44 bg-slate-900 border border-white/10 rounded-xl shadow-[0_12px_40px_rgba(0,0,0,0.45)] overflow-hidden"
        >
          <button
            class="w-full text-left px-4 py-2.5 text-xs font-bold uppercase tracking-widest text-emerald-300 hover:bg-emerald-500/20"
            @click="runAction('resume')"
          >
            Resume
          </button>
          <button
            v-if="!props.session.is_paused"
            class="w-full text-left px-4 py-2.5 text-xs font-bold uppercase tracking-widest text-amber-300 hover:bg-amber-500/20"
            @click="runAction('pause')"
          >
            Pause
          </button>
          <button
            v-else
            class="w-full text-left px-4 py-2.5 text-xs font-bold uppercase tracking-widest text-sky-300 hover:bg-sky-500/20"
            @click="runAction('unpause')"
          >
            Unpause
          </button>
          <button
            class="w-full text-left px-4 py-2.5 text-xs font-bold uppercase tracking-widest text-slate-200 hover:bg-white/10"
            @click="runAction('reset')"
          >
            Reset
          </button>
          <button
            class="w-full text-left px-4 py-2.5 text-xs font-bold uppercase tracking-widest text-red-300 hover:bg-red-500/20"
            @click="runAction('delete')"
          >
            Delete Session
          </button>
        </div>
      </div>
    </div>

    <div>
      <span
        class="px-2 py-1 rounded-full text-[10px] uppercase tracking-widest font-bold"
        :class="props.session.is_paused ? 'bg-amber-500/20 text-amber-300' : 'bg-emerald-500/20 text-emerald-300'"
      >
        {{ props.session.is_paused ? 'Paused' : 'Active' }}
      </span>
    </div>

    <p class="text-[11px] text-slate-400">
      In-game time: {{ props.session.in_game_time }} min
    </p>
  </article>
</template>
