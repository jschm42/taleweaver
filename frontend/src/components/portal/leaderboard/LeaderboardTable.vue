<script setup lang="ts">
import type { Component } from 'vue'
import { Crown, Medal, Shield, Trophy, Zap, CircleCheck, CircleX, ChevronRight } from 'lucide-vue-next'
import type { LeaderboardEntry } from '@/types'
import PlayerAvatar from './PlayerAvatar.vue'
import { formatNumber, rankTier, type RankTier } from './leaderboardUtils'

const props = defineProps<{
  players: LeaderboardEntry[]
  currentUserId?: string | null
}>()

const emit = defineEmits<{ (e: 'select', player: LeaderboardEntry): void }>()

const RANK_BADGES: Record<RankTier, { icon: Component | null; badge: string }> = {
  gold: { icon: Crown, badge: 'bg-amber-400/15 text-amber-300 border-amber-300/40 shadow-[0_0_14px_rgba(251,191,36,0.35)]' },
  silver: { icon: Medal, badge: 'bg-slate-300/10 text-slate-200 border-slate-300/30' },
  bronze: { icon: Shield, badge: 'bg-orange-500/10 text-orange-300 border-orange-400/30' },
  plain: { icon: null, badge: 'bg-white/5 text-slate-400 border-white/10' },
}

const GRID = 'grid grid-cols-[3rem_minmax(0,1fr)_auto] md:grid-cols-[4rem_minmax(0,1.6fr)_1fr_0.8fr_1.2fr_auto] items-center gap-3 md:gap-4'

function badgeFor(player: LeaderboardEntry) {
  return RANK_BADGES[rankTier(player.rank)]
}

function select(player: LeaderboardEntry): void {
  emit('select', player)
}
</script>

<template>
  <div class="rounded-3xl border border-white/5 bg-[#060d18]/70 backdrop-blur-xl overflow-hidden">
    <div :class="[GRID, 'px-4 md:px-6 py-3 border-b border-white/5 text-[10px] font-black uppercase tracking-[0.25em] text-slate-500']">
      <span>Rank</span>
      <span>Adventurer</span>
      <span class="hidden md:block">Total XP</span>
      <span class="hidden md:block">Awards</span>
      <span class="hidden md:block">Quests</span>
      <span class="text-right">Action</span>
    </div>

    <div
      v-for="player in props.players"
      :key="player.id"
      role="button"
      tabindex="0"
      :class="[
        GRID,
        'px-4 md:px-6 py-3.5 border-b border-white/[0.03] last:border-b-0 cursor-pointer transition-colors hover:bg-amber-200/[0.03] focus:outline-none focus-visible:bg-amber-200/[0.05]',
        player.id === props.currentUserId ? 'bg-aether-primary/[0.04]' : '',
      ]"
      @click="select(player)"
      @keydown.enter.self.prevent="select(player)"
      @keydown.space.self.prevent="select(player)"
    >
      <span :class="['w-9 h-9 md:w-10 md:h-10 rounded-xl border flex items-center justify-center text-sm font-black', badgeFor(player).badge]">
        <component :is="badgeFor(player).icon" v-if="badgeFor(player).icon" class="w-4 h-4" />
        <template v-else>{{ player.rank }}</template>
      </span>

      <div class="flex items-center gap-3 min-w-0">
        <button type="button" class="rounded-full shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-300/60" @click.stop="select(player)">
          <PlayerAvatar :username="player.username" :image-url="player.profile_image_url" size-class="w-10 h-10 text-base" />
        </button>
        <div class="min-w-0">
          <div class="flex items-center gap-2 min-w-0">
            <button
              type="button"
              class="font-fantasy font-bold text-[15px] text-slate-100 hover:text-amber-200 transition-colors truncate"
              @click.stop="select(player)"
            >
              {{ player.username }}
            </button>
            <span
              v-if="player.id === props.currentUserId"
              class="shrink-0 text-[9px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded-md bg-aether-primary/15 text-aether-primary border border-aether-primary/30"
            >You</span>
          </div>
          <p class="md:hidden mt-0.5 text-[11px] text-slate-500">
            {{ formatNumber(player.total_xp) }} XP · {{ player.total_awards }} awards · {{ player.completed_quests }}/{{ player.failed_quests }} quests
          </p>
        </div>
      </div>

      <span class="hidden md:flex">
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-aether-primary/10 border border-aether-primary/25 text-aether-primary text-xs font-black shadow-ambient-emerald">
          <Zap class="w-3.5 h-3.5" />
          {{ formatNumber(player.total_xp) }}
        </span>
      </span>

      <span class="hidden md:flex">
        <button
          type="button"
          class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-400/10 border border-amber-300/25 text-amber-200 text-xs font-black hover:bg-amber-400/20 transition-colors"
          :title="`View awards of ${player.username}`"
          @click.stop="select(player)"
        >
          <Trophy class="w-3.5 h-3.5" />
          {{ player.total_awards }}
        </button>
      </span>

      <span class="hidden md:flex items-center gap-2">
        <span class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-emerald-500/10 border border-emerald-400/25 text-emerald-300 text-xs font-bold" title="Completed quests">
          <CircleCheck class="w-3.5 h-3.5" />
          {{ player.completed_quests }}
        </span>
        <span class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-rose-500/10 border border-rose-400/25 text-rose-300 text-xs font-bold" title="Failed quests">
          <CircleX class="w-3.5 h-3.5" />
          {{ player.failed_quests }}
        </span>
      </span>

      <button
        type="button"
        class="justify-self-end inline-flex items-center gap-1 px-3 py-1.5 rounded-xl border border-white/10 bg-white/5 text-[10px] font-black uppercase tracking-widest text-slate-300 hover:text-white hover:border-amber-300/40 hover:bg-amber-300/10 transition-all"
        @click.stop="select(player)"
      >
        <span class="hidden sm:inline">View Awards</span>
        <ChevronRight class="w-3.5 h-3.5" />
      </button>
    </div>
  </div>
</template>
