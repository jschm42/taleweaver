<script setup lang="ts">
/**
 * One recently played session in the "Continue your journey" row: the full 2:3 cover next to
 * the session's progress, tinted by the cover's own colors. `wide` is the single-session layout.
 */
import { computed } from 'vue'
import { Play } from 'lucide-vue-next'
import type { GameSession } from '@/types'
import ProgressRing from './ProgressRing.vue'
import { resolveGenreAccent, toneToLabel } from '@/composables/useGenreAccent'
import { formatRelative } from '@/utils/relativeTime'
import { sessionTemplateId } from './heroSession'

const props = defineProps<{
  session: GameSession
  teaser?: string
  wide?: boolean
  isStartingSession?: boolean
}>()

const emit = defineEmits<{
  (e: 'resume', gameId: string): void
  (e: 'start-session', templateId: string): void
}>()

const accent = computed(() => resolveGenreAccent(toneToLabel(props.session.selected_tone)))
const templateId = computed(() => sessionTemplateId(props.session))
const teaserText = computed(() => (props.teaser || '').replace(/\\n/g, '\n'))
</script>

<template>
  <article
    class="tale-enter relative overflow-hidden rounded-2xl"
    :style="{ '--accent-rgb': accent.rgb, boxShadow: `0 0 0 1px rgb(251 191 36 / 0.16), 0 24px 48px -28px rgb(${accent.rgb} / 0.5)` }"
  >
    <div class="absolute inset-0 bg-[#050b14]"></div>
    <img v-if="session.image_url" :src="session.image_url" alt="" aria-hidden="true" class="hero-ambient absolute inset-0 h-full w-full object-cover" />
    <div class="absolute inset-0" :style="{ background: `radial-gradient(ellipse at 100% 100%, rgb(${accent.rgb} / 0.18), transparent 60%)` }"></div>
    <div class="tale-card__frame absolute inset-0"><div class="tale-card__frame-bl"></div></div>

    <div class="relative z-10 flex gap-4 p-4" :class="wide ? 'sm:gap-6 sm:p-5' : ''">
      <div
        class="continue-cover relative aspect-[2/3] shrink-0 overflow-hidden rounded-lg"
        :class="wide ? 'w-28 sm:w-40' : 'w-28 sm:w-32'"
      >
        <img v-if="session.image_url" :src="session.image_url" :alt="`Cover of ${session.adventure_title}`" class="h-full w-full object-cover" />
        <div v-else class="flex h-full w-full items-center justify-center bg-white/5 text-slate-500">
          <i class="ra ra-book text-3xl"></i>
        </div>
      </div>

      <div class="flex min-w-0 flex-1 flex-col gap-2">
        <h3 class="tale-title line-clamp-2 text-lg leading-tight text-white" :class="wide ? 'sm:text-3xl' : 'sm:text-xl'">
          {{ session.adventure_title }}
        </h3>

        <div class="flex flex-col gap-1 text-xs text-slate-300">
          <span v-if="session.current_scene_name" class="flex min-w-0 items-center gap-1.5">
            <i class="ra ra-compass text-slate-400"></i><span class="truncate">{{ session.current_scene_name }}</span>
          </span>
          <span class="flex items-center gap-1.5">
            <i class="ra ra-hourglass text-slate-400"></i>Played {{ formatRelative(session.last_played_at || session.created_at) }}
          </span>
          <span v-if="session.quest_count || session.award_count" class="flex items-center gap-3">
            <span v-if="session.quest_count" class="flex items-center gap-1.5">
              <i class="ra ra-scroll-unfurled text-slate-400"></i>{{ session.completed_quest_count || 0 }}/{{ session.quest_count }} quests
            </span>
            <span v-if="session.award_count" class="flex items-center gap-1.5">
              <i class="ra ra-trophy text-amber-300"></i>{{ session.earned_award_count || 0 }}/{{ session.award_count }}
            </span>
          </span>
        </div>

        <p v-if="wide && teaserText" class="hidden font-narrative text-sm leading-relaxed text-slate-300 line-clamp-2 whitespace-pre-wrap sm:block">
          {{ teaserText }}
        </p>

        <div class="mt-auto flex items-center gap-2 pt-1">
          <ProgressRing :value="session.progress || 0" :size="34" />
          <button
            type="button"
            class="tale-action tale-action--solid flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold uppercase tracking-wider transition-all sm:text-sm"
            :disabled="isStartingSession"
            @click="emit('resume', session.game_id)"
          >
            <Play class="h-4 w-4 fill-current" />Continue
          </button>
          <button
            v-if="templateId"
            type="button"
            class="flex h-9 w-9 items-center justify-center rounded-xl border border-white/15 bg-white/5 text-slate-300 transition-all hover:bg-white/10 hover:text-white disabled:opacity-50"
            :disabled="isStartingSession"
            :title="`New journey in ${session.adventure_title}`"
            :aria-label="`New journey in ${session.adventure_title}`"
            @click="emit('start-session', templateId)"
          >
            <i class="ra ra-quill-ink"></i>
          </button>
        </div>
      </div>
    </div>
  </article>
</template>
