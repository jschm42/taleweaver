<script setup lang="ts">
/**
 * AdventureEndingCard — the win / game-over card, shown inline in the story feed.
 *
 * Rendered from the `adventure_ending` chat message the server stores after the terminal
 * epilogue, so it keeps its place in the story. Built like the ChapterBanner (same width and
 * --tw-overlay-* skin tokens) with an outcome tint: gold for a win, ember red for a loss.
 * After a win the player can keep playing below the card; after a loss the input is locked
 * and the card offers to load a save.
 */
import { computed } from 'vue'
import { Crown, Skull, History, LogOut } from 'lucide-vue-next'

interface EndingPayload {
  outcome: 'won' | 'lost'
  reason?: string
  adventure_title?: string
  exp?: number
  quests_completed?: number
  quests_total?: number
  awards_earned?: number
  awards_total?: number
}

const props = defineProps<{
  /** JSON content of the `adventure_ending` message. */
  content: string
}>()

const emit = defineEmits<{
  backToMenu: []
  loadSave: []
}>()

const ending = computed<EndingPayload>(() => {
  try {
    const parsed = JSON.parse(props.content || '{}')
    return { ...parsed, outcome: parsed?.outcome === 'lost' ? 'lost' : 'won' }
  } catch {
    return { outcome: 'won' }
  }
})

const won = computed(() => ending.value.outcome === 'won')

const fallbackReason = computed(() =>
  won.value ? 'You saw this tale through to its end.' : 'Your journey has come to an end.'
)

/** Only tallies the adventure actually has (no "0 / 0 Awards"). */
const tallies = computed<string[]>(() => {
  const e = ending.value
  const parts = [`${(e.exp ?? 0).toLocaleString()} EXP`]
  if (e.quests_total) parts.push(`${e.quests_completed ?? 0} / ${e.quests_total} Quests`)
  if (e.awards_total) parts.push(`${e.awards_earned ?? 0} / ${e.awards_total} Awards`)
  return parts
})
</script>

<template>
  <section
    class="ending-card tw-overlay-band relative overflow-hidden shrink-0 self-start w-full max-w-2xl my-6 sm:my-8 rounded-2xl px-4 pt-8 pb-6 sm:pt-10 text-center"
    :class="won ? 'ending-card--won' : 'ending-card--lost'"
    role="status"
    :aria-label="won ? 'Adventure completed' : 'Game over'"
  >
    <div class="tw-overlay-wash absolute inset-0 pointer-events-none opacity-40"></div>
    <div class="tw-overlay-texture absolute inset-0 pointer-events-none"></div>
    <div class="ending-halo absolute left-1/2 top-16 w-72 h-72 -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl pointer-events-none"></div>

    <!-- Rising sparks (win) / drifting embers (loss) -->
    <div class="ending-sparks absolute inset-0 pointer-events-none" aria-hidden="true">
      <span v-for="n in 10" :key="n" class="ending-spark" :style="{ '--i': n }"></span>
    </div>

    <div class="relative z-10 flex flex-col items-center">
      <!-- Medallion -->
      <div class="ending-medallion relative w-20 h-20 sm:w-24 sm:h-24 mb-4" aria-hidden="true">
        <span class="ending-medallion-ring absolute inset-0 rounded-full"></span>
        <span class="ending-medallion-core absolute inset-[6px] rounded-full flex items-center justify-center">
          <Crown v-if="won" class="w-9 h-9 sm:w-11 sm:h-11" stroke-width="1.75" />
          <Skull v-else class="w-9 h-9 sm:w-11 sm:h-11" stroke-width="1.75" />
        </span>
      </div>

      <div class="flex items-center gap-3 mb-2">
        <span class="ending-rule w-8 sm:w-14 h-px"></span>
        <span class="ending-eyebrow tw-overlay-eyebrow text-[10px] sm:text-[11px] font-bold tracking-[0.35em] uppercase">
          {{ won ? 'The End' : 'Your Story Ends' }}
        </span>
        <span class="ending-rule w-8 sm:w-14 h-px"></span>
      </div>

      <h2 class="ending-title tw-overlay-title tw-overlay-title--chapter text-3xl sm:text-5xl font-black leading-none">
        {{ won ? 'Victory' : 'Game Over' }}
      </h2>
      <p v-if="ending.adventure_title" class="tw-overlay-muted text-[11px] sm:text-xs font-semibold tracking-[0.2em] uppercase mt-2">
        {{ ending.adventure_title }}
      </p>

      <div class="flex items-center justify-center gap-2 my-3.5 w-full">
        <span class="ending-rule w-14 sm:w-24 h-px"></span>
        <span class="ending-diamond w-1.5 h-1.5 rotate-45"></span>
        <span class="ending-rule w-14 sm:w-24 h-px"></span>
      </div>

      <p class="ending-reason text-sm sm:text-base font-serif italic max-w-lg leading-relaxed">
        {{ ending.reason || fallbackReason }}
      </p>

      <p class="ending-tally tw-overlay-muted mt-4 text-[11px] sm:text-xs font-bold tracking-[0.18em] uppercase flex flex-wrap justify-center gap-x-2 gap-y-1">
        <template v-for="(part, idx) in tallies" :key="part">
          <span v-if="idx > 0" aria-hidden="true" class="opacity-50">·</span>
          <span>{{ part }}</span>
        </template>
      </p>

      <div class="flex flex-wrap items-center justify-center gap-2 mt-6">
        <button
          v-if="!won"
          type="button"
          class="tw-prompt-action"
          @click="emit('loadSave')"
        >
          <History class="w-4 h-4" />
          <span>Load a Save</span>
        </button>
        <button
          type="button"
          class="tw-prompt-action tw-prompt-action--ghost"
          @click="emit('backToMenu')"
        >
          <LogOut class="w-4 h-4" />
          <span>Back to Menu</span>
        </button>
      </div>

      <p class="tw-overlay-muted mt-3 text-[11px] sm:text-xs">
        {{ won ? 'The world stays open: keep exploring as long as you like.' : 'The story is over. Load a save to try again.' }}
      </p>
    </div>
  </section>
</template>

<style scoped>
.ending-card {
  --ending-accent: var(--tw-overlay-highlight);
  border-inline: 1px solid color-mix(in srgb, var(--ending-accent) 30%, transparent);
  border-block-color: color-mix(in srgb, var(--ending-accent) 45%, transparent);
  animation: ending-in 1.1s cubic-bezier(0.16, 1, 0.3, 1) both;
}

.ending-card--lost {
  --ending-accent: #f87171;
}

.ending-halo {
  background: color-mix(in srgb, var(--ending-accent) 22%, transparent);
}

.ending-eyebrow {
  color: var(--ending-accent);
  text-shadow: 0 0 12px color-mix(in srgb, var(--ending-accent) 55%, transparent);
}

.ending-rule {
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--ending-accent) 75%, transparent), transparent);
}

.ending-diamond {
  background: var(--ending-accent);
  box-shadow: 0 0 10px var(--ending-accent);
}

.ending-title {
  letter-spacing: 0.08em;
  overflow-wrap: anywhere;
  text-shadow:
    0 0 28px color-mix(in srgb, var(--ending-accent) 45%, transparent),
    0 4px 22px rgba(0, 0, 0, 0.95);
}

.ending-reason {
  color: var(--tw-overlay-ink);
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.9);
}

/* Medallion: a slowly turning ring around the outcome emblem. */
.ending-medallion-ring {
  background: conic-gradient(
    from 0deg,
    var(--ending-accent),
    transparent 30%,
    color-mix(in srgb, var(--ending-accent) 60%, transparent) 50%,
    transparent 75%,
    var(--ending-accent)
  );
  animation: ending-spin 9s linear infinite;
  filter: drop-shadow(0 0 12px color-mix(in srgb, var(--ending-accent) 60%, transparent));
}

.ending-medallion-core {
  background: radial-gradient(circle at 50% 35%, color-mix(in srgb, var(--ending-accent) 22%, var(--tw-overlay-bg)), var(--tw-overlay-bg) 75%);
  border: 1px solid color-mix(in srgb, var(--ending-accent) 55%, transparent);
  color: var(--ending-accent);
  box-shadow: inset 0 0 18px color-mix(in srgb, var(--ending-accent) 30%, transparent);
}

.ending-card--won .ending-medallion {
  animation: ending-pop 0.9s 0.2s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.ending-card--lost .ending-medallion-core {
  animation: ending-ember 3.2s ease-in-out infinite;
}

/* Sparks rise for a win; embers sink for a loss. */
.ending-spark {
  position: absolute;
  bottom: -6px;
  left: calc(6% + (var(--i) * 8.5%));
  width: 3px;
  height: 3px;
  border-radius: 9999px;
  background: var(--ending-accent);
  box-shadow: 0 0 6px var(--ending-accent);
  opacity: 0;
  animation: ending-rise calc(3.5s + (var(--i) * 0.37s)) calc(var(--i) * -0.61s) linear infinite;
}

.ending-card--lost .ending-spark {
  bottom: auto;
  top: -6px;
  animation-name: ending-fall;
  animation-duration: calc(5s + (var(--i) * 0.45s));
}

@keyframes ending-in {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.97);
    filter: blur(3px);
  }
  to {
    opacity: 1;
    transform: none;
    filter: none;
  }
}

@keyframes ending-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes ending-pop {
  from {
    transform: scale(0.4);
    opacity: 0;
  }
  to {
    transform: none;
    opacity: 1;
  }
}

@keyframes ending-ember {
  0%,
  100% {
    box-shadow: inset 0 0 14px color-mix(in srgb, var(--ending-accent) 20%, transparent);
  }
  50% {
    box-shadow: inset 0 0 26px color-mix(in srgb, var(--ending-accent) 45%, transparent);
  }
}

@keyframes ending-rise {
  0% {
    transform: translateY(0);
    opacity: 0;
  }
  15% {
    opacity: 0.9;
  }
  100% {
    transform: translateY(-340px);
    opacity: 0;
  }
}

@keyframes ending-fall {
  0% {
    transform: translateY(0);
    opacity: 0;
  }
  20% {
    opacity: 0.6;
  }
  100% {
    transform: translateY(340px);
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ending-card,
  .ending-medallion,
  .ending-medallion-ring,
  .ending-medallion-core {
    animation: none !important;
  }

  .ending-sparks {
    display: none;
  }
}
</style>
