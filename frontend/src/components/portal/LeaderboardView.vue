<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Search, RefreshCw, X, Users } from 'lucide-vue-next'
import type { LeaderboardEntry } from '@/types'
import { api } from '@/composables/useApi'
import { authState } from '@/store/auth'
import PlayerAwardsModal from '@/components/portal/PlayerAwardsModal.vue'
import LeaderboardPodium from '@/components/portal/leaderboard/LeaderboardPodium.vue'
import LeaderboardTable from '@/components/portal/leaderboard/LeaderboardTable.vue'
import {
  SORT_OPTIONS,
  filterPlayers,
  sortPlayers,
  type LeaderboardSortKey,
} from '@/components/portal/leaderboard/leaderboardUtils'

const players = ref<LeaderboardEntry[]>([])
const isLoading = ref(false)
const errorMessage = ref('')
const searchQuery = ref('')
const sortKey = ref<LeaderboardSortKey>('rank')
const selectedPlayer = ref<LeaderboardEntry | null>(null)

const currentUserId = computed(() => authState.user?.id ?? null)
const isSearching = computed(() => searchQuery.value.trim().length > 0)
const visiblePlayers = computed(() => sortPlayers(filterPlayers(players.value, searchQuery.value), sortKey.value))

async function loadLeaderboard(): Promise<void> {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const response = await api.getLeaderboard()
    players.value = response.players
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load the leaderboard.'
  } finally {
    isLoading.value = false
  }
}

function openPlayer(player: LeaderboardEntry): void {
  selectedPlayer.value = player
}

function sortButtonClass(key: LeaderboardSortKey): string {
  const base = 'px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all'
  if (sortKey.value === key) return `${base} bg-amber-300/15 text-amber-200 border border-amber-300/40 shadow-[0_0_14px_rgba(251,191,36,0.2)]`
  return `${base} border border-transparent text-slate-400 hover:text-white hover:bg-white/5`
}

onMounted(loadLeaderboard)
</script>

<template>
  <div class="space-y-8 animate-fade-in">
    <header class="relative overflow-hidden rounded-3xl border border-amber-200/10 bg-gradient-to-br from-[#0c1626] via-[#081425] to-[#120d1f] px-6 py-8 sm:px-10 sm:py-10">
      <div class="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-amber-300/70 to-transparent"></div>
      <div class="pointer-events-none absolute -top-24 -right-16 w-80 h-80 rounded-full bg-amber-400/10 blur-3xl"></div>
      <div class="pointer-events-none absolute -bottom-32 -left-10 w-80 h-80 rounded-full bg-aether-secondary/10 blur-3xl"></div>

      <div class="relative flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6">
        <div>
          <p class="text-[10px] font-black uppercase tracking-[0.4em] text-amber-300/80 flex items-center gap-2">
            <i class="ra ra-trophy"></i> Leaderboard
          </p>
          <h1 class="mt-2 font-fantasy text-3xl sm:text-4xl font-bold text-white">Hall of Legends</h1>
          <p class="mt-2 text-sm text-slate-400 max-w-xl">
            The archive remembers every deed. Adventurers are ranked by experience, trophies and the quests they saw through to the end.
          </p>
        </div>

        <div class="flex flex-col sm:flex-row gap-3 lg:items-center">
          <label class="relative flex-1 sm:min-w-[16rem]">
            <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              v-model="searchQuery"
              type="search"
              placeholder="Search adventurers..."
              aria-label="Search adventurers by name"
              class="w-full pl-9 pr-9 py-2.5 rounded-xl bg-black/30 border border-white/10 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-amber-300/40 focus:ring-2 focus:ring-amber-300/10 transition-all"
            />
            <button
              v-if="isSearching"
              type="button"
              class="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-slate-500 hover:text-white"
              aria-label="Clear search"
              @click="searchQuery = ''"
            >
              <X class="w-4 h-4" />
            </button>
          </label>
          <button
            type="button"
            class="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-white/10 bg-white/5 text-xs font-bold uppercase tracking-widest text-slate-300 hover:text-white hover:bg-white/10 disabled:opacity-50 transition-all"
            :disabled="isLoading"
            title="Refresh leaderboard"
            @click="loadLeaderboard"
          >
            <RefreshCw class="w-4 h-4" :class="isLoading ? 'animate-spin' : ''" />
            Refresh
          </button>
        </div>
      </div>

      <div class="relative mt-6 flex flex-wrap items-center gap-2">
        <span class="text-[10px] font-bold uppercase tracking-widest text-slate-500 mr-1">Sort by</span>
        <button
          v-for="option in SORT_OPTIONS"
          :key="option.key"
          type="button"
          :class="sortButtonClass(option.key)"
          :aria-pressed="sortKey === option.key"
          @click="sortKey = option.key"
        >
          {{ option.label }}
        </button>
      </div>
    </header>

    <div v-if="isLoading && players.length === 0" class="flex flex-col items-center justify-center py-20 gap-6">
      <div class="w-14 h-14 border-4 border-amber-300/10 border-t-amber-300 rounded-full animate-spin"></div>
      <p class="text-amber-200/80 font-bold uppercase tracking-[0.3em] text-xxs">Summoning the legends...</p>
    </div>

    <div v-else-if="errorMessage && players.length === 0" class="rounded-2xl border border-rose-400/20 bg-rose-500/5 p-8 text-center space-y-4">
      <p class="text-sm text-rose-200">{{ errorMessage }}</p>
      <button type="button" class="px-4 py-2 rounded-xl border border-white/10 bg-white/5 text-xs font-bold uppercase tracking-widest text-slate-200 hover:bg-white/10" @click="loadLeaderboard">
        Try again
      </button>
    </div>

    <template v-else>
      <LeaderboardPodium
        v-if="!isSearching"
        :players="players"
        :current-user-id="currentUserId"
        @select="openPlayer"
      />

      <LeaderboardTable
        v-if="visiblePlayers.length"
        :players="visiblePlayers"
        :current-user-id="currentUserId"
        @select="openPlayer"
      />

      <div v-else class="rounded-3xl border border-dashed border-white/10 py-16 px-6 flex flex-col items-center gap-3 text-center">
        <Users class="w-10 h-10 text-slate-600" />
        <p class="text-sm text-slate-400">
          {{ isSearching ? `No adventurers match "${searchQuery.trim()}".` : 'No adventurers have entered the hall yet.' }}
        </p>
      </div>
    </template>

    <PlayerAwardsModal :is-open="selectedPlayer !== null" :player="selectedPlayer" @close="selectedPlayer = null" />
  </div>
</template>
