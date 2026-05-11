<script setup lang="ts">
import type { GameSession } from '@/types'
import GameSessionCard from './GameSessionCard.vue'

defineProps<{
  sessions: GameSession[]
}>()

defineEmits<{
  (e: 'resume', gameId: string): void
  (e: 'delete', gameId: string, title: string): void
  (e: 'switch-to-templates'): void
}>()
</script>

<template>
  <div class="space-y-6">
    <div v-if="sessions.length === 0" class="rounded-xl border border-white/10 bg-aether-surface/20 p-12 text-center flex flex-col items-center gap-4">
      <div class="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center text-3xl text-slate-500 mb-2">
        <i class="ra ra-pawn"></i>
      </div>
      <p class="text-slate-400 max-w-md">
        No active sessions yet. Discover new worlds in the Adventure Library and start your journey.
      </p>
      <button 
        @click="$emit('switch-to-templates')"
        class="mt-2 px-6 py-3 rounded-xl bg-aether-primary/10 border border-aether-primary/30 text-aether-primary font-bold hover:bg-aether-primary/20 transition-all uppercase tracking-widest text-xxs flex items-center gap-3"
      >
        <i class="ra ra-book text-sm"></i>
        Adventure Library
      </button>
    </div>
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 2xl:grid-cols-6 gap-5 xl:gap-4">
      <GameSessionCard
        v-for="entry in sessions"
        :key="entry.game_id"
        :session="entry"
        @resume="(id) => $emit('resume', id)"
        @delete="(id, title) => $emit('delete', id, title)"
      />
    </div>
  </div>
</template>
