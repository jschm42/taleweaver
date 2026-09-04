<script setup lang="ts">
/**
 * ImmersiveStoryFeed — Comic narration, dialogue bubbles, and turn history
 *
 * Displays the comic storyline: System announcements, protagonist speech bubbles,
 * GM narrative caption boxes, NPC dialogue bubbles with angled tails pointing
 * to character portraits, item discovery cards, and turn pagination controls.
 */
import { ref } from 'vue'
import { configState } from '@/store/config'
import { audioService } from '@/services/audioService'
import { getItemIcon, getTypeColor, getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'
import type { ComicTurn } from '@/composables/useComicTurns'
import { renderFormattedHtml, resolveNpc } from '@/composables/useComicTurns'
import LicenseInfoBlock from '@/components/game/LicenseInfoBlock.vue'
import {
  Sparkles,
  Volume2,
  VolumeX,
  Brain,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
} from 'lucide-vue-next'

const props = defineProps<{
  gameTurns: ComicTurn[]
  activeTurn: ComicTurn | null
  activeTurnIndex: number
  viewingTurnIndex: number | null
  isEvaluating?: boolean
  statusText?: string
  sheet?: any
  entities: any[]
  currentSceneDescription?: string | null
  npcMetadata: Record<string, any>
  gameId?: string
  turnError?: { message: string; action: string } | null
}>()

const emit = defineEmits<{
  goToTurn: [index: number]
  goToLatestTurn: []
  retryTurn: []
  cancelTurnError: []
  openSheet: []
  npcClick: [name: string]
  itemClick: [item: any]
  takeDirect: [item: any]
  npcHover: [entity: any, event: MouseEvent]
  npcLeave: []
  npcContextmenu: [entity: any, event: MouseEvent]
}>()

const brokenImages = ref<Record<string, boolean>>({})

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

function getBubbleTtsText(text: string, speakerName?: string) {
  return speakerName ? `${speakerName}: ${text}` : text
}

function isSpeakingBubble(text: string, speakerName?: string) {
  if (!audioService.isPlaying.value) return false
  const target = getBubbleTtsText(text, speakerName)
  return audioService.currentText.value === target || audioService.currentText.value === text
}

function speakBubble(text: string, speakerName?: string) {
  if (!text || !configState.isTtsEnabled) return
  if (isSpeakingBubble(text, speakerName)) {
    audioService.stop()
    return
  }
  audioService.unlock()
  const contentToSpeak = getBubbleTtsText(text, speakerName)
  audioService.speak(contentToSpeak, {
    sceneDescription: props.currentSceneDescription || undefined,
    adventureId: props.sheet?.template_id,
    sessionId: props.gameId,
    title: props.sheet?.adventure_title,
    sceneName: props.sheet?.current_scene,
    tone: props.sheet?.adventure_tone,
    npcMetadata: props.npcMetadata,
  })
}

function getEntityForHover(nameOrEntity: any) {
  if (typeof nameOrEntity === 'object' && nameOrEntity && nameOrEntity.id) {
    const cloned = { ...nameOrEntity }
    if (!cloned.entity_type) cloned.entity_type = 'NPC'
    return cloned
  }
  const name = typeof nameOrEntity === 'string' ? nameOrEntity.trim() : String(nameOrEntity?.name || '').trim()
  const norm = name.toLowerCase()
  if (norm === 'you' || norm === (props.sheet?.name || '').toLowerCase() || norm === `you (${props.sheet?.name || ''})`.toLowerCase()) {
    return {
      id: 'PLAYER',
      name: props.sheet?.name || 'You',
      entity_type: 'NPC',
      description: props.sheet?.description || 'Your hero character.',
      image_url: props.sheet?.profile_image || null,
      role: props.sheet?.role || 'Hero',
      hp: typeof props.sheet?.hp === 'number' ? props.sheet?.hp : 100,
      max_hp: typeof props.sheet?.max_hp === 'number' ? props.sheet?.max_hp : 100,
      mana: typeof props.sheet?.mana === 'number' ? props.sheet?.mana : 50,
      max_mana: typeof props.sheet?.max_mana === 'number' ? props.sheet?.max_mana : 50,
      stamina: typeof props.sheet?.stamina === 'number' ? props.sheet?.stamina : 50,
      max_stamina: typeof props.sheet?.max_stamina === 'number' ? props.sheet?.max_stamina : 50,
      inventory: Array.isArray(props.sheet?.inventory) ? props.sheet.inventory : [],
      stats: props.sheet?.stats,
    }
  }
  const resolved = resolveNpc(name, props.entities, props.npcMetadata)
  if (resolved) return resolved
  return { name, entity_type: 'NPC', description: 'A character in this adventure.' }
}

function isDebugSystemMessage(msg: any): boolean {
  if (!msg) return false
  if (msg.is_debug) return true
  const c = String(msg.content || '').trim()
  return c.startsWith('[DEBUG') || c.startsWith('DEBUG:') || c.startsWith('--- DEBUG')
}
</script>

<template>
  <div class="flex-1 flex flex-col justify-between min-h-0 relative overflow-hidden">
    <!-- COMIC STORY CONTAINER (Turn Display) -->
    <div class="flex-1 overflow-y-auto custom-scrollbar p-2 sm:p-4 flex flex-col gap-4 min-h-0 relative">
      <!-- Empty State -->
      <div v-if="!props.activeTurn && !props.isEvaluating" class="flex-1 flex flex-col items-center justify-center text-slate-500">
        <Sparkles class="w-8 h-8 text-amber-400/60 mb-2 animate-pulse" />
        <p class="text-sm font-semibold tracking-wider uppercase">Awaiting Adventure Turn...</p>
      </div>

      <template v-else-if="props.activeTurn">
        <!-- 0A) LICENSE & CREDITS BANNER (Initial Turn / Re-run) -->
        <LicenseInfoBlock v-if="props.activeTurn.licenseMessage" :msg="props.activeTurn.licenseMessage" />

        <!-- 0B) SYSTEM MESSAGES / INTRO TEXT BANNER -->
        <div
          v-for="(sysMsg, sIdx) in props.activeTurn.systemMessages"
          :key="sIdx"
          class="animate-fade-in relative group my-1"
        >
          <div
            :class="[
              'relative rounded-r-2xl p-4 sm:p-5 shadow-[0_12px_35px_rgba(0,0,0,0.7)] backdrop-blur-xl border-y border-r text-slate-100 transition-all',
              props.turnError && props.turnError.message && sysMsg.content.includes(props.turnError.message)
                ? 'bg-red-950/80 border-l-4 border-l-red-500 border-red-500/40 shadow-red-950/40'
                : isDebugSystemMessage(sysMsg)
                  ? 'bg-slate-950/90 border-l-4 border-l-cyan-400 border-cyan-500/30 shadow-cyan-950/20'
                  : 'bg-slate-900/95 border-l-4 border-emerald-500 border-emerald-500/30'
            ]"
          >
            <!-- Overlay TTS Button -->
            <button
              v-if="configState.isTtsEnabled && !isDebugSystemMessage(sysMsg)"
              type="button"
              @click.stop="speakBubble(sysMsg.content, 'System')"
              class="absolute -top-2.5 right-3 z-30 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-200 flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/90 hover:bg-emerald-900 border border-emerald-400/60 text-emerald-300 text-[10px] font-black uppercase tracking-wider shadow-lg cursor-pointer backdrop-blur-md"
              :title="isSpeakingBubble(sysMsg.content, 'System') ? 'Stop Audio' : 'Play Audio'"
            >
              <VolumeX v-if="isSpeakingBubble(sysMsg.content, 'System')" class="w-3 h-3 text-red-400" />
              <Volume2 v-else class="w-3 h-3" />
              <span>{{ isSpeakingBubble(sysMsg.content, 'System') ? 'Stop' : 'Audio' }}</span>
            </button>

            <!-- System Header & Content -->
            <div
              :class="[
                'comic-narration-text text-sm sm:text-base leading-relaxed',
                props.turnError && props.turnError.message && sysMsg.content.includes(props.turnError.message)
                  ? 'text-red-100'
                  : isDebugSystemMessage(sysMsg)
                    ? 'text-cyan-100'
                    : 'text-emerald-100'
              ]"
            >
              <span
                :class="[
                  'inline-flex items-center align-middle mr-2.5 not-italic select-none px-2 py-0.5 rounded-md font-sans font-black text-[10px] uppercase tracking-[0.2em] shadow-sm',
                  props.turnError && props.turnError.message && sysMsg.content.includes(props.turnError.message)
                    ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                    : isDebugSystemMessage(sysMsg)
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                      : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                ]"
              >
                {{ props.turnError && props.turnError.message && sysMsg.content.includes(props.turnError.message) ? 'Error' : isDebugSystemMessage(sysMsg) ? 'Debug' : 'System' }}
              </span>
              <pre v-if="isDebugSystemMessage(sysMsg) && (sysMsg.content.includes('\n') || sysMsg.content.length > 90)" class="mt-2 p-3 rounded-xl bg-black/60 border border-cyan-500/20 text-cyan-300/90 text-xs font-mono whitespace-pre-wrap break-all custom-scrollbar">{{ sysMsg.content }}</pre>
              <span v-else class="italic font-medium" :class="{ 'font-mono text-xs text-cyan-200/90 not-italic': isDebugSystemMessage(sysMsg) }" v-html="renderFormattedHtml(sysMsg.content)"></span>
            </div>

            <!-- Inline Action Buttons (Retry & Cancel) -->
            <div
              v-if="props.turnError && props.turnError.message && sysMsg.content.includes(props.turnError.message)"
              class="mt-3.5 pt-3 border-t border-red-500/25 flex items-center gap-2.5 not-italic"
            >
              <button
                type="button"
                @click.stop="emit('retryTurn')"
                class="px-3.5 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-black uppercase tracking-wider text-[11px] transition-all flex items-center gap-1.5 shadow-md active:scale-95 cursor-pointer"
                title="Retry this action"
              >
                <RotateCcw class="w-3.5 h-3.5" />
                Retry
              </button>
              <button
                type="button"
                @click.stop="emit('cancelTurnError')"
                class="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white font-bold uppercase tracking-wider text-[11px] transition-all border border-white/10 active:scale-95 cursor-pointer"
                title="Cancel error"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>

        <!-- 1) PROTAGONIST / USER SPEECH OR ACTION BUBBLE -->
        <div
          v-if="props.activeTurn.userMessage"
          class="flex flex-wrap items-center gap-3 animate-fade-in group"
        >
          <div class="relative max-w-2xl">
            <!-- Overlay TTS Button (visible on hover) -->
            <button
              v-if="configState.isTtsEnabled"
              type="button"
              @click.stop="speakBubble(props.activeTurn.userSpeechText || props.activeTurn.userMessage.content, props.sheet?.name || 'You')"
              class="absolute -top-2.5 right-3 z-30 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-200 flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/90 hover:bg-emerald-900 border border-emerald-400/60 text-emerald-300 text-[10px] font-black uppercase tracking-wider shadow-lg cursor-pointer backdrop-blur-md"
              :title="isSpeakingBubble(props.activeTurn.userSpeechText || props.activeTurn.userMessage.content, props.sheet?.name || 'You') ? 'Stop Audio' : 'Play Audio'"
            >
              <VolumeX v-if="isSpeakingBubble(props.activeTurn.userSpeechText || props.activeTurn.userMessage.content, props.sheet?.name || 'You')" class="w-3 h-3 text-red-400" />
              <Volume2 v-else class="w-3 h-3" />
              <span>{{ isSpeakingBubble(props.activeTurn.userSpeechText || props.activeTurn.userMessage.content, props.sheet?.name || 'You') ? 'Stop' : 'Audio' }}</span>
            </button>

            <!-- SVG Speech Tail pointing to Speaker on Left -->
            <svg
              class="absolute -left-3.5 top-4 w-4 h-6 text-slate-900 pointer-events-none z-20 overflow-visible"
              viewBox="0 0 16 24"
            >
              <polygon
                points="16,0 0,12 16,24"
                class="fill-slate-900 stroke-emerald-400"
                stroke-width="2"
                stroke-linejoin="round"
              />
              <rect x="14" y="1" width="4" height="22" class="fill-slate-900" />
            </svg>

            <div
              class="relative p-3.5 sm:p-4.5 rounded-2xl border-2 shadow-[0_8px_25px_rgba(0,0,0,0.6)] backdrop-blur-xl bg-slate-900/95 border-emerald-400 text-slate-100"
            >
              <!-- Content: Name Tag, Target Addressee & Speech -->
              <p
                class="comic-bubble-text text-sm sm:text-base leading-relaxed font-semibold"
                :class="props.activeTurn.userIsDialogue ? 'italic text-white' : 'text-emerald-100'"
              >
                <!-- Speaker Tag -->
                <span
                  class="inline-flex items-center align-baseline mr-1.5 not-italic select-none px-2 py-0.5 rounded-lg border font-black text-xs sm:text-sm uppercase tracking-wider bg-emerald-500/20 border-emerald-400/50 text-emerald-300 hover:bg-emerald-500/30 hover:border-emerald-400 cursor-pointer transition-all shadow-sm"
                  @mouseenter="emit('npcHover', getEntityForHover(props.sheet?.name || 'You'), $event)"
                  @mousemove="emit('npcHover', getEntityForHover(props.sheet?.name || 'You'), $event)"
                  @mouseleave="emit('npcLeave')"
                  @click="emit('openSheet')"
                >
                  {{ props.sheet?.name || 'You' }}
                </span>

                <!-- Target Addressee Tag with Arrow -->
                <template v-if="props.activeTurn.userTargetName">
                  <span class="inline-flex items-center align-baseline text-slate-400 mx-1 not-italic font-black text-xs select-none">
                    ➔
                  </span>
                  <span
                    class="inline-flex items-center align-baseline mr-2.5 not-italic select-none px-2 py-0.5 rounded-lg border font-black text-xs sm:text-sm uppercase tracking-wider bg-cyan-500/20 border-cyan-400/50 text-cyan-300 hover:bg-cyan-500/30 hover:border-cyan-400 cursor-pointer transition-all shadow-sm"
                    @mouseenter="emit('npcHover', getEntityForHover(props.activeTurn.userTargetEntity || props.activeTurn.userTargetName), $event)"
                    @mousemove="emit('npcHover', getEntityForHover(props.activeTurn.userTargetEntity || props.activeTurn.userTargetName), $event)"
                    @mouseleave="emit('npcLeave')"
                    @click="emit('npcClick', props.activeTurn.userTargetName)"
                  >
                    {{ props.activeTurn.userTargetName }}
                  </span>
                </template>

                {{ props.activeTurn.userIsDialogue ? `"${props.activeTurn.userSpeechText}"` : props.activeTurn.userSpeechText }}
              </p>
            </div>
          </div>

          <!-- Animated Brain Thinking Indicator right next to the bubble -->
          <div
            v-if="props.isEvaluating"
            class="flex items-center gap-2 px-3 py-1.5 rounded-2xl bg-amber-950/80 border border-amber-400/70 text-amber-200 shadow-[0_0_20px_rgba(251,191,36,0.3)] backdrop-blur-xl animate-fade-in shrink-0 self-center select-none"
            :title="props.statusText || 'Thinking & Validating rules...'"
          >
            <div class="relative flex items-center justify-center w-5 h-5">
              <div class="absolute inset-0 rounded-full bg-amber-400/20 animate-ping"></div>
              <Brain class="w-4 h-4 text-amber-400 animate-pulse" />
            </div>
            <span class="text-xs font-black uppercase tracking-wider text-amber-300">
              {{ props.statusText || 'Thinking...' }}
            </span>
          </div>
        </div>

        <!-- Fallback Brain Thinking Indicator if evaluating without a user message -->
        <div
          v-else-if="props.isEvaluating"
          class="flex items-center gap-2.5 px-3.5 py-2 rounded-2xl bg-amber-950/80 border border-amber-400/70 text-amber-200 shadow-[0_0_20px_rgba(251,191,36,0.3)] backdrop-blur-xl animate-fade-in shrink-0 self-start my-1 select-none"
        >
          <div class="relative flex items-center justify-center w-5 h-5">
            <div class="absolute inset-0 rounded-full bg-amber-400/20 animate-ping"></div>
            <Brain class="w-4 h-4 text-amber-400 animate-pulse" />
          </div>
          <span class="text-xs font-black uppercase tracking-wider text-amber-300">
            {{ props.statusText || 'Thinking...' }}
          </span>
        </div>

        <!-- 2) GM COMIC NARRATIVE CAPTION BOX -->
        <div v-if="props.activeTurn.narration" class="animate-fade-in relative group">
          <div class="relative bg-slate-900/95 border-2 border-amber-500/70 rounded-2xl p-4 sm:p-5 shadow-[0_12px_35px_rgba(0,0,0,0.7)] backdrop-blur-xl">
            <!-- Overlay TTS Button -->
            <button
              v-if="configState.isTtsEnabled"
              type="button"
              @click.stop="speakBubble(props.activeTurn.narration)"
              class="absolute -top-2.5 right-3 z-30 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-200 flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-950/90 hover:bg-amber-900 border border-amber-400/60 text-amber-300 text-[10px] font-black uppercase tracking-wider shadow-lg cursor-pointer backdrop-blur-md"
              :title="isSpeakingBubble(props.activeTurn.narration) ? 'Stop Audio' : 'Play Audio'"
            >
              <VolumeX v-if="isSpeakingBubble(props.activeTurn.narration)" class="w-3 h-3 text-red-400" />
              <Volume2 v-else class="w-3 h-3" />
              <span>{{ isSpeakingBubble(props.activeTurn.narration) ? 'Stop' : 'Audio' }}</span>
            </button>

            <!-- Narrative Text with Inline "GAME MASTER" Badge in Text Flow -->
            <div class="comic-narration-text text-sm sm:text-base leading-relaxed text-slate-100">
              <span
                class="inline-flex items-center align-middle mr-2.5 not-italic select-none px-2 py-0.5 rounded-md bg-amber-500 text-slate-950 font-sans font-black text-[10px] uppercase tracking-[0.2em] shadow-sm"
              >
                Game Master
              </span>
              <span v-html="renderFormattedHtml(props.activeTurn.narration)"></span>
            </div>
          </div>
        </div>

        <!-- 3) NPC DIALOGUE COMIC SPEECH BUBBLES -->
        <div
          v-for="(dlg, dIdx) in props.activeTurn.dialogues"
          :key="dIdx"
          class="flex flex-col gap-1 animate-fade-in items-start group"
        >
          <div class="relative max-w-2xl">
            <!-- Overlay TTS Button -->
            <button
              v-if="configState.isTtsEnabled"
              type="button"
              @click.stop="speakBubble(dlg.text, dlg.speaker)"
              class="absolute -top-2.5 right-3 z-30 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-200 flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider shadow-lg cursor-pointer backdrop-blur-md border"
              :class="dlg.isPlayer ? 'bg-emerald-950/90 hover:bg-emerald-900 border-emerald-400/60 text-emerald-300' : 'bg-amber-950/90 hover:bg-amber-900 border-amber-400/60 text-amber-300'"
              :title="isSpeakingBubble(dlg.text, dlg.speaker) ? 'Stop Audio' : 'Play Audio'"
            >
              <VolumeX v-if="isSpeakingBubble(dlg.text, dlg.speaker)" class="w-3 h-3 text-red-400" />
              <Volume2 v-else class="w-3 h-3" />
              <span>{{ isSpeakingBubble(dlg.text, dlg.speaker) ? 'Stop' : 'Audio' }}</span>
            </button>

            <!-- Comic Angled Speech Tail pointing Left directly towards the NPC portrait card -->
            <svg
              class="absolute -left-3.5 top-4 w-4 h-6 text-slate-900 pointer-events-none z-20 overflow-visible"
              viewBox="0 0 16 24"
            >
              <polygon
                points="16,0 0,12 16,24"
                class="fill-slate-900"
                :class="dlg.isPlayer ? 'stroke-emerald-400' : 'stroke-amber-400'"
                stroke-width="2"
                stroke-linejoin="round"
              />
              <rect x="14" y="1" width="4" height="22" class="fill-slate-900" />
            </svg>

            <div
              class="relative p-3.5 sm:p-4.5 rounded-2xl border-2 shadow-[0_10px_30px_rgba(0,0,0,0.65)] backdrop-blur-xl bg-slate-900/95"
              :class="dlg.isPlayer ? 'border-emerald-400 text-slate-100' : 'border-amber-400 text-slate-100 shadow-[0_0_20px_rgba(251,191,36,0.25)]'"
            >
              <p class="comic-bubble-text text-sm sm:text-base leading-relaxed font-medium italic text-white">
                <!-- Speaker Tag -->
                <span
                  class="inline-flex items-center align-baseline mr-1.5 not-italic select-none px-2 py-0.5 rounded-lg border font-black text-xs sm:text-sm uppercase tracking-wider cursor-pointer transition-all shadow-sm"
                  :class="[
                    dlg.isPlayer
                      ? 'bg-emerald-500/20 border-emerald-400/50 text-emerald-300 hover:bg-emerald-500/30 hover:border-emerald-400'
                      : 'bg-amber-500/20 border-amber-400/50 text-amber-300 hover:bg-amber-500/30 hover:border-amber-400'
                  ]"
                  @mouseenter="emit('npcHover', getEntityForHover(dlg.speakerEntity || dlg.speaker), $event)"
                  @mousemove="emit('npcHover', getEntityForHover(dlg.speakerEntity || dlg.speaker), $event)"
                  @mouseleave="emit('npcLeave')"
                  @contextmenu.prevent="emit('npcContextmenu', resolveNpc(dlg.speaker, props.entities, props.npcMetadata) || { name: dlg.speaker, entity_type: 'NPC' }, $event)"
                  @click="dlg.isPlayer ? emit('openSheet') : emit('npcClick', dlg.speaker)"
                >
                  {{ dlg.speaker }}
                </span>

                <!-- Target Addressee Badge (if targeted) -->
                <template v-if="dlg.target">
                  <span class="inline-flex items-center align-baseline text-slate-400 mx-1 not-italic font-black text-xs select-none">
                    ➔
                  </span>
                  <span
                    class="inline-flex items-center align-baseline mr-2.5 not-italic select-none px-2 py-0.5 rounded-lg border font-black text-xs sm:text-sm uppercase tracking-wider bg-cyan-500/20 border-cyan-400/50 text-cyan-300 hover:bg-cyan-500/30 hover:border-cyan-400 cursor-pointer transition-all shadow-sm"
                    @mouseenter="emit('npcHover', getEntityForHover(dlg.targetEntity || dlg.target), $event)"
                    @mousemove="emit('npcHover', getEntityForHover(dlg.targetEntity || dlg.target), $event)"
                    @mouseleave="emit('npcLeave')"
                    @click="emit('npcClick', dlg.target)"
                  >
                    {{ dlg.target }}
                  </span>
                </template>

                "{{ dlg.text }}"
              </p>
            </div>
          </div>
        </div>

        <!-- 4) REVEALED ITEMS DISCOVERY CARDS -->
        <div v-if="props.activeTurn.revealedItemIds.length" class="flex flex-wrap gap-3 my-2">
          <div
            v-for="itemId in props.activeTurn.revealedItemIds"
            :key="itemId"
            v-show="props.entities.find((e) => e.id === itemId)"
            class="flex items-center gap-3 p-2.5 rounded-xl bg-slate-900/90 border border-emerald-500/50 shadow-lg cursor-pointer hover:border-emerald-400"
            @click="emit('itemClick', props.entities.find((e) => e.id === itemId))"
          >
            <div class="w-8 h-8 rounded-lg overflow-hidden bg-slate-950 border border-slate-700 flex items-center justify-center shrink-0">
              <img
                v-if="props.entities.find((e) => e.id === itemId)?.image_url && showImage(props.entities.find((e) => e.id === itemId).image_url)"
                :src="getImageUrl(props.entities.find((e) => e.id === itemId).image_url, { thumbnail: true })"
                class="w-full h-full object-cover"
                @error="onImageLoadError($event, props.entities.find((e) => e.id === itemId).image_url)"
              />
              <i v-else :class="['ra text-base', getItemIcon(props.entities.find((e) => e.id === itemId)?.item_type), getTypeColor(props.entities.find((e) => e.id === itemId)?.item_type)]"></i>
            </div>
            <div>
              <span class="text-xs font-bold text-white block">{{ props.entities.find((e) => e.id === itemId)?.name }}</span>
              <span class="text-[10px] text-emerald-400 uppercase font-black tracking-wider">New Discovery!</span>
            </div>
            <button
              type="button"
              class="px-2 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[10px] font-black uppercase tracking-wider ml-2 cursor-pointer"
              @click.stop="emit('takeDirect', props.entities.find((e) => e.id === itemId))"
            >
              Take
            </button>
          </div>
        </div>
      </template>
    </div>

    <!-- COMIC TURN NAVIGATION & PAGING CONTROLS -->
    <div v-if="props.gameTurns.length > 1" class="flex items-center justify-between px-3 py-1.5 bg-slate-950/80 border-t border-slate-800/80 shrink-0 text-xs font-bold text-slate-400">
      <div class="flex items-center gap-1">
        <button
          type="button"
          :disabled="props.activeTurnIndex <= 0"
          @click="emit('goToTurn', props.activeTurnIndex - 1)"
          class="p-1 rounded bg-slate-900 border border-slate-700 disabled:opacity-30 disabled:cursor-not-allowed hover:text-white cursor-pointer"
          title="Previous Turn"
        >
          <ChevronLeft class="w-3.5 h-3.5" />
        </button>
        <span class="px-2 font-mono">Turn {{ props.activeTurnIndex + 1 }} / {{ props.gameTurns.length }}</span>
        <button
          type="button"
          :disabled="props.activeTurnIndex >= props.gameTurns.length - 1"
          @click="emit('goToTurn', props.activeTurnIndex + 1)"
          class="p-1 rounded bg-slate-900 border border-slate-700 disabled:opacity-30 disabled:cursor-not-allowed hover:text-white cursor-pointer"
          title="Next Turn"
        >
          <ChevronRight class="w-3.5 h-3.5" />
        </button>
      </div>

      <button
        v-if="props.viewingTurnIndex !== null"
        type="button"
        @click="emit('goToLatestTurn')"
        class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-black uppercase tracking-wider hover:bg-amber-500/30 cursor-pointer"
      >
        Jump to Latest
      </button>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.05); border-radius: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.1); }

.comic-narration-text,
.comic-bubble-text {
  font-family: 'Acme', sans-serif;
  letter-spacing: 0.02em;
}

:deep(.comic-voice-tag) {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
  padding: 0.125rem 0.4rem;
  margin: 0 0.3rem 0 0;
  border-radius: 0.375rem;
  font-size: 0.6875rem;
  font-weight: 800;
  line-height: 1.25;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  background: rgba(251, 191, 36, 0.15);
  color: rgb(252, 211, 77);
  border: 1px solid rgba(251, 191, 36, 0.3);
}

:deep(.comic-object-tag) {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
  padding: 0.125rem 0.35rem;
  margin: 0 0.2rem;
  border-radius: 0.375rem;
  font-family: monospace;
  font-size: 0.75rem;
  font-weight: 700;
  line-height: 1.25;
  background: rgba(56, 189, 248, 0.15);
  color: rgb(56, 189, 248);
  border: 1px solid rgba(56, 189, 248, 0.3);
}

.animate-fade-in {
  animation: comicPop 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes comicPop {
  0% {
    opacity: 0;
    transform: translateY(12px) scale(0.98);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
