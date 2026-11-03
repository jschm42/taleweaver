<script setup lang="ts">
/**
 * AwardUnlockedOverlay — Announces an award earned during play in a glowing card near the top of
 * the game area (not fullscreen) for a few seconds. Triggered by the backend's
 * "Award Achievement: <title>" system message, so GM-, rule- and script-granted awards all show.
 * Awards already in the history when the page loads are not announced again.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { formatEntityRefs } from '@/utils/entityRefs'

const AWARD_MESSAGE_PREFIX = 'Award Achievement: '
/** How long one award stays on screen (ms); matches the progress line animation. */
const DISPLAY_MS = 5200

interface AnnouncedAward {
  id: number
  title: string
  tier: string
  description: string
}

const props = defineProps<{
  messages: Array<{ role?: string; content?: unknown }>
  awards?: Array<{ key?: string; title?: string; tier?: string; description?: string }>
}>()

const queue = ref<AnnouncedAward[]>([])
const current = computed(() => queue.value[0] ?? null)
let nextId = 1
let seenAwardMessages: number | null = null
let timer = 0

function awardTitles(): string[] {
  return (props.messages || [])
    .filter((m) => m.role === 'system' && String(m.content ?? '').startsWith(AWARD_MESSAGE_PREFIX))
    .map((m) => String(m.content).slice(AWARD_MESSAGE_PREFIX.length).trim())
}

function describe(title: string): AnnouncedAward {
  const award = (props.awards || []).find((a) => a.title === title || a.key === title)
  return {
    id: nextId++,
    title: award?.title || title,
    tier: String(award?.tier || 'gold').toLowerCase(),
    description: award?.description || '',
  }
}

function showNext() {
  window.clearTimeout(timer)
  if (!current.value) return
  timer = window.setTimeout(dismiss, DISPLAY_MS)
}

function dismiss() {
  queue.value = queue.value.slice(1)
  showNext()
}

// Count the award messages: the first count is the loaded history; later growth is new awards.
// Counting (instead of comparing message objects) survives the feed reloading its messages.
watch(
  () => awardTitles(),
  (titles) => {
    if (seenAwardMessages === null) {
      seenAwardMessages = titles.length
      return
    }
    if (titles.length <= seenAwardMessages) {
      seenAwardMessages = titles.length
      return
    }
    const fresh = titles.slice(seenAwardMessages).map(describe)
    seenAwardMessages = titles.length
    const wasIdle = !current.value
    queue.value = [...queue.value, ...fresh]
    if (wasIdle) showNext()
  },
  { immediate: true }
)

onBeforeUnmount(() => window.clearTimeout(timer))
</script>

<template>
  <div class="tw-award-layer" role="status" aria-live="polite">
    <Transition name="tw-award">
      <button
        v-if="current"
        :key="current.id"
        type="button"
        class="tw-award-card"
        :class="`tier-${current.tier}`"
        :style="{ '--tw-award-ms': `${DISPLAY_MS}ms` }"
        title="Dismiss"
        @click="dismiss"
      >
        <span class="tw-award-shine" aria-hidden="true"></span>
        <span class="tw-award-icon" aria-hidden="true"><i class="ra ra-trophy"></i></span>
        <span class="tw-award-text">
          <span class="tw-award-kicker">Achievement Unlocked</span>
          <span class="tw-award-title">{{ current.title }}</span>
          <span v-if="current.description" class="tw-award-desc" v-html="formatEntityRefs(current.description)"></span>
        </span>
        <span class="tw-award-tier">{{ current.tier }}</span>
        <span class="tw-award-progress" aria-hidden="true"></span>
      </button>
    </Transition>
  </div>
</template>

<style scoped>
.tw-award-layer {
  position: absolute;
  top: 1.25rem;
  left: 50%;
  z-index: 60;
  width: min(30rem, calc(100% - 2rem));
  transform: translateX(-50%);
  pointer-events: none;
}

.tw-award-card {
  --tw-award-color: 245 158 11;
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.9rem;
  width: 100%;
  overflow: hidden;
  padding: 0.9rem 1.1rem 1.1rem;
  border-radius: 1rem;
  border: 1px solid rgb(var(--tw-award-color) / 0.75);
  background:
    radial-gradient(circle at 12% 50%, rgb(var(--tw-award-color) / 0.28), transparent 55%),
    linear-gradient(135deg, rgb(15 23 42 / 0.96), rgb(2 6 23 / 0.96));
  box-shadow:
    0 18px 40px rgb(0 0 0 / 0.65),
    0 0 28px rgb(var(--tw-award-color) / 0.45);
  color: #fff;
  text-align: left;
  cursor: pointer;
  pointer-events: auto;
  animation: tw-award-glow 2.2s ease-in-out infinite;
}

.tier-bronze { --tw-award-color: 205 127 50; }
.tier-silver { --tw-award-color: 203 213 225; }
.tier-gold { --tw-award-color: 245 158 11; }
.tier-negative { --tw-award-color: 239 68 68; }

.tw-award-icon {
  display: grid;
  flex-shrink: 0;
  place-items: center;
  width: 3.2rem;
  height: 3.2rem;
  border-radius: 9999px;
  border: 2px solid rgb(var(--tw-award-color));
  background: rgb(var(--tw-award-color) / 0.18);
  color: rgb(var(--tw-award-color));
  font-size: 1.6rem;
  box-shadow: 0 0 18px rgb(var(--tw-award-color) / 0.6);
  animation: tw-award-pop 0.7s cubic-bezier(0.34, 1.56, 0.64, 1) 0.15s both;
}

.tw-award-text {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 0.15rem;
}

.tw-award-kicker {
  font-size: 0.65rem;
  font-weight: 900;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgb(var(--tw-award-color));
}

.tw-award-title {
  font-size: 1.15rem;
  font-weight: 900;
  line-height: 1.2;
  text-shadow: 0 2px 6px rgb(0 0 0 / 0.9);
}

.tw-award-desc {
  display: -webkit-box;
  overflow: hidden;
  font-size: 0.8rem;
  line-height: 1.35;
  color: rgb(203 213 225);
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.tw-award-tier {
  flex-shrink: 0;
  align-self: flex-start;
  padding: 0.1rem 0.55rem;
  border-radius: 9999px;
  border: 1px solid rgb(var(--tw-award-color) / 0.7);
  font-size: 0.6rem;
  font-weight: 900;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: rgb(var(--tw-award-color));
}

/* A light band sweeps across the card once it has landed. */
.tw-award-shine {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(110deg, transparent 35%, rgb(255 255 255 / 0.28) 50%, transparent 65%);
  transform: translateX(-120%);
  animation: tw-award-shine 1.4s ease-out 0.35s forwards;
}

/* Time left until the card closes. */
.tw-award-progress {
  position: absolute;
  inset: auto 0 0;
  height: 3px;
  background: rgb(var(--tw-award-color));
  transform-origin: left;
  animation: tw-award-progress var(--tw-award-ms, 5200ms) linear forwards;
}

.tw-award-enter-active {
  animation: tw-award-in 0.55s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.tw-award-leave-active {
  transition: opacity 0.35s ease, transform 0.35s ease;
}

.tw-award-leave-to {
  opacity: 0;
  transform: translateY(-0.75rem) scale(0.96);
}

@keyframes tw-award-in {
  from { opacity: 0; transform: translateY(-1.5rem) scale(0.85); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes tw-award-pop {
  from { transform: scale(0) rotate(-25deg); }
  to { transform: scale(1) rotate(0); }
}

@keyframes tw-award-shine {
  to { transform: translateX(120%); }
}

@keyframes tw-award-progress {
  from { transform: scaleX(1); }
  to { transform: scaleX(0); }
}

@keyframes tw-award-glow {
  50% {
    box-shadow:
      0 18px 40px rgb(0 0 0 / 0.65),
      0 0 44px rgb(var(--tw-award-color) / 0.7);
  }
}

@media (prefers-reduced-motion: reduce) {
  .tw-award-card,
  .tw-award-icon,
  .tw-award-shine {
    animation: none;
  }

  .tw-award-shine {
    display: none;
  }

  .tw-award-enter-active {
    animation: none;
    transition: opacity 0.3s ease;
  }

  .tw-award-enter-from {
    opacity: 0;
  }
}
</style>
