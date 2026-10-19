<script setup lang="ts">
import { computed, ref } from 'vue'
import type { PlayerSessionSummary } from '@/composables/useApi'
import { formatShortDate, sessionStatusMeta } from './sessionStatus'

const props = defineProps<{ session: PlayerSessionSummary }>()
const emit = defineEmits<{ (e: 'open', gameId: string): void }>()

const showChapters = ref(false)
const meta = computed(() => sessionStatusMeta(props.session.status))
const isFinished = computed(() => props.session.status === 'completed' || props.session.status === 'game_over')
const isDefeated = computed(() => props.session.status === 'game_over')
const progressPercent = computed(() => {
  const { sequences_total: total, sequences_completed: done } = props.session
  return total ? Math.round((done / total) * 100) : 0
})
const currentChapter = computed(() => props.session.sequences.find(s => s.active)?.title)
const lastDate = computed(() => formatShortDate(props.session.updated_at || props.session.created_at))
</script>

<template>
  <article
    class="group relative flex flex-col overflow-hidden rounded-2xl border bg-[#0b1322]/80 transition-all duration-300 sm:flex-row"
    :class="meta.accent"
  >
    <!-- Cover -->
    <div class="relative h-32 shrink-0 overflow-hidden sm:h-auto sm:w-44">
      <img
        v-if="session.image_url"
        :src="session.image_url"
        alt=""
        class="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
        :class="isDefeated ? 'grayscale opacity-50' : 'opacity-80'"
      />
      <div v-else class="flex h-full w-full items-center justify-center bg-gradient-to-br from-aether-surface to-black">
        <i class="ra ra-scroll-unfurled text-4xl text-white/10"></i>
      </div>
      <div class="pointer-events-none absolute inset-0 bg-gradient-to-t from-[#0b1322] via-transparent to-transparent sm:bg-gradient-to-l"></div>

      <!-- Outcome seal -->
      <div
        v-if="isFinished"
        class="absolute left-3 top-3 flex h-11 w-11 items-center justify-center rounded-full border-2 text-lg shadow-lg backdrop-blur-sm"
        :class="isDefeated ? 'border-red-400/70 bg-red-950/70 text-red-300' : 'border-amber-300/80 bg-amber-950/60 text-amber-200'"
        :title="meta.label"
      >
        <i :class="isDefeated ? 'ra ra-skull' : 'ra ra-crown'"></i>
      </div>
    </div>

    <!-- Body -->
    <div class="flex min-w-0 flex-1 flex-col gap-3 p-4 sm:p-5">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <div class="min-w-0">
          <h4 class="truncate font-display text-lg leading-tight text-white">{{ session.adventure_title }}</h4>
          <p class="mt-0.5 truncate text-xs text-slate-400">
            <span v-if="session.avatar_name">as <span class="text-slate-200">{{ session.avatar_name }}</span></span>
            <span v-if="session.avatar_name && lastDate"> · </span>
            <span v-if="lastDate">{{ lastDate }}</span>
          </p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <span class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-black uppercase tracking-widest" :class="meta.badge">
            <i :class="meta.icon"></i>{{ meta.label }}
          </span>
          <span class="inline-flex items-center gap-1 rounded-full border border-aether-primary/30 bg-aether-primary/10 px-2.5 py-0.5 text-[11px] font-black tracking-wider text-aether-primary">
            {{ session.xp }} XP
          </span>
        </div>
      </div>

      <!-- Sequence progress -->
      <div v-if="session.sequences_total" class="space-y-1.5">
        <div class="flex items-center justify-between text-[11px] font-bold uppercase tracking-widest text-slate-500">
          <span>Sequences {{ session.sequences_completed }} / {{ session.sequences_total }}</span>
          <span>{{ progressPercent }}%</span>
        </div>
        <div class="flex gap-1" role="list" :aria-label="`${session.sequences_completed} of ${session.sequences_total} sequences completed`">
          <div
            v-for="(seq, idx) in session.sequences"
            :key="seq.id || idx"
            role="listitem"
            :title="`${seq.title}${seq.completed ? ' (completed)' : seq.active ? ' (current)' : ''}`"
            class="h-2 flex-1 rounded-full transition-colors"
            :class="seq.completed
              ? (isDefeated ? 'bg-red-400/60' : 'bg-aether-primary')
              : seq.active ? 'bg-sky-400/70 animate-pulse-subtle' : 'bg-white/10'"
          ></div>
        </div>
        <p v-if="currentChapter" class="text-xs text-slate-400">
          Current: <span class="text-slate-200">{{ currentChapter }}</span>
        </p>
      </div>
      <p v-else class="text-xs italic text-slate-500">This adventure has no sequences.</p>

      <p v-if="isFinished && session.status_note" class="line-clamp-2 border-l-2 pl-3 text-xs italic text-slate-400" :class="isDefeated ? 'border-red-500/40' : 'border-amber-300/40'">
        {{ session.status_note }}
      </p>

      <!-- Chapter list -->
      <ol v-if="showChapters" class="space-y-1 rounded-xl bg-black/30 p-3">
        <li v-for="(seq, idx) in session.sequences" :key="seq.id || idx" class="flex items-center gap-2 text-xs">
          <span
            class="flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-black"
            :class="seq.completed ? 'bg-aether-primary text-[#081425]' : seq.active ? 'border border-sky-400 text-sky-300' : 'border border-white/15 text-slate-600'"
          >{{ seq.completed ? '✓' : idx + 1 }}</span>
          <span class="flex-1 truncate" :class="seq.completed ? 'text-slate-200' : 'text-slate-500'">{{ seq.title }}</span>
          <span v-if="seq.exp_reward" class="text-[10px] font-bold text-slate-500">+{{ seq.exp_reward }} XP</span>
        </li>
      </ol>

      <div class="mt-auto flex items-center justify-between gap-2 pt-1">
        <button
          v-if="session.sequences_total"
          type="button"
          class="text-[11px] font-black uppercase tracking-widest text-slate-500 transition-colors hover:text-white"
          :aria-expanded="showChapters"
          @click="showChapters = !showChapters"
        >
          {{ showChapters ? 'Hide sequences' : 'Show sequences' }}
        </button>
        <span v-else></span>
        <button
          type="button"
          class="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] font-black uppercase tracking-widest text-slate-200 transition-all hover:border-aether-primary/40 hover:text-aether-primary"
          @click="emit('open', session.game_id)"
        >
          {{ session.status === 'active' ? 'Resume' : 'Open' }}
        </button>
      </div>
    </div>
  </article>
</template>
