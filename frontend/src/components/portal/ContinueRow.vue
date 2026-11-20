<script setup lang="ts">
/**
 * Top of the library: the latest session of the three most recently played adventures side by
 * side (one card per adventure). Without a running session
 * it shows the featured adventure instead.
 */
import { computed } from 'vue'
import type { AdventureTemplateSummary, GameSession } from '@/types'
import ContinueCard from './ContinueCard.vue'
import PortalHeroBanner from './PortalHeroBanner.vue'
import { pickRecentSessions, playableSessions, sessionTemplateId } from './heroSession'

const MAX_CARDS = 3

const props = defineProps<{
  sessions: GameSession[]
  templates: AdventureTemplateSummary[]
  isStartingSession?: boolean
}>()

const emit = defineEmits<{
  (e: 'resume', gameId: string): void
  (e: 'start-session', templateId: string): void
  (e: 'show-sessions'): void
}>()

const recent = computed(() => pickRecentSessions(props.sessions, MAX_CARDS))
const playableCount = computed(() => playableSessions(props.sessions).length)

const gridClass = computed(() => {
  if (recent.value.length === 1) return 'grid-cols-1'
  if (recent.value.length === 2) return 'grid-cols-1 md:grid-cols-2'
  return 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3'
})

function teaserOf(session: GameSession): string {
  const id = sessionTemplateId(session)
  return props.templates.find((t) => t.template_id === id)?.teaser || ''
}
</script>

<template>
  <section v-if="recent.length" class="space-y-3" aria-labelledby="continue-heading">
    <div class="flex items-center gap-4">
      <h2 id="continue-heading" class="shelf-heading flex-1 text-xs uppercase sm:text-sm">Continue your journey</h2>
      <button
        v-if="playableCount > recent.length"
        type="button"
        class="shrink-0 text-xs font-bold text-amber-300/80 transition-colors hover:text-amber-200"
        @click="emit('show-sessions')"
      >
        All {{ playableCount }} sessions →
      </button>
    </div>
    <div class="grid gap-3 sm:gap-4" :class="gridClass">
      <ContinueCard
        v-for="(session, index) in recent"
        :key="session.game_id"
        :style="{ '--i': index }"
        :session="session"
        :teaser="teaserOf(session)"
        :wide="recent.length === 1"
        :is-starting-session="isStartingSession"
        @resume="(id) => emit('resume', id)"
        @start-session="(id) => emit('start-session', id)"
      />
    </div>
  </section>
  <PortalHeroBanner
    v-else
    :templates="templates"
    :is-starting-session="isStartingSession"
    @start-session="(id) => emit('start-session', id)"
  />
</template>
