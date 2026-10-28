<script setup lang="ts">
import { computed } from 'vue'
import type { AdventureTemplateSummary, GameSession } from '@/types'
import { Play } from 'lucide-vue-next'
import ProgressRing from './ProgressRing.vue'
import { resolveGenreAccent, toneToLabel } from '@/composables/useGenreAccent'
import { formatRelative, lastPlayedMs } from '@/utils/relativeTime'

const props = defineProps<{
  sessions: GameSession[]
  templates: AdventureTemplateSummary[]
  isStartingSession?: boolean
}>()

const emit = defineEmits<{
  (e: 'resume', gameId: string): void
  (e: 'start-session', templateId: string): void
}>()

interface HeroModel {
  title: string
  imageUrl: string | null
  toneLabel: string
  teaser: string
  templateId: string | null
  session: GameSession | null
}

/** The playable session the player opened most recently. */
const resumable = computed(() => {
  const playable = props.sessions.filter((s) => s.is_ready && (!s.status || s.status === 'active'))
  if (playable.length === 0) return null
  return playable.reduce((latest, s) => (lastPlayedMs(s) > lastPlayedMs(latest) ? s : latest))
})

/** Fallback when nothing is in progress: the first playable adventure with cover art. */
const featured = computed(() =>
  props.templates.find((t) => t.image_url && t.can_start !== false && !t.is_legacy_format) || null
)

const hero = computed<HeroModel | null>(() => {
  const session = resumable.value
  if (session) {
    const template = props.templates.find((t) => t.template_id === (session.template_id || session.adventure_id))
    return {
      title: session.adventure_title,
      imageUrl: session.image_url,
      toneLabel: toneToLabel(session.selected_tone),
      teaser: template?.teaser || '',
      templateId: template?.template_id || null,
      session,
    }
  }
  const tpl = featured.value
  if (!tpl) return null
  return {
    title: tpl.title,
    imageUrl: tpl.image_url,
    toneLabel: toneToLabel(tpl.selected_tone),
    teaser: tpl.teaser || '',
    templateId: tpl.template_id,
    session: null,
  }
})

const accent = computed(() => resolveGenreAccent(hero.value?.toneLabel))
const teaser = computed(() => (hero.value?.teaser || '').replace(/\\n/g, '\n'))
</script>

<template>
  <section
    v-if="hero"
    class="tale-enter relative overflow-hidden rounded-3xl min-h-[180px] sm:min-h-[220px] lg:min-h-[250px] flex items-end"
    :style="{ '--accent-rgb': accent.rgb, boxShadow: `0 0 0 1px rgb(251 191 36 / 0.16), 0 30px 60px -30px rgb(${accent.rgb} / 0.45)` }"
  >
    <div class="absolute inset-0 bg-[#050b14]"></div>
    <template v-if="hero.imageUrl">
      <img :src="hero.imageUrl" alt="" aria-hidden="true" class="hero-ambient absolute inset-0 w-full h-full object-cover" />
      <div class="hero-cover absolute inset-y-0 right-0 w-[70%] sm:w-[55%] lg:w-[42%] overflow-hidden">
        <img :src="hero.imageUrl" alt="" class="hero-kenburns absolute inset-0 w-full h-full object-cover object-[center_30%]" />
      </div>
    </template>
    <div
      class="absolute inset-0"
      :style="{ background: `radial-gradient(ellipse at 0% 100%, rgb(${accent.rgb} / 0.22), transparent 55%)` }"
    ></div>
    <div class="absolute inset-0 bg-gradient-to-t from-[#050b14]/90 via-transparent to-transparent"></div>
    <div class="tale-card__frame absolute inset-0"><div class="tale-card__frame-bl"></div></div>

    <div class="relative z-10 p-4 sm:p-6 lg:p-7 max-w-2xl space-y-2 sm:space-y-3">
      <p class="tale-accent-text tale-legible text-[11px] sm:text-xs font-bold uppercase tracking-[0.25em]">
        <i :class="['ra', hero.session ? 'ra-hourglass' : 'ra-castle-emblem']" class="mr-1.5"></i>
        {{ hero.session ? 'Continue your journey' : 'Featured tale' }}
      </p>

      <h2 class="tale-title text-xl sm:text-3xl lg:text-4xl text-white leading-tight">{{ hero.title }}</h2>

      <div v-if="hero.session" class="flex flex-wrap items-center gap-3 sm:gap-5 text-xs text-slate-300">
        <ProgressRing :value="hero.session.progress || 0" :size="36" />
        <span class="flex items-center gap-1.5">
          <i class="ra ra-hourglass text-slate-400"></i>Played {{ formatRelative(hero.session.last_played_at || hero.session.created_at) }}
        </span>
        <span v-if="hero.session.current_scene_name" class="flex items-center gap-1.5">
          <i class="ra ra-compass text-slate-400"></i>{{ hero.session.current_scene_name }}
        </span>
        <span v-if="hero.session.quest_count" class="flex items-center gap-1.5">
          <i class="ra ra-scroll-unfurled text-slate-400"></i>{{ hero.session.completed_quest_count || 0 }}/{{ hero.session.quest_count }} quests
        </span>
        <span v-if="hero.session.award_count" class="flex items-center gap-1.5">
          <i class="ra ra-trophy text-amber-300"></i>{{ hero.session.earned_award_count || 0 }}/{{ hero.session.award_count }}
        </span>
      </div>

      <p v-else-if="teaser" class="font-narrative text-sm sm:text-base text-slate-300 leading-relaxed line-clamp-2 whitespace-pre-wrap">{{ teaser }}</p>

      <div class="flex flex-wrap gap-2.5 pt-1">
        <button
          v-if="hero.session"
          class="tale-action px-4 sm:px-6 py-2 sm:py-2.5 rounded-xl text-xs sm:text-sm font-bold uppercase tracking-wider flex items-center gap-2 transition-all"
          :disabled="props.isStartingSession"
          @click="emit('resume', hero.session.game_id)"
        >
          <Play class="w-4 h-4 fill-current" />Continue
        </button>
        <button
          v-if="hero.templateId"
          class="px-4 sm:px-6 py-2 sm:py-2.5 rounded-xl text-xs sm:text-sm font-bold uppercase tracking-wider flex items-center gap-2 transition-all disabled:opacity-50"
          :class="hero.session ? 'bg-white/5 border border-white/15 text-slate-200 hover:bg-white/10' : 'tale-action'"
          :disabled="props.isStartingSession"
          @click="emit('start-session', hero.templateId)"
        >
          <i class="ra ra-quill-ink"></i>{{ hero.session ? 'New journey' : 'Begin adventure' }}
        </button>
      </div>
    </div>
  </section>
</template>
