<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { AdventureTemplateSummary } from '@/types'
import { Loader2, BookOpen } from 'lucide-vue-next'
import PortalForgeRow from './PortalForgeRow.vue'
import { setAmbientAccent } from '@/store/portalAmbient'
import { lastPlayedMs } from '@/utils/relativeTime'
import PendingAdventureCard from './PendingAdventureCard.vue'
import AdventureTemplateCard from './AdventureTemplateCard.vue'

const props = defineProps<{
  visibleTemplates: AdventureTemplateSummary[]
  pendingCards: any[]
  isSeeding: boolean
  loadingWordIndex: number
  isStartingSession?: boolean
  startingSessionTemplateId?: string | null
  updatingTemplateIds?: Set<string>
  hasMore?: boolean
  totalFilteredCount?: number
}>()

const emit = defineEmits<{
  (e: 'create'): void
  (e: 'generate-world'): void
  (e: 'open-library'): void
  (e: 'remove-failed-pending', adventureId: string, kind: 'creation' | 'import'): void
  (e: 'cancel-pending', adventureId: string): void
  (e: 'start-session', templateId: string): void
  (e: 'resume-session', gameId: string): void
  (e: 'update-adventure', templateId: string): void
  (e: 'migrate', template: any): void
  (e: 'cover', templateId: string): void
  (e: 'edit', templateId: string): void
  (e: 'duplicate', templateId: string): void
  (e: 'export-adz', templateId: string, title: string): void
  (e: 'export-adv', templateId: string, title: string): void
  (e: 'delete', templateId: string, title: string): void
  (e: 'dismiss-warning', templateId: string): void
  (e: 'click-pending', pending: any): void
  (e: 'load-more'): void
}>()

/**
 * One card per adventure that has actually been played; it continues the adventure's most
 * recently played session (the backend resolves active_game_id to that session).
 * The archive below always lists every adventure, played or not.
 */
const inProgressTemplates = computed(() =>
  props.visibleTemplates
    .filter((t) => t.has_active_session && t.last_played_at)
    .sort((a, b) => lastPlayedMs(b) - lastPlayedMs(a))
)

const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null
let scrollContainer: HTMLElement | null = null

function handleScroll() {
  if (!scrollContainer) return
  if (scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight < 400) {
    emit('load-more')
  }
}

onMounted(() => {
  if (sentinelRef.value) {
    scrollContainer = sentinelRef.value.closest('.overflow-y-auto') as HTMLElement | null
    if (scrollContainer) {
      scrollContainer.addEventListener('scroll', handleScroll, { passive: true })
    }
    observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          emit('load-more')
        }
      },
      { root: scrollContainer, rootMargin: '400px' }
    )
    observer.observe(sentinelRef.value)
  }
})

onUnmounted(() => {
  setAmbientAccent(null)
  if (scrollContainer) {
    scrollContainer.removeEventListener('scroll', handleScroll)
  }
  if (observer) {
    observer.disconnect()
    observer = null
  }
})
</script>

<template>
  <div class="space-y-8 sm:space-y-10">
    <PortalForgeRow
      :is-seeding="isSeeding"
      @create="$emit('create')"
      @generate-world="$emit('generate-world')"
      @open-library="$emit('open-library')"
    />

    <!-- Shelf: adventures with a running session -->
    <section v-if="inProgressTemplates.length > 0" class="space-y-3" aria-label="In progress">
      <h2 class="shelf-heading text-xs sm:text-sm uppercase">In Progress</h2>
      <div class="shelf-grid gap-3 sm:gap-4 xl:gap-5 pt-2">
        <div
          v-for="(entry, index) in inProgressTemplates"
          :key="`active-${entry.template_id}`"
          class="tale-enter"
          :style="{ '--i': index }"
        >
          <AdventureTemplateCard
            :template="entry"
            resumable
            :is-starting-session="isStartingSession"
            :is-starting-this-template="startingSessionTemplateId === entry.template_id"
            :is-updating="props.updatingTemplateIds ? props.updatingTemplateIds.has(entry.template_id) : false"
            @start-session="(id) => $emit('start-session', id)"
            @resume-session="(id) => $emit('resume-session', id)"
            @update-adventure="(id) => $emit('update-adventure', id)"
            @migrate="(tpl) => $emit('migrate', tpl)"
            @cover="(id) => $emit('cover', id)"
            @edit="(id) => $emit('edit', id)"
            @duplicate="(id) => $emit('duplicate', id)"
            @export-adz="(id, title) => $emit('export-adz', id, title)"
            @export-adv="(id, title) => $emit('export-adv', id, title)"
            @delete="(id, title) => $emit('delete', id, title)"
            @dismiss-warning="(id) => $emit('dismiss-warning', id)"
          />
        </div>
      </div>
    </section>

    <!-- Shelf: every adventure, including those in progress -->
    <section class="space-y-3" aria-label="The archive">
      <h2 class="shelf-heading text-xs sm:text-sm uppercase">The Archive</h2>
      <div class="shelf-grid gap-3 sm:gap-4 xl:gap-5 pt-2">
        <div v-if="isSeeding" class="flex flex-col items-center justify-center rounded-2xl border border-dashed border-amber-300/20 bg-white/5 gap-3 aspect-[3/4]">
          <div class="w-8 h-8 border-2 border-aether-primary/10 border-t-aether-primary rounded-full animate-spin"></div>
          <span class="text-xxs text-aether-primary uppercase tracking-widest font-bold">Importing Tales...</span>
        </div>

        <PendingAdventureCard
          v-for="pending in pendingCards"
          :key="`pending-${pending.adventureId}`"
          :pending="pending"
          :loading-word-index="loadingWordIndex"
          @remove-failed="(id, kind) => $emit('remove-failed-pending', id, kind)"
          @cancel="(id) => $emit('cancel-pending', id)"
          @click="$emit('click-pending', pending)"
        />

        <div
          v-for="(entry, index) in props.visibleTemplates"
          :key="entry.template_id"
          class="tale-enter"
          :style="{ '--i': index }"
        >
          <AdventureTemplateCard
            :template="entry"
            :is-starting-session="isStartingSession"
            :is-starting-this-template="startingSessionTemplateId === entry.template_id"
            :is-updating="props.updatingTemplateIds ? props.updatingTemplateIds.has(entry.template_id) : false"
            @start-session="(id) => $emit('start-session', id)"
            @resume-session="(id) => $emit('resume-session', id)"
            @update-adventure="(id) => $emit('update-adventure', id)"
            @migrate="(tpl) => $emit('migrate', tpl)"
            @cover="(id) => $emit('cover', id)"
            @edit="(id) => $emit('edit', id)"
            @duplicate="(id) => $emit('duplicate', id)"
            @export-adz="(id, title) => $emit('export-adz', id, title)"
            @export-adv="(id, title) => $emit('export-adv', id, title)"
            @delete="(id, title) => $emit('delete', id, title)"
            @dismiss-warning="(id) => $emit('dismiss-warning', id)"
          />
        </div>
      </div>
    </section>

    <!-- Empty filtered state notice if no templates match filters -->
    <div
      v-if="props.visibleTemplates.length === 0 && props.pendingCards.length === 0"
      class="rounded-xl border border-white/10 bg-aether-surface/20 p-8 text-center flex flex-col items-center gap-3"
    >
      <BookOpen class="w-8 h-8 text-slate-500" />
      <p class="text-xs sm:text-sm text-slate-400">
        No adventures match your selected filter criteria.
      </p>
    </div>

    <!-- Infinite Scroll Sentinel & Loader -->
    <div ref="sentinelRef" class="py-6 flex items-center justify-center">
      <div v-if="props.hasMore" class="flex items-center gap-2 text-xs text-slate-400 bg-black/40 px-4 py-2 rounded-xl border border-white/10">
        <Loader2 class="w-4 h-4 animate-spin text-aether-primary" />
        <span>Loading more adventures (showing {{ props.visibleTemplates.length }} of {{ props.totalFilteredCount }})...</span>
      </div>
      <div v-else-if="props.visibleTemplates.length > 12" class="text-xs text-slate-500">
        All {{ props.visibleTemplates.length }} adventures loaded
      </div>
    </div>
  </div>
</template>
