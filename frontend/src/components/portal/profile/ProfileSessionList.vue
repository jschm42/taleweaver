<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ProfileSessionCard from './ProfileSessionCard.vue'
import ProfileSessionRow from './ProfileSessionRow.vue'
import { SESSION_FILTERS, SESSION_SORTS } from './sessionStatus'
import type { ProfileSessions } from './useProfileSessions'

type ViewMode = 'list' | 'cards'
const VIEW_STORAGE_KEY = 'taleweaver.profile.sessionView'

const props = defineProps<{ state: ProfileSessions }>()
// Top-level refs so the template unwraps them and v-model binds straight to the composable.
const { items, total, counts, filter, search, sort, isLoading, isLoadingMore, error, hasMore, reload, loadMore } = props.state

const router = useRouter()
const view = ref<ViewMode>(readStoredView())

function readStoredView(): ViewMode {
  try {
    return localStorage.getItem(VIEW_STORAGE_KEY) === 'cards' ? 'cards' : 'list'
  } catch {
    return 'list'
  }
}

watch(view, (value) => {
  try {
    localStorage.setItem(VIEW_STORAGE_KEY, value)
  } catch {
    // Storage unavailable (private mode): the choice only lasts for this visit.
  }
})

function openSession(gameId: string): void {
  router.push({ name: 'game', params: { id: gameId } })
}
</script>

<template>
  <section class="space-y-4">
    <!-- Toolbar -->
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
      <label class="relative min-w-0 flex-1">
        <span class="sr-only">Search adventures</span>
        <svg class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" stroke-linecap="round" />
        </svg>
        <input
          v-model="search"
          type="search"
          maxlength="100"
          placeholder="Search by adventure or hero..."
          class="w-full rounded-xl border border-white/10 bg-black/30 py-2 pl-9 pr-3 text-sm text-white placeholder:text-slate-500 outline-none focus:border-aether-primary/50"
        />
      </label>
      <div class="flex items-center gap-2">
        <label class="sr-only" for="profile-session-sort">Sort adventures</label>
        <select
          id="profile-session-sort"
          v-model="sort"
          class="cursor-pointer rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-200 outline-none focus:border-aether-primary/50"
        >
          <option v-for="option in SESSION_SORTS" :key="option.key" :value="option.key">{{ option.label }}</option>
        </select>
        <div class="flex rounded-xl border border-white/10 bg-black/30 p-0.5" role="group" aria-label="Layout">
          <button
            v-for="mode in (['list', 'cards'] as const)"
            :key="mode"
            type="button"
            :aria-pressed="view === mode"
            :title="mode === 'list' ? 'Compact list' : 'Detailed cards'"
            class="flex h-8 w-9 items-center justify-center rounded-lg text-sm transition-colors"
            :class="view === mode ? 'bg-aether-primary/15 text-aether-primary' : 'text-slate-500 hover:text-white'"
            @click="view = mode"
          >
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
              <path v-if="mode === 'list'" d="M4 6h16M4 12h16M4 18h16" />
              <path v-else d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" />
            </svg>
            <span class="sr-only">{{ mode === 'list' ? 'Compact list' : 'Detailed cards' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Status filter -->
    <div class="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1" role="tablist" aria-label="Filter adventures">
      <button
        v-for="option in SESSION_FILTERS"
        :key="option.key"
        type="button"
        role="tab"
        :aria-selected="filter === option.key"
        class="inline-flex shrink-0 items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs font-bold transition-all"
        :class="filter === option.key
          ? 'border-aether-primary/50 bg-aether-primary/15 text-aether-primary'
          : 'border-white/10 bg-white/5 text-slate-400 hover:text-white'"
        @click="filter = option.key"
      >
        {{ option.label }}
        <span class="rounded-full bg-black/30 px-1.5 text-[10px] tabular-nums">{{ counts[option.key] }}</span>
      </button>
    </div>

    <!-- States -->
    <div v-if="isLoading && !items.length" class="space-y-2">
      <div v-for="n in 5" :key="n" class="h-14 animate-pulse rounded-xl border border-white/5 bg-white/[0.03]"></div>
    </div>

    <div v-else-if="error && !items.length" class="rounded-2xl border border-red-500/20 bg-red-500/5 p-6 text-center">
      <p class="text-sm text-red-300">{{ error }}</p>
      <button type="button" class="mt-3 text-xs font-black uppercase tracking-widest text-slate-300 hover:text-white" @click="reload">
        Try again
      </button>
    </div>

    <div v-else-if="!items.length" class="rounded-2xl border border-dashed border-white/10 py-14 text-center">
      <i class="ra ra-scroll-unfurled mb-3 block text-4xl text-white/10"></i>
      <p class="text-sm text-slate-400">
        {{ counts.all || search ? 'No adventures match these filters.' : 'No adventures yet. Start one from the portal!' }}
      </p>
    </div>

    <!-- Results -->
    <template v-else>
      <ul
        v-if="view === 'list'"
        class="divide-y divide-white/5 overflow-hidden rounded-2xl border border-white/10 bg-[#0b1322]/80 transition-opacity"
        :class="{ 'opacity-60': isLoading }"
      >
        <ProfileSessionRow v-for="session in items" :key="session.game_id" :session="session" @open="openSession" />
      </ul>
      <div v-else class="grid gap-4 transition-opacity" :class="{ 'opacity-60': isLoading }">
        <ProfileSessionCard v-for="session in items" :key="session.game_id" :session="session" @open="openSession" />
      </div>

      <div class="flex flex-col items-center gap-2 pt-1">
        <p class="text-[11px] font-bold uppercase tracking-widest text-slate-500 tabular-nums">
          Showing {{ items.length }} of {{ total }}
        </p>
        <p v-if="error" class="text-xs text-red-300">{{ error }}</p>
        <button
          v-if="hasMore"
          type="button"
          :disabled="isLoadingMore"
          class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-[11px] font-black uppercase tracking-widest text-slate-200 transition-all hover:border-aether-primary/40 hover:text-aether-primary disabled:opacity-50"
          @click="loadMore"
        >
          <i v-if="isLoadingMore" class="ra ra-cycle animate-spin"></i>
          {{ isLoadingMore ? 'Loading...' : 'Load more' }}
        </button>
      </div>
    </template>
  </section>
</template>
