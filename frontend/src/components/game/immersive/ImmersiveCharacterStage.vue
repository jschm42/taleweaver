<script setup lang="ts">
/**
 * ImmersiveCharacterStage — Left-side 2:3 vertical character cards
 *
 * Displays portraits of the protagonist and scene NPCs with health status, defeat tags, and quick
 * click/hover interactions. With auto-speak on, the NPC whose line is being read aloud gets an
 * animated ring in the skin's accent color. Characters joining the scene
 * get a skin-specific entrance (see src/skins/entrances.css). Changed HP, Mana, Stamina or
 * attributes float up on the card as "-5 HP" / "+2 STR"; an HP loss also flashes the card.
 * Crowded scenes: defeated characters move last (see stageCastOrder.ts) and cards shrink to fit the
 * column height, switching to compact/mini layouts (see useStageDensity.ts).
 */
import { ref, watch, nextTick, computed } from 'vue'
import { getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'
import { audioService } from '@/services/audioService'
import { STAT_POPUP_STAGGER_MS, useStatChangePopups } from './useStatChangePopups'
import { useStageDensity } from './useStageDensity'
import { isDefeated, orderStageCast } from './stageCastOrder'

const props = defineProps<{
  npcs: any[]
  activeSpeakers: Set<string>
  activeTurnIndex?: number
}>()

const emit = defineEmits<{
  npcClick: [npc: any]
  npcHover: [entity: any, event: MouseEvent]
  npcLeave: []
  npcContextmenu: [npc: any, event: MouseEvent]
}>()

const stageContainerRef = ref<HTMLElement | null>(null)
const { popups: statPopups, hitCards } = useStatChangePopups(() => props.npcs)

function formatDelta(delta: number): string {
  return `${delta > 0 ? '+' : '−'}${Math.abs(delta)}`
}
const brokenImages = ref<Record<string, boolean>>({})

function scrollToTop() {
  if (!stageContainerRef.value) return
  stageContainerRef.value.scrollTo({
    top: 0,
    behavior: 'smooth'
  })
}

const activeSpeakersSignature = computed(() => {
  if (!props.activeSpeakers || props.activeSpeakers.size === 0) return ''
  return Array.from(props.activeSpeakers).sort().join(',')
})

const hasSpeakingNpc = computed(() => {
  if (!props.activeSpeakers || props.activeSpeakers.size === 0) return false
  return (props.npcs || []).some((npc) => isInLatestExchange(npc))
})

watch(
  [() => props.activeTurnIndex, activeSpeakersSignature],
  () => {
    if (hasSpeakingNpc.value) {
      nextTick(() => {
        scrollToTop()
      })
    }
  }
)

function handleImageError(path?: string | null) {
  if (!path) return
  brokenImages.value[path] = true
}

function onImageLoadError(e: Event, path?: string | null) {
  if (!path) return
  const target = e.target as HTMLImageElement
  if (target && target.src && target.src.includes('_thumb')) {
    target.src = getOriginalImageUrl(path)
  } else {
    handleImageError(path)
  }
}

function showImage(path?: string | null) {
  return !!path && !brokenImages.value[path]
}

// --- Entrances: characters that join the scene after the stage was first filled ---
const ARRIVAL_HIGHLIGHT_MS = 2600
const recentArrivals = ref<Set<string>>(new Set())
/** Entrance transitions start only after the first cast has rendered (no animation on load). */
const stageReady = ref(false)

watch(
  () => (props.npcs || []).map((npc) => String(npc.id)),
  (ids, previousIds) => {
    if (!stageReady.value) {
      if (ids.length) {
        nextTick(() => {
          stageReady.value = true
        })
      }
      return
    }
    const known = new Set(previousIds ?? [])
    const arrivals = ids.filter((id) => id !== 'PLAYER' && !known.has(id))
    if (!arrivals.length) {
      return
    }
    recentArrivals.value = new Set([...recentArrivals.value, ...arrivals])
    window.setTimeout(() => {
      const remaining = new Set(recentArrivals.value)
      arrivals.forEach((id) => remaining.delete(id))
      recentArrivals.value = remaining
    }, ARRIVAL_HIGHLIGHT_MS)
  }
)

function hasJustArrived(npc: any): boolean {
  return recentArrivals.value.has(String(npc.id))
}

function isInLatestExchange(npc: any): boolean {
  if (!npc || !props.activeSpeakers) return false
  const nameMatch = npc.name && props.activeSpeakers.has(npc.name.toLowerCase())
  const idMatch = npc.id && props.activeSpeakers.has(String(npc.id).toLowerCase())
  return Boolean(nameMatch || idMatch)
}

/** Lowercased speaker of the line auto-speak is reading right now, or '' if none. */
const voicedSpeaker = computed(() => {
  if (!audioService.autoSpeechEnabled.value || !audioService.isPlaying.value) {
    return ''
  }
  return (audioService.currentSpeaker.value || '').trim().toLowerCase()
})

/**
 * Danger level of the protagonist's card in 25% HP steps: 0 above 75%, 1 up to 75%,
 * 2 up to 50%, 3 up to 25% (and at 0). The card glows redder with each level.
 */
function playerDangerLevel(npc: any): 0 | 1 | 2 | 3 {
  if (npc?.id !== 'PLAYER') return 0
  const hp = Number(npc.hp)
  const maxHp = Number(npc.max_hp)
  if (!Number.isFinite(hp) || !Number.isFinite(maxHp) || maxHp <= 0) return 0
  const ratio = hp / maxHp
  if (ratio <= 0.25) return 3
  if (ratio <= 0.5) return 2
  if (ratio <= 0.75) return 1
  return 0
}

function playerCardClass(npc: any): string {
  const level = playerDangerLevel(npc)
  if (level === 0) return 'border-emerald-500/70 hover:border-emerald-400'
  return `tw-hp-danger-${level}`
}

function isNpcVoiced(npc: any): boolean {
  const speaker = voicedSpeaker.value
  if (!speaker || !npc) {
    return false
  }
  return String(npc.name || '').toLowerCase() === speaker || String(npc.id || '').toLowerCase() === speaker
}

// --- Crowded scenes: defeated characters last, cards shrink to fit the column ---
const orderedNpcs = computed(() => orderStageCast(props.npcs))
const { density, cardStyle } = useStageDensity(stageContainerRef, () => orderedNpcs.value.length)
</script>

<template>
  <aside
    ref="stageContainerRef"
    class="flex flex-col gap-2 shrink-0 overflow-y-auto w-16 sm:w-[5.6rem] md:w-[7.2rem] lg:w-[8.8rem] tw-scroll pr-1 py-1 max-h-full"
  >
    <TransitionGroup :name="stageReady ? 'tw-npc' : 'tw-npc-initial'" tag="div" class="flex flex-col gap-2 w-full">
      <div
        v-for="npc in orderedNpcs"
        :key="npc.id"
        class="relative group flex flex-col items-center bg-slate-950 border-2 transition-all duration-300 shrink-0 w-full overflow-hidden cursor-pointer shadow-[0_6px_20px_rgba(0,0,0,0.7)] active:scale-98"
        :style="cardStyle"
        :class="[
          density === 'mini' ? 'rounded-lg' : 'rounded-xl',
          { 'tw-npc-arrived': hasJustArrived(npc), 'tw-npc-hit': hitCards.has(String(npc.id)) },
          isNpcVoiced(npc)
            ? 'tw-npc-voiced border-transparent'
            : npc.id === 'PLAYER'
              ? playerCardClass(npc)
              : 'border-slate-700/70 hover:border-cyan-400/80'
        ]"
        :title="npc.id === 'PLAYER' ? (playerDangerLevel(npc) ? `Open your hero (HP ${npc.hp}/${npc.max_hp})` : 'Open your hero') : undefined"
        @click="emit('npcClick', npc)"
        @mouseenter="emit('npcHover', npc, $event)"
        @mousemove="emit('npcHover', npc, $event)"
        @mouseleave="emit('npcLeave')"
        @contextmenu.prevent="emit('npcContextmenu', npc, $event)"
      >
        <!-- Full 2:3 Character Portrait -->
        <img
          v-if="npc.image_url && showImage(npc.image_url)"
          :src="getImageUrl(npc.image_url, { thumbnail: true })"
          :alt="npc.name"
          class="w-full h-full object-cover object-top transition-transform duration-700 group-hover:scale-105"
          :class="{ 'grayscale opacity-50': isDefeated(npc) }"
          @error="onImageLoadError($event, npc.image_url)"
        />
        <div v-else class="w-full h-full flex flex-col items-center justify-center bg-gradient-to-b from-slate-900 to-slate-950 text-slate-600">
          <i :class="['ra mb-1', density === 'full' ? 'text-4xl' : 'text-2xl', npc.id === 'PLAYER' ? 'ra-player text-emerald-400' : 'ra-helmet text-cyan-400']"></i>
        </div>

        <!-- Entrance: one-off light sweep and a short "Enters" tag -->
        <div v-if="hasJustArrived(npc)" class="tw-npc-sweep" aria-hidden="true"></div>
        <div v-if="hasJustArrived(npc)" class="tw-npc-arrival-tag">Enters</div>

        <!-- Changed values float up from the top of the card -->
        <div v-if="statPopups[String(npc.id)]?.length" class="tw-stat-popups" aria-hidden="true">
          <span
            v-for="popup in statPopups[String(npc.id)]"
            :key="popup.id"
            class="tw-stat-popup"
            :class="popup.delta < 0 ? 'is-loss' : 'is-gain'"
            :style="{ animationDelay: `${popup.order * STAT_POPUP_STAGGER_MS}ms` }"
          >{{ formatDelta(popup.delta) }} {{ popup.label }}</span>
        </div>

        <!-- Voiced by auto-speak: rotating accent ring -->
        <div v-if="isNpcVoiced(npc)" class="tw-npc-voice-ring" aria-hidden="true"></div>

        <!-- Defeated: ribbon on larger cards, a small skull badge on mini cards -->
        <div v-if="isDefeated(npc) && density !== 'mini'" class="absolute -right-6 top-3 bg-red-600 text-white text-[8px] font-black uppercase tracking-[0.12em] py-0.5 w-24 text-center rotate-45 shadow-lg z-20">
          Defeated
        </div>
        <div
          v-else-if="isDefeated(npc)"
          class="absolute right-1 top-1 z-20 flex h-4 w-4 items-center justify-center rounded-full bg-red-600 text-[9px] text-white shadow-lg"
          title="Defeated"
        >
          <i class="ra ra-skull"></i>
        </div>

        <!-- Name & Role Overlay with Gradient & Strong Shadow (role only on full cards) -->
        <div
          class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/95 via-black/60 to-transparent flex flex-col items-center text-center pointer-events-none z-10"
          :class="density === 'mini' ? 'pt-3 pb-0.5 px-1' : 'pt-8 pb-2 px-2'"
        >
          <h4
            class="font-black text-white group-hover:text-amber-300 transition-colors uppercase drop-shadow-[0_2px_3px_rgba(0,0,0,1)] truncate w-full"
            :class="density === 'mini' ? 'text-[9px] tracking-wide' : 'text-[11px] sm:text-xs tracking-wider'"
          >
            {{ npc.name }}
          </h4>
          <span v-if="npc.role && density === 'full'" class="text-[9px] font-bold text-slate-300/90 uppercase tracking-widest drop-shadow-[0_1px_2px_rgba(0,0,0,1)] truncate w-full mt-0.5">
            {{ npc.role }}
          </span>
        </div>
      </div>
    </TransitionGroup>
  </aside>
</template>

<style scoped>
@property --tw-voice-angle {
  syntax: '<angle>';
  initial-value: 0deg;
  inherits: false;
}

.tw-npc-voiced {
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--tw-accent, #f59e0b) 55%, transparent),
    0 0 22px color-mix(in srgb, var(--tw-accent, #f59e0b) 55%, transparent);
  animation: tw-voice-glow 1.6s ease-in-out infinite;
}

/* A bright arc runs around the card edge; the mask cuts out everything but a 3px frame. */
.tw-npc-voice-ring {
  position: absolute;
  inset: 0;
  z-index: 20;
  padding: 3px;
  border-radius: inherit;
  pointer-events: none;
  background: conic-gradient(
    from var(--tw-voice-angle),
    var(--tw-accent, #f59e0b),
    color-mix(in srgb, var(--tw-accent, #f59e0b) 15%, transparent) 30%,
    #fff8e1 50%,
    color-mix(in srgb, var(--tw-accent, #f59e0b) 15%, transparent) 70%,
    var(--tw-accent, #f59e0b)
  );
  mask:
    linear-gradient(#000 0 0) content-box exclude,
    linear-gradient(#000 0 0);
  animation: tw-voice-spin 2.4s linear infinite;
}

@keyframes tw-voice-spin {
  to {
    --tw-voice-angle: 360deg;
  }
}

@keyframes tw-voice-glow {
  50% {
    box-shadow:
      0 0 0 1px color-mix(in srgb, var(--tw-accent, #f59e0b) 80%, transparent),
      0 0 34px color-mix(in srgb, var(--tw-accent, #f59e0b) 75%, transparent);
  }
}

/* Stat changes: values float up from the top of the card and fade (see useStatChangePopups). */
.tw-stat-popups {
  position: absolute;
  /* Starts around the card's middle and floats up from there (the name sits at the bottom). */
  inset: 34% 0.25rem auto;
  z-index: 30;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
  pointer-events: none;
  /* The value scales with the card (narrow on phones, wide on desktops). */
  container-type: inline-size;
}

.tw-stat-popup {
  padding: 0.1rem 0.5rem;
  border-radius: 9999px;
  font-size: clamp(0.8rem, 14cqi, 1.2rem);
  line-height: 1.2;
  font-weight: 900;
  letter-spacing: 0.04em;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 1);
  background: rgba(2, 6, 23, 0.75);
  opacity: 0;
  animation: tw-stat-float 3.2s ease-out forwards;
}

.tw-stat-popup.is-loss {
  color: rgb(254 202 202);
  border: 1px solid rgb(239 68 68 / 0.7);
  box-shadow: 0 0 10px rgb(239 68 68 / 0.45);
}

.tw-stat-popup.is-gain {
  color: rgb(187 247 208);
  border: 1px solid rgb(34 197 94 / 0.7);
  box-shadow: 0 0 10px rgb(34 197 94 / 0.4);
}

@keyframes tw-stat-float {
  0% { opacity: 0; transform: translateY(0.9rem) scale(0.7); }
  12% { opacity: 1; transform: translateY(0) scale(1.15); }
  22% { transform: translateY(0) scale(1); }
  75% { opacity: 1; transform: translateY(-0.6rem); }
  100% { opacity: 0; transform: translateY(-1.4rem); }
}

/* HP loss: a short red flash and shake of the whole card. */
.tw-npc-hit {
  animation: tw-npc-hit 0.9s ease-out;
}

.tw-npc-hit::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 25;
  pointer-events: none;
  background: radial-gradient(circle at 50% 40%, rgb(239 68 68 / 0.55), rgb(127 29 29 / 0.25) 70%);
  animation: tw-npc-hit-flash 0.9s ease-out forwards;
}

@keyframes tw-npc-hit {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-3px); }
  40% { transform: translateX(3px); }
  60% { transform: translateX(-2px); }
  80% { transform: translateX(1px); }
}

@keyframes tw-npc-hit-flash {
  from { opacity: 1; }
  to { opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .tw-stat-popup {
    animation-name: tw-stat-fade;
  }

  .tw-npc-hit {
    animation: none;
  }
}

@keyframes tw-stat-fade {
  0%, 100% { opacity: 0; }
  10%, 80% { opacity: 1; }
}

/* Protagonist low on HP: the card glows redder in 25% steps (see playerDangerLevel). */
.tw-hp-danger-1 {
  border-color: rgb(251 113 133 / 0.6);
  box-shadow:
    0 6px 20px rgba(0, 0, 0, 0.7),
    0 0 12px rgb(239 68 68 / 0.35);
}

.tw-hp-danger-2 {
  border-color: rgb(239 68 68 / 0.85);
  box-shadow:
    0 6px 20px rgba(0, 0, 0, 0.7),
    0 0 20px rgb(239 68 68 / 0.6);
}

.tw-hp-danger-3 {
  border-color: rgb(220 38 38);
  box-shadow:
    0 6px 20px rgba(0, 0, 0, 0.7),
    0 0 30px rgb(220 38 38 / 0.85),
    inset 0 0 18px rgb(220 38 38 / 0.45);
  animation: tw-hp-danger-pulse 1.2s ease-in-out infinite;
}

@keyframes tw-hp-danger-pulse {
  50% {
    box-shadow:
      0 6px 20px rgba(0, 0, 0, 0.7),
      0 0 42px rgb(239 68 68 / 1),
      inset 0 0 26px rgb(239 68 68 / 0.6);
  }
}

@media (prefers-reduced-motion: reduce) {
  .tw-npc-voiced,
  .tw-npc-voice-ring,
  .tw-hp-danger-3 {
    animation: none;
  }
}

.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
