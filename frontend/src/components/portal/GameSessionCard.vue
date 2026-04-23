<script setup lang="ts">
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
</script>

<template>
  <article class="rounded-xl border border-white/10 bg-[#0d1524] p-4 flex flex-col gap-4">
    <div class="flex items-start justify-between gap-3">
      <div>
        <h3 class="text-lg font-black text-white leading-tight">{{ props.session.adventure_title }}</h3>
        <p class="text-[11px] uppercase tracking-widest text-slate-400 mt-1">
          Scene: {{ props.session.current_scene_name || 'Unknown' }}
        </p>
      </div>
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

    <div class="grid grid-cols-2 gap-2">
      <button
        class="px-3 py-2 rounded-lg bg-emerald-500/20 text-emerald-300 text-xs font-bold uppercase tracking-widest hover:bg-emerald-500/30 transition-colors"
        @click="emit('resume', props.session.game_id)"
      >
        Resume
      </button>

      <button
        v-if="!props.session.is_paused"
        class="px-3 py-2 rounded-lg bg-amber-500/20 text-amber-300 text-xs font-bold uppercase tracking-widest hover:bg-amber-500/30 transition-colors"
        @click="emit('pause', templateIdOfSession())"
      >
        Pause
      </button>
      <button
        v-else
        class="px-3 py-2 rounded-lg bg-sky-500/20 text-sky-300 text-xs font-bold uppercase tracking-widest hover:bg-sky-500/30 transition-colors"
        @click="emit('resumeHeartbeat', templateIdOfSession())"
      >
        Unpause
      </button>

      <button
        class="px-3 py-2 rounded-lg bg-white/10 text-slate-200 text-xs font-bold uppercase tracking-widest hover:bg-white/20 transition-colors"
        @click="emit('reset', templateIdOfSession())"
      >
        Reset
      </button>

      <button
        class="px-3 py-2 rounded-lg bg-red-500/15 text-red-300 text-xs font-bold uppercase tracking-widest hover:bg-red-500/25 transition-colors"
        @click="emit('delete', props.session.game_id, props.session.adventure_title)"
      >
        Delete Session
      </button>
    </div>
  </article>
</template>
