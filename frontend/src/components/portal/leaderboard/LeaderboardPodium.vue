<script setup lang="ts">
import { computed, type Component } from 'vue'
import { Crown, Medal, Shield } from 'lucide-vue-next'
import type { LeaderboardEntry } from '@/types'
import PlayerAvatar from './PlayerAvatar.vue'
import { formatNumber, rankTier, type RankTier } from './leaderboardUtils'

const props = defineProps<{
  players: LeaderboardEntry[]
  currentUserId?: string | null
}>()

const emit = defineEmits<{ (e: 'select', player: LeaderboardEntry): void }>()

interface TierStyle {
  icon: Component
  title: string
  card: string
  ring: string
  text: string
  plinth: string
  order: string
  avatar: string
}

const TIER_STYLES: Record<Exclude<RankTier, 'plain'>, TierStyle> = {
  gold: {
    icon: Crown,
    title: 'Champion',
    card: 'border-amber-300/40 bg-gradient-to-b from-amber-400/15 via-amber-900/10 to-transparent shadow-[0_0_60px_-10px_rgba(251,191,36,0.45)] md:-translate-y-6',
    ring: 'ring-amber-300/70 shadow-[0_0_30px_rgba(251,191,36,0.5)]',
    text: 'text-amber-300',
    plinth: 'h-4 bg-gradient-to-r from-amber-500/0 via-amber-300/70 to-amber-500/0',
    order: 'order-1 md:order-2',
    avatar: 'w-24 h-24 text-4xl',
  },
  silver: {
    icon: Medal,
    title: 'Paragon',
    card: 'border-slate-300/30 bg-gradient-to-b from-slate-300/10 via-slate-800/10 to-transparent shadow-[0_0_40px_-12px_rgba(203,213,225,0.35)]',
    ring: 'ring-slate-300/60 shadow-[0_0_20px_rgba(203,213,225,0.35)]',
    text: 'text-slate-200',
    plinth: 'h-3 bg-gradient-to-r from-slate-400/0 via-slate-300/60 to-slate-400/0',
    order: 'order-2 md:order-1',
    avatar: 'w-20 h-20 text-3xl',
  },
  bronze: {
    icon: Shield,
    title: 'Vanguard',
    card: 'border-orange-400/30 bg-gradient-to-b from-orange-500/10 via-orange-950/10 to-transparent shadow-[0_0_40px_-12px_rgba(234,88,12,0.35)]',
    ring: 'ring-orange-400/60 shadow-[0_0_20px_rgba(234,88,12,0.35)]',
    text: 'text-orange-300',
    plinth: 'h-2 bg-gradient-to-r from-orange-500/0 via-orange-400/60 to-orange-500/0',
    order: 'order-3',
    avatar: 'w-20 h-20 text-3xl',
  },
}

const podium = computed(() =>
  props.players
    .filter((player) => player.rank <= 3)
    .sort((a, b) => a.rank - b.rank)
    .map((player) => ({ player, style: TIER_STYLES[rankTier(player.rank) as Exclude<RankTier, 'plain'>] })),
)
</script>

<template>
  <section v-if="podium.length" class="grid grid-cols-1 md:grid-cols-3 gap-5 md:gap-6 items-end pt-4 md:pt-10">
    <article
      v-for="{ player, style } in podium"
      :key="player.id"
      :class="['relative rounded-3xl border backdrop-blur-xl px-6 pt-10 pb-6 flex flex-col items-center text-center transition-all duration-500 hover:-translate-y-1', style.card, style.order]"
    >
      <div :class="['absolute -top-5 left-1/2 -translate-x-1/2 w-10 h-10 rounded-full bg-aether-background border border-white/10 flex items-center justify-center', style.text]">
        <component :is="style.icon" class="w-5 h-5" />
      </div>

      <button
        type="button"
        class="rounded-full ring-2 ring-offset-4 ring-offset-aether-background transition-transform hover:scale-105 focus:outline-none focus-visible:ring-4"
        :class="style.ring"
        :aria-label="`View awards of ${player.username}`"
        @click="emit('select', player)"
      >
        <PlayerAvatar :username="player.username" :image-url="player.profile_image_url" :size-class="style.avatar" />
      </button>

      <p :class="['mt-5 text-[10px] font-black uppercase tracking-[0.35em]', style.text]">#{{ player.rank }} · {{ style.title }}</p>
      <button
        type="button"
        class="mt-1 font-fantasy text-xl font-bold text-white hover:text-amber-200 transition-colors truncate max-w-full"
        @click="emit('select', player)"
      >
        {{ player.username }}
      </button>
      <span
        v-if="player.id === props.currentUserId"
        class="mt-1 text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full bg-aether-primary/15 text-aether-primary border border-aether-primary/30"
      >You</span>

      <dl class="mt-5 grid grid-cols-3 gap-2 w-full">
        <div class="rounded-xl bg-black/20 border border-white/5 py-2">
          <dt class="text-[9px] font-bold uppercase tracking-widest text-slate-500">XP</dt>
          <dd :class="['text-sm font-black', style.text]">{{ formatNumber(player.total_xp) }}</dd>
        </div>
        <div class="rounded-xl bg-black/20 border border-white/5 py-2">
          <dt class="text-[9px] font-bold uppercase tracking-widest text-slate-500">Awards</dt>
          <dd class="text-sm font-black text-aether-secondary">{{ player.total_awards }}</dd>
        </div>
        <div class="rounded-xl bg-black/20 border border-white/5 py-2">
          <dt class="text-[9px] font-bold uppercase tracking-widest text-slate-500">Quests</dt>
          <dd class="text-sm font-black text-emerald-300">{{ player.completed_quests }}</dd>
        </div>
      </dl>

      <div :class="['absolute bottom-0 left-6 right-6 rounded-t-full blur-[2px]', style.plinth]"></div>
    </article>
  </section>
</template>
