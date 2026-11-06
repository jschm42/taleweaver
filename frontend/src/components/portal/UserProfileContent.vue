<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/composables/useApi'
import { authState } from '@/store/auth'
import AwardTile from './AwardTile.vue'
import ProfileAccountPanel from './profile/ProfileAccountPanel.vue'
import ProfileHero, { type ProfileStats } from './profile/ProfileHero.vue'
import ProfileSessionList from './profile/ProfileSessionList.vue'
import { useProfileSessions } from './profile/useProfileSessions'

type ProfileTab = 'adventures' | 'trophies' | 'account'
type Notification = { id: number, message: string, type: 'success' | 'error' }

const TABS: Array<{ key: ProfileTab, label: string, icon: string }> = [
  { key: 'adventures', label: 'Adventures', icon: 'ra ra-scroll-unfurled' },
  { key: 'trophies', label: 'Trophies', icon: 'ra ra-trophy' },
  { key: 'account', label: 'Account', icon: 'ra ra-shield' },
]

const activeTab = ref<ProfileTab>('adventures')
const sessions = useProfileSessions()
const canGenerateAvatar = ref(false)
const notifications = ref<Notification[]>([])

const earnedAwards = computed(() => (authState.user?.earned_awards || []) as any[])

const stats = computed<ProfileStats>(() => ({
  adventures: authState.user?.adventure_count ?? 0,
  victories: sessions.totals.value.completed,
  defeats: sessions.totals.value.game_over,
  totalXp: authState.user?.total_xp ?? 0,
  awards: earnedAwards.value.length,
}))

const tabBadges = computed<Record<ProfileTab, number | null>>(() => ({
  adventures: sessions.totals.value.all,
  trophies: earnedAwards.value.length,
  account: null,
}))

async function checkAvatarGeneration(): Promise<void> {
  try {
    const settings = await api.getSettings()
    canGenerateAvatar.value = Boolean((settings?.t2i_settings as { simple_model?: string } | undefined)?.simple_model)
  } catch {
    canGenerateAvatar.value = false
  }
}

function notify(message: string, type: 'success' | 'error'): void {
  const id = Date.now() + Math.random()
  notifications.value.push({ id, message, type })
  setTimeout(() => {
    notifications.value = notifications.value.filter(n => n.id !== id)
  }, 5000)
}

onMounted(() => {
  void sessions.reload()
  void checkAvatarGeneration()
})
</script>

<template>
  <div class="mx-auto grid w-full max-w-7xl gap-6 pb-10 lg:grid-cols-[minmax(260px,300px)_minmax(0,1fr)] lg:items-start">
    <aside class="lg:sticky lg:top-4">
      <ProfileHero :stats="stats" :can-generate-avatar="canGenerateAvatar" @notify="notify" />
    </aside>

    <div class="min-w-0 space-y-5">
      <nav class="flex gap-1 overflow-x-auto rounded-2xl border border-white/10 bg-white/[0.03] p-1" role="tablist" aria-label="Profile sections">
        <button
          v-for="tab in TABS"
          :key="tab.key"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab.key"
          class="flex flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-xl px-4 py-2.5 text-xs font-black uppercase tracking-widest transition-all"
          :class="activeTab === tab.key ? 'bg-aether-primary/15 text-aether-primary shadow-glass' : 'text-slate-500 hover:text-white'"
          @click="activeTab = tab.key"
        >
          <i :class="tab.icon"></i>{{ tab.label }}
          <span v-if="tabBadges[tab.key] !== null" class="rounded-full bg-black/30 px-1.5 text-[10px] tabular-nums">{{ tabBadges[tab.key] }}</span>
        </button>
      </nav>

      <!-- v-show keeps the loaded pages, filters and scroll position while switching tabs. -->
      <ProfileSessionList v-show="activeTab === 'adventures'" :state="sessions" />

      <section v-if="activeTab === 'trophies'">
        <div v-if="!earnedAwards.length" class="rounded-2xl border border-dashed border-white/10 py-14 text-center">
          <i class="ra ra-trophy mb-3 block text-4xl text-white/10"></i>
          <p class="text-sm text-slate-400">Your trophy room is empty. Earn awards by completing heroic deeds!</p>
        </div>
        <div v-else class="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
          <AwardTile v-for="award in earnedAwards" :key="(award.earned_at || '') + award.key" :award="award" />
        </div>
      </section>

      <ProfileAccountPanel v-if="activeTab === 'account'" @notify="notify" />
    </div>

    <Teleport to="body">
      <div class="pointer-events-none fixed bottom-6 right-4 z-[100] flex flex-col gap-3 sm:right-8" aria-live="polite">
        <TransitionGroup name="profile-toast">
          <div
            v-for="n in notifications"
            :key="n.id"
            class="pointer-events-auto flex min-w-[260px] max-w-sm items-center gap-3 rounded-2xl border px-4 py-3 text-xs font-bold shadow-2xl backdrop-blur-xl"
            :class="n.type === 'error' ? 'border-red-500/20 bg-red-500/10 text-red-300' : 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300'"
          >
            <span class="flex-1">{{ n.message }}</span>
            <button type="button" class="opacity-60 hover:opacity-100" aria-label="Dismiss" @click="notifications = notifications.filter(x => x.id !== n.id)">
              <i class="ra ra-cancel"></i>
            </button>
          </div>
        </TransitionGroup>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.profile-toast-enter-active,
.profile-toast-leave-active {
  transition: all 0.25s ease;
}
.profile-toast-enter-from,
.profile-toast-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
