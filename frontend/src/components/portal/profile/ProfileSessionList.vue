<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { PlayerSessionSummary } from '@/composables/useApi'
import ProfileSessionCard from './ProfileSessionCard.vue'
import { SESSION_FILTERS, type SessionFilter } from './sessionStatus'

const props = defineProps<{
  sessions: PlayerSessionSummary[]
  isLoading: boolean
  error: string
}>()
const emit = defineEmits<{ (e: 'retry'): void }>()

const router = useRouter()
const activeFilter = ref<SessionFilter>('all')

const counts = computed(() => {
  const result: Record<SessionFilter, number> = { all: props.sessions.length, active: 0, completed: 0, game_over: 0, archived: 0 }
  for (const session of props.sessions) {
    const key = session.status as SessionFilter
    if (key in result) result[key] += 1
  }
  return result
})

const visibleSessions = computed(() => activeFilter.value === 'all'
  ? props.sessions
  : props.sessions.filter(s => s.status === activeFilter.value))

function openSession(gameId: string) {
  router.push({ name: 'game', params: { id: gameId } })
}
</script>

<template>
  <section class="space-y-5">
    <div class="flex flex-wrap gap-2" role="tablist" aria-label="Filter adventures">
      <button
        v-for="filter in SESSION_FILTERS"
        :key="filter.key"
        type="button"
        role="tab"
        :aria-selected="activeFilter === filter.key"
        class="inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs font-bold transition-all"
        :class="activeFilter === filter.key
          ? 'border-aether-primary/50 bg-aether-primary/15 text-aether-primary'
          : 'border-white/10 bg-white/5 text-slate-400 hover:text-white'"
        @click="activeFilter = filter.key"
      >
        {{ filter.label }}
        <span class="rounded-full bg-black/30 px-1.5 text-[10px] tabular-nums">{{ counts[filter.key] }}</span>
      </button>
    </div>

    <div v-if="isLoading" class="grid gap-4">
      <div v-for="n in 3" :key="n" class="h-36 animate-pulse rounded-2xl border border-white/5 bg-white/[0.03]"></div>
    </div>

    <div v-else-if="error" class="rounded-2xl border border-red-500/20 bg-red-500/5 p-6 text-center">
      <p class="text-sm text-red-300">{{ error }}</p>
      <button type="button" class="mt-3 text-xs font-black uppercase tracking-widest text-slate-300 hover:text-white" @click="emit('retry')">
        Try again
      </button>
    </div>

    <div v-else-if="!visibleSessions.length" class="rounded-2xl border border-dashed border-white/10 py-14 text-center">
      <i class="ra ra-scroll-unfurled mb-3 block text-4xl text-white/10"></i>
      <p class="text-sm text-slate-400">
        {{ sessions.length ? 'No adventures match this filter.' : 'No adventures yet. Start one from the portal!' }}
      </p>
    </div>

    <div v-else class="grid gap-4">
      <ProfileSessionCard
        v-for="session in visibleSessions"
        :key="session.game_id"
        :session="session"
        @open="openSession"
      />
    </div>
  </section>
</template>
