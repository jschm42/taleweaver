<script setup lang="ts">
import { ref } from 'vue'
import type { GameSession } from '@/types'
import { MoreHorizontal, Clock } from 'lucide-vue-next'

const props = defineProps<{
  session: GameSession
}>()

const emit = defineEmits<{
  (e: 'resume', gameId: string): void
  (e: 'delete', gameId: string, title: string): void
  (e: 'copy', gameId: string): void
}>()

const isMenuOpen = ref(false)

function toggleMenu(): void {
  isMenuOpen.value = !isMenuOpen.value
}

function closeMenu(): void {
  isMenuOpen.value = false
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return 'Recently'
  const d = new Date(dateStr)
  return d.toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function runAction(action: 'resume' | 'delete' | 'copy'): void {
  if (action === 'resume') {
    emit('resume', props.session.game_id)
  } else if (action === 'delete') {
    emit('delete', props.session.game_id, props.session.adventure_title)
  } else if (action === 'copy') {
    emit('copy', props.session.game_id)
  }
  closeMenu()
}
</script>

<template>
  <article class="rounded-xl border border-white/10 bg-aether-surface/20 flex flex-col relative group">
    <!-- Top Cover Area -->
    <div class="aspect-[3/2] relative bg-black/30 border-b border-white/5">
      <div class="absolute inset-0 overflow-hidden rounded-t-xl">
        <!-- Ribbon for Game Over / Completed -->
        <div v-if="props.session.status === 'game_over'" class="absolute -right-12 top-6 bg-red-600 text-white text-xs font-black uppercase tracking-[0.2em] py-1.5 w-48 text-center rotate-45 shadow-lg z-10">
          Game Over
        </div>
        <div v-if="props.session.status === 'completed'" class="absolute -right-12 top-6 bg-emerald-500 text-white text-xs font-black uppercase tracking-[0.2em] py-1.5 w-48 text-center rotate-45 shadow-lg z-10">
          Completed
        </div>
        <img
          v-if="props.session.image_url"
          :src="props.session.image_url"
          class="w-full h-full object-cover object-top opacity-60 group-hover:opacity-80 transition-opacity"
          alt="Adventure cover"
        />
        <div v-else class="w-full h-full flex items-center justify-center text-slate-500 text-xs font-bold uppercase tracking-widest">
          No Cover
        </div>
      </div>
      
      <!-- Status Badge -->
      <div class="absolute top-3 left-3">
        <span
          class="px-2.5 py-1 rounded-full text-xs uppercase tracking-widest font-black"
          :class="{
            'bg-amber-500/20 text-amber-300': props.session.is_paused && (!props.session.status || props.session.status === 'active'),
            'bg-emerald-500/20 text-emerald-300': !props.session.is_paused && (!props.session.status || props.session.status === 'active'),
            'bg-red-500/20 text-red-300': props.session.status === 'game_over',
            'bg-emerald-600/40 text-emerald-100': props.session.status === 'completed'
          }"
        >
          {{ 
            props.session.status === 'game_over' ? 'Defeated' : 
            props.session.status === 'completed' ? 'Victory' : 
            (props.session.is_paused ? 'Paused' : 'Active') 
          }}
        </span>
      </div>

      <!-- Action Dots -->
      <div class="absolute top-3 right-3 z-20">
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
            class="w-full text-left px-4 py-2.5 text-xs font-black uppercase tracking-widest text-slate-400 hover:text-white hover:bg-white/5"
            @click="runAction('copy')"
          >
            Copy Session
          </button>
          <div class="h-[1px] bg-white/5 mx-2 my-1"></div>
          <button
            class="w-full text-left px-4 py-2.5 text-xs font-black uppercase tracking-widest text-red-400/60 hover:text-red-400 hover:bg-red-500/10"
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
        <h3 class="text-xl font-black text-white leading-tight line-clamp-1 tracking-tight flex items-center gap-2">
          <span class="truncate">{{ props.session.adventure_title }}</span>
          <span v-if="props.session.copied_from_id" class="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] font-bold uppercase tracking-wider shrink-0">
            Copy
          </span>
          <span v-if="props.session.adventure_version" class="text-[10px] font-mono font-bold text-slate-500 opacity-60 shrink-0">v{{ props.session.adventure_version }}</span>
        </h3>
        <div class="flex flex-col gap-1.5 mt-3">
          <p class="text-sm text-slate-400 flex items-center gap-2 font-bold uppercase tracking-[0.15em]">
            <span class="w-2 h-2 rounded-full bg-emerald-500/60"></span>
            {{ props.session.current_scene_name || 'Exploring...' }}
          </p>
          <p class="text-xs text-slate-500 flex items-center gap-2 font-black uppercase tracking-widest">
            <Clock class="w-3 h-3 opacity-50" />
            {{ props.session.copied_from_id ? 'Copied:' : 'Started:' }} {{ formatDate(props.session.created_at) }}
          </p>
        </div>
      </div>

      <!-- Progress Stats -->
      <div class="grid grid-cols-3 gap-4 pt-1">
        <!-- Quests -->
        <div class="min-w-0 flex flex-col gap-2.5">
          <div class="flex items-center justify-between gap-2 min-w-0">
            <span class="text-[10px] font-black uppercase tracking-widest text-slate-500 truncate">Quests</span>
            <span class="text-[10px] font-bold text-slate-300 shrink-0">{{ props.session.completed_quest_count || 0 }}/{{ props.session.quest_count || 0 }}</span>
          </div>
          <div class="h-1.5 bg-white/5 rounded-full overflow-hidden">
            <div 
              class="h-full bg-emerald-500 transition-all duration-500 shadow-[0_0_10px_rgba(16,185,129,0.3)]"
              :style="{ width: `${((props.session.completed_quest_count || 0) / ((props.session.quest_count || 0) || 1)) * 100}%` }"
            ></div>
          </div>
        </div>

        <!-- Awards -->
        <div class="min-w-0 flex flex-col gap-2.5">
          <div class="flex items-center justify-between gap-2 min-w-0">
            <span class="text-[10px] font-black uppercase tracking-widest text-slate-500 truncate">Awards</span>
            <span class="text-[10px] font-bold text-slate-300 shrink-0">{{ props.session.earned_award_count || 0 }}/{{ props.session.award_count || 0 }}</span>
          </div>
          <div class="h-1.5 bg-white/5 rounded-full overflow-hidden">
            <div 
              class="h-full bg-amber-400 transition-all duration-500 shadow-[0_0_10px_rgba(251,191,36,0.3)]"
              :style="{ width: `${((props.session.earned_award_count || 0) / ((props.session.award_count || 0) || 1)) * 100}%` }"
            ></div>
          </div>
        </div>

        <!-- Time Played -->
        <div class="min-w-0 flex flex-col gap-1.5 items-end text-right">
          <span class="text-[10px] font-black uppercase tracking-widest text-slate-500">Playtime</span>
          <span class="text-base font-black text-slate-200 tracking-wide leading-none truncate">{{ props.session.in_game_time || 0 }} MIN</span>
        </div>
      </div>

      <!-- Action Button -->
      <button
        class="w-full py-3.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all border flex items-center justify-center gap-3 mt-1 shadow-lg group/btn"
        :class="[
          props.session.status === 'game_over' ? 'bg-red-500/10 text-red-400 border-red-500/20 hover:bg-red-500/20 shadow-red-500/5' :
          props.session.status === 'completed' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20 hover:bg-amber-500/20 shadow-amber-500/5' :
          'bg-emerald-500/10 text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/20 shadow-emerald-500/5'
        ]"
        @click="runAction('resume')"
      >
        <i :class="[
          'text-sm transition-transform group-hover/btn:scale-110',
          props.session.status === 'game_over' ? 'ra ra-skull' : 
          props.session.status === 'completed' ? 'ra ra-trophy' : 
          'ra ra-play'
        ]"></i>
        {{ 
          props.session.status === 'game_over' ? 'Continue Anyway' : 
          props.session.status === 'completed' ? 'Continue Anyway' : 
          'Resume Game' 
        }}
      </button>
    </div>
  </article>
</template>

