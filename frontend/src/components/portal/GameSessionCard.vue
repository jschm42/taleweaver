<script setup lang="ts">
import { ref } from 'vue'
import type { GameSession } from '@/types'
import { MoreHorizontal } from 'lucide-vue-next'

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
  <article class="rounded-xl border border-white/10 bg-aether-surface/20 flex flex-col overflow-hidden relative group">
    <!-- Top Cover Area -->
    <div class="aspect-[1.8/1] relative overflow-hidden bg-black/30 border-b border-white/5">
      <img
        v-if="props.session.image_url"
        :src="props.session.image_url"
        class="w-full h-full object-cover opacity-60 group-hover:opacity-80 transition-opacity"
        alt="Adventure cover"
      />
      <div v-else class="w-full h-full flex items-center justify-center text-slate-500 text-[10px] font-bold uppercase tracking-widest">
        No Cover
      </div>
      
      <!-- Status Badge -->
      <div class="absolute top-3 left-3">
        <span
          class="px-2.5 py-1 rounded-full text-[9px] uppercase tracking-widest font-black"
          :class="props.session.is_paused ? 'bg-amber-500/20 text-amber-300' : 'bg-emerald-500/20 text-emerald-300'"
        >
          {{ props.session.is_paused ? 'Paused' : 'Active' }}
        </span>
      </div>

      <!-- Action Dots -->
      <div class="absolute top-3 right-3">
        <button
          @click.stop="toggleMenu"
          class="w-8 h-8 rounded-full bg-black/40 backdrop-blur-md border border-white/10 text-white hover:bg-black/60 transition-all flex items-center justify-center"
          title="Session actions"
        >
          <MoreHorizontal class="w-5 h-5" />
        </button>

        <div v-if="isMenuOpen" class="fixed inset-0 z-20" @click="closeMenu"></div>
        <div
          v-if="isMenuOpen"
          class="absolute right-0 top-10 z-30 w-44 bg-[#0d1117] border border-white/10 rounded-xl shadow-[0_12px_40px_rgba(0,0,0,0.6)] overflow-hidden backdrop-blur-xl"
        >
          <button
            v-if="!props.session.is_paused"
            class="w-full text-left px-4 py-2.5 text-[10px] font-black uppercase tracking-widest text-amber-400/80 hover:text-amber-400 hover:bg-amber-500/10"
            @click="runAction('pause')"
          >
            Pause
          </button>
          <button
            v-else
            class="w-full text-left px-4 py-2.5 text-[10px] font-black uppercase tracking-widest text-sky-400/80 hover:text-sky-400 hover:bg-sky-500/10"
            @click="runAction('unpause')"
          >
            Unpause
          </button>
          <button
            class="w-full text-left px-4 py-2.5 text-[10px] font-black uppercase tracking-widest text-slate-400 hover:text-white hover:bg-white/5"
            @click="runAction('reset')"
          >
            Reset
          </button>
          <div class="h-[1px] bg-white/5 mx-2 my-1"></div>
          <button
            class="w-full text-left px-4 py-2.5 text-[10px] font-black uppercase tracking-widest text-red-400/60 hover:text-red-400 hover:bg-red-500/10"
            @click="runAction('delete')"
          >
            Delete Session
          </button>
        </div>
      </div>
    </div>

    <!-- Content Area -->
    <div class="p-6 flex flex-col gap-6">
      <div class="min-w-0">
        <h3 class="text-2xl font-black text-white leading-tight line-clamp-1 tracking-tight">{{ props.session.adventure_title }}</h3>
        <p class="text-sm text-slate-400 mt-2 flex items-center gap-2 font-bold uppercase tracking-[0.15em]">
          <span class="w-2 h-2 rounded-full bg-emerald-500/60"></span>
          {{ props.session.current_scene_name || 'Exploring...' }}
        </p>
      </div>

      <!-- Progress Stats Single Row -->
      <div class="flex items-end justify-between gap-6 pt-1">
        <!-- Quests -->
        <div v-if="props.session.quest_count" class="flex-1 flex flex-col gap-2.5">
          <div class="flex items-center justify-between">
            <span class="text-[10px] font-black uppercase tracking-widest text-slate-500">Quests</span>
            <span class="text-xs font-bold text-slate-300">{{ props.session.completed_quest_count }}/{{ props.session.quest_count }}</span>
          </div>
          <div class="h-1.5 bg-white/5 rounded-full overflow-hidden">
            <div 
              class="h-full bg-emerald-500 transition-all duration-500 shadow-[0_0_10px_rgba(16,185,129,0.3)]"
              :style="{ width: `${(props.session.completed_quest_count || 0) / (props.session.quest_count || 1) * 100}%` }"
            ></div>
          </div>
        </div>

        <!-- Awards -->
        <div v-if="props.session.award_count" class="flex-1 flex flex-col gap-2.5">
          <div class="flex items-center justify-between">
            <span class="text-[10px] font-black uppercase tracking-widest text-slate-500">Awards</span>
            <span class="text-xs font-bold text-slate-300">{{ props.session.earned_award_count }}/{{ props.session.award_count }}</span>
          </div>
          <div class="h-1.5 bg-white/5 rounded-full overflow-hidden">
            <div 
              class="h-full bg-amber-400 transition-all duration-500 shadow-[0_0_10px_rgba(251,191,36,0.3)]"
              :style="{ width: `${(props.session.earned_award_count || 0) / (props.session.award_count || 1) * 100}%` }"
            ></div>
          </div>
        </div>

        <!-- Time Played -->
        <div class="flex flex-col gap-1.5 items-end shrink-0">
          <span class="text-[10px] font-black uppercase tracking-widest text-slate-500">Playtime</span>
          <span class="text-sm font-black text-slate-200 tracking-widest">{{ props.session.in_game_time }} MIN</span>
        </div>
      </div>

      <!-- Action Button -->
      <button
        class="w-full py-3.5 rounded-xl bg-emerald-500/10 text-emerald-400 text-xs font-black uppercase tracking-widest hover:bg-emerald-500/20 transition-all border border-emerald-500/20 flex items-center justify-center gap-3 mt-1 shadow-lg shadow-emerald-500/5 group/btn"
        @click="runAction('resume')"
      >
        <i class="ra ra-play text-sm transition-transform group-hover/btn:scale-110"></i>
        Resume Game
      </button>
    </div>
  </article>
</template>
