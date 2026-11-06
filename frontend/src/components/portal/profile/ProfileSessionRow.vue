<script setup lang="ts">
import { computed } from 'vue'
import type { PlayerSessionSummary } from '@/composables/useApi'
import { formatShortDate, sessionStatusMeta } from './sessionStatus'

/** Dense one-line entry for long adventure histories (the card view shows the details). */
const props = defineProps<{ session: PlayerSessionSummary }>()
const emit = defineEmits<{ (e: 'open', gameId: string): void }>()

const meta = computed(() => sessionStatusMeta(props.session.status))
const isDefeated = computed(() => props.session.status === 'game_over')
const progressPercent = computed(() => {
  const { sequences_total: total, sequences_completed: done } = props.session
  return total ? Math.round((done / total) * 100) : 0
})
const lastDate = computed(() => formatShortDate(
  props.session.last_played_at || props.session.updated_at || props.session.created_at,
))
</script>

<template>
  <li>
    <button
      type="button"
      class="group flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-white/[0.04] focus-visible:bg-white/[0.06] focus-visible:outline-none sm:gap-4 sm:px-4"
      @click="emit('open', session.game_id)"
    >
      <div class="h-11 w-11 shrink-0 overflow-hidden rounded-lg border border-white/10 bg-black/40">
        <img
          v-if="session.image_url"
          :src="session.image_url"
          alt=""
          loading="lazy"
          class="h-full w-full object-cover"
          :class="isDefeated ? 'grayscale opacity-50' : 'opacity-85'"
        />
        <i v-else class="ra ra-scroll-unfurled flex h-full w-full items-center justify-center text-lg text-white/15"></i>
      </div>

      <div class="min-w-0 flex-1">
        <p class="truncate text-sm font-bold text-white group-hover:text-aether-primary">{{ session.adventure_title }}</p>
        <p class="truncate text-xs text-slate-500">
          <span v-if="session.avatar_name">as <span class="text-slate-300">{{ session.avatar_name }}</span></span>
          <span v-if="session.avatar_name && lastDate"> · </span>
          <span v-if="lastDate">{{ lastDate }}</span>
        </p>
      </div>

      <div v-if="session.sequences_total" class="hidden w-28 shrink-0 md:block" :title="`${session.sequences_completed} / ${session.sequences_total} sequences`">
        <div class="h-1.5 overflow-hidden rounded-full bg-white/10">
          <div
            class="h-full rounded-full"
            :class="isDefeated ? 'bg-red-400/60' : 'bg-aether-primary'"
            :style="{ width: `${progressPercent}%` }"
          ></div>
        </div>
        <p class="mt-1 text-[10px] font-bold tabular-nums text-slate-500">{{ session.sequences_completed }} / {{ session.sequences_total }}</p>
      </div>

      <span class="hidden w-16 shrink-0 text-right text-xs font-black tabular-nums text-aether-primary sm:block">{{ session.xp }} XP</span>

      <span
        class="inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-widest"
        :class="meta.badge"
        :title="meta.label"
      >
        <i :class="meta.icon"></i><span class="hidden lg:inline">{{ meta.label }}</span>
      </span>
    </button>
  </li>
</template>
