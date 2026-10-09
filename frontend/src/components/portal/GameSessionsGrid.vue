<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import type { GameSession } from '@/types'
import { Loader2 } from 'lucide-vue-next'
import GameSessionCard from './GameSessionCard.vue'

const props = defineProps<{
  sessions: GameSession[]
  hasMore?: boolean
  totalFilteredCount?: number
}>()

const emit = defineEmits<{
  (e: 'resume', gameId: string): void
  (e: 'delete', gameId: string, title: string): void
  (e: 'copy', gameId: string): void
  (e: 'switch-to-templates'): void
  (e: 'edit-note', gameId: string, currentNote: string): void
  (e: 'export', gameId: string): void
  (e: 'load-more'): void
}>()

const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null
let scrollContainer: HTMLElement | null = null

function handleScroll() {
  if (!scrollContainer) return
  if (scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight < 400) {
    emit('load-more')
  }
}

onMounted(() => {
  if (sentinelRef.value) {
    scrollContainer = sentinelRef.value.closest('.overflow-y-auto') as HTMLElement | null
    if (scrollContainer) {
      scrollContainer.addEventListener('scroll', handleScroll, { passive: true })
    }
    observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          emit('load-more')
        }
      },
      { root: scrollContainer, rootMargin: '400px' }
    )
    observer.observe(sentinelRef.value)
  }
})

onUnmounted(() => {
  if (scrollContainer) {
    scrollContainer.removeEventListener('scroll', handleScroll)
  }
  if (observer) {
    observer.disconnect()
    observer = null
  }
})
</script>

<template>
  <div class="space-y-6">
    <div v-if="sessions.length === 0" class="rounded-xl border border-white/10 bg-aether-surface/20 p-8 sm:p-12 text-center flex flex-col items-center gap-4">
      <div class="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-white/5 flex items-center justify-center text-2xl sm:text-3xl text-slate-500 mb-2">
        <i class="ra ra-pawn"></i>
      </div>
      <p class="text-sm sm:text-base text-slate-400 max-w-md">
        No active sessions found matching your criteria. Discover new worlds in the Adventure Library and start your journey.
      </p>
      <button
        @click="$emit('switch-to-templates')"
        class="mt-2 px-5 sm:px-6 py-3 rounded-xl bg-aether-primary/10 border border-aether-primary/30 text-aether-primary font-bold hover:bg-aether-primary/20 transition-all uppercase tracking-widest text-xxs flex items-center gap-3"
      >
        <i class="ra ra-book text-sm"></i>
        Adventure Library
      </button>
    </div>
    
    <div v-else class="space-y-6">
      <div class="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-3 sm:gap-4 lg:gap-5">
        <GameSessionCard
          v-for="entry in sessions"
          :key="entry.game_id"
          :session="entry"
          @resume="(id) => $emit('resume', id)"
          @delete="(id, title) => $emit('delete', id, title)"
          @copy="(id) => $emit('copy', id)"
          @edit-note="(id, note) => $emit('edit-note', id, note)"
          @export="(id) => $emit('export', id)"
        />
      </div>

      <!-- Infinite Scroll Sentinel & Loader -->
      <div ref="sentinelRef" class="py-6 flex items-center justify-center">
        <div v-if="props.hasMore" class="flex items-center gap-2 text-xs text-slate-400 bg-black/40 px-4 py-2 rounded-xl border border-white/10">
          <Loader2 class="w-4 h-4 animate-spin text-aether-primary" />
          <span>Loading more sessions (showing {{ props.sessions.length }} of {{ props.totalFilteredCount }})...</span>
        </div>
        <div v-else-if="props.sessions.length > 8" class="text-xs text-slate-500">
          All {{ props.sessions.length }} sessions loaded
        </div>
      </div>
    </div>
  </div>
</template>
