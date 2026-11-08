<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { X, Zap, Trophy, CircleCheck, CircleX, Scroll } from 'lucide-vue-next'
import type { EarnedAward, LeaderboardEntry } from '@/types'
import { api } from '@/composables/useApi'
import AwardTile from '@/components/portal/AwardTile.vue'
import PlayerAvatar from '@/components/portal/leaderboard/PlayerAvatar.vue'
import { formatNumber, rankTier } from '@/components/portal/leaderboard/leaderboardUtils'

const props = defineProps<{
  isOpen: boolean
  player: LeaderboardEntry | null
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

/** Fresh awards from the server; falls back to the leaderboard snapshot until loaded. */
const fetchedAwards = ref<EarnedAward[] | null>(null)
const isLoadingAwards = ref(false)

const RANK_BADGE: Record<string, string> = {
  gold: 'bg-amber-400/15 text-amber-300 border-amber-300/40',
  silver: 'bg-slate-300/10 text-slate-200 border-slate-300/30',
  bronze: 'bg-orange-500/10 text-orange-300 border-orange-400/30',
  plain: 'bg-white/5 text-slate-300 border-white/10',
}

const awards = computed<EarnedAward[]>(() => {
  const list = fetchedAwards.value ?? props.player?.earned_awards ?? []
  return [...list].sort((a, b) => (b.earned_at || '').localeCompare(a.earned_at || ''))
})

const rankBadgeClass = computed(() => RANK_BADGE[rankTier(props.player?.rank ?? 0)])

const statCards = computed(() => {
  const player = props.player
  if (!player) return []
  return [
    { label: 'Total XP', value: formatNumber(player.total_xp), icon: Zap, tone: 'text-aether-primary' },
    { label: 'Awards', value: formatNumber(player.total_awards), icon: Trophy, tone: 'text-amber-300' },
    { label: 'Completed', value: formatNumber(player.completed_quests), icon: CircleCheck, tone: 'text-emerald-300' },
    { label: 'Failed', value: formatNumber(player.failed_quests), icon: CircleX, tone: 'text-rose-300' },
    { label: 'Adventures', value: formatNumber(player.adventure_count), icon: Scroll, tone: 'text-sky-300' },
  ]
})

async function loadAwards(userId: string): Promise<void> {
  isLoadingAwards.value = true
  try {
    const result = await api.getPlayerAwards(userId)
    if (props.player?.id === userId) fetchedAwards.value = result
  } catch (error) {
    console.warn('Failed to refresh player awards', error)
  } finally {
    isLoadingAwards.value = false
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('close')
}

watch(
  () => [props.isOpen, props.player?.id] as const,
  ([isOpen, playerId]) => {
    fetchedAwards.value = null
    window.removeEventListener('keydown', onKeydown)
    if (!isOpen || !playerId) return
    window.addEventListener('keydown', onKeydown)
    void loadAwards(playerId)
  },
  { immediate: true },
)

onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="awards-modal">
      <div
        v-if="props.isOpen && props.player"
        class="fixed inset-0 z-[100] flex items-center justify-center p-3 sm:p-6 bg-slate-950/75 backdrop-blur-md"
        @click.self="emit('close')"
      >
        <div
          class="awards-panel relative w-full max-w-5xl max-h-[92vh] flex flex-col rounded-3xl border border-amber-200/10 bg-gradient-to-b from-[#0c1626] to-[#060d18] shadow-[0_40px_120px_-20px_rgba(0,0,0,0.8)] overflow-hidden"
          role="dialog"
          aria-modal="true"
          :aria-label="`Awards of ${props.player.username}`"
        >
          <div class="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-amber-300/80 to-transparent"></div>
          <div class="absolute inset-x-16 top-0 h-px bg-gradient-to-r from-transparent via-aether-primary/60 to-transparent blur-[1px]"></div>
          <div class="pointer-events-none absolute -top-32 left-1/2 -translate-x-1/2 w-[36rem] h-64 rounded-full bg-amber-400/10 blur-3xl"></div>

          <button
            type="button"
            class="absolute top-4 right-4 z-10 w-9 h-9 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:text-white hover:bg-white/10 transition-all flex items-center justify-center"
            aria-label="Close"
            @click="emit('close')"
          >
            <X class="w-4 h-4" />
          </button>

          <div class="relative overflow-y-auto p-6 sm:p-8 space-y-8">
            <header class="flex flex-col sm:flex-row items-center sm:items-start gap-5 text-center sm:text-left pr-0 sm:pr-10">
              <PlayerAvatar
                :username="props.player.username"
                :image-url="props.player.profile_image_url"
                size-class="w-24 h-24 text-4xl ring-2 ring-amber-300/40 ring-offset-4 ring-offset-[#0c1626]"
              />
              <div class="min-w-0 flex-1">
                <p class="text-[10px] font-black uppercase tracking-[0.35em] text-amber-300/80">Chronicle of</p>
                <div class="mt-1 flex flex-wrap items-center justify-center sm:justify-start gap-3">
                  <h2 class="font-fantasy text-3xl font-bold text-white truncate">{{ props.player.username }}</h2>
                  <span :class="['px-2.5 py-1 rounded-lg border text-xs font-black tracking-widest', rankBadgeClass]">
                    RANK #{{ props.player.rank }}
                  </span>
                </div>
                <p v-if="props.player.bio" class="mt-3 text-sm text-slate-400 leading-relaxed max-w-2xl whitespace-pre-line">
                  {{ props.player.bio }}
                </p>
              </div>
            </header>

            <section class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              <div
                v-for="card in statCards"
                :key="card.label"
                class="rounded-2xl border border-white/5 bg-white/[0.03] px-4 py-3 flex items-center gap-3"
              >
                <component :is="card.icon" :class="['w-5 h-5 shrink-0', card.tone]" />
                <div class="min-w-0">
                  <p class="text-[9px] font-bold uppercase tracking-widest text-slate-500">{{ card.label }}</p>
                  <p :class="['text-lg font-black leading-tight', card.tone]">{{ card.value }}</p>
                </div>
              </div>
            </section>

            <section>
              <div class="flex items-center gap-3 mb-4">
                <h3 class="font-fantasy text-lg font-bold text-amber-100">Trophy Hall</h3>
                <span class="text-xs font-bold text-slate-500">{{ awards.length }}</span>
                <div class="flex-1 h-px bg-gradient-to-r from-amber-200/20 to-transparent"></div>
                <span v-if="isLoadingAwards" class="w-4 h-4 border-2 border-amber-300/20 border-t-amber-300 rounded-full animate-spin"></span>
              </div>

              <div v-if="awards.length" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <AwardTile v-for="(award, index) in awards" :key="`${award.session_id}-${award.key}-${index}`" :award="award" />
              </div>
              <div v-else class="rounded-2xl border border-dashed border-white/10 py-14 px-6 flex flex-col items-center gap-3 text-center">
                <Trophy class="w-10 h-10 text-slate-600" />
                <p class="text-sm text-slate-400 max-w-sm">
                  No trophies earned yet. This adventurer has just begun their journey.
                </p>
              </div>
            </section>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.awards-modal-enter-active,
.awards-modal-leave-active {
  transition: opacity 0.25s ease;
}
.awards-modal-enter-active .awards-panel,
.awards-modal-leave-active .awards-panel {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.awards-modal-enter-from,
.awards-modal-leave-to {
  opacity: 0;
}
.awards-modal-enter-from .awards-panel,
.awards-modal-leave-to .awards-panel {
  transform: translateY(16px) scale(0.98);
}
</style>
