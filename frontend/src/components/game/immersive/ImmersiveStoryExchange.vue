<script setup lang="ts">
/**
 * ImmersiveStoryExchange — One exchange of a story page: protagonist speech/action bubble,
 * engine events, GM narration caption boxes, NPC dialogue bubbles, and item discovery cards.
 */
import { ref } from 'vue'
import { configState } from '@/store/config'
import { audioService } from '@/services/audioService'
import { getItemIcon, getTypeColor, getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'
import type { ComicExchange } from '@/composables/useComicTurns'
import { renderFormattedHtml, resolveNpc } from '@/composables/useComicTurns'
import { useStoryBubbleAudio } from '@/composables/useStoryBubbleAudio'
import ImmersiveSystemMessage from '@/components/game/immersive/ImmersiveSystemMessage.vue'
import { Volume2, VolumeX, Brain } from 'lucide-vue-next'

const props = defineProps<{
  exchange: ComicExchange
  /** Latest exchange of the latest page: shows the "thinking" indicator while evaluating. */
  isLatest?: boolean
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

const { isSpeakingBubble, speakBubble } = useStoryBubbleAudio(() => props)
const brokenImages = ref<Record<string, boolean>>({})

function onImageLoadError(e: Event, path?: string | null) {
  if (!path) return
  const target = e.target as HTMLImageElement
  if (target && target.src && target.src.includes('_thumb')) {
    target.src = getOriginalImageUrl(path)
  } else {
    brokenImages.value[path] = true
  }
}

function showImage(path?: string | null) {
  return !!path && !brokenImages.value[path]
}

function findEntity(itemId: string) {
  return props.entities.find((e) => e.id === itemId)
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
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- 1) PROTAGONIST / USER SPEECH OR ACTION BUBBLE -->
    <div
      v-if="props.exchange.userMessage"
      class="flex flex-wrap items-center gap-3 animate-fade-in group shrink-0"
    >
      <div class="relative max-w-2xl">
        <!-- Overlay TTS Button (visible on hover) -->
        <button
          v-if="configState.isTtsEnabled"
          type="button"
          @click.stop="speakBubble(props.exchange.userSpeechText || props.exchange.userMessage.content, props.sheet?.name || 'You')"
          class="absolute -top-2.5 right-3 z-30 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-200 flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/90 hover:bg-emerald-900 border border-emerald-400/60 text-emerald-300 text-[10px] font-black uppercase tracking-wider shadow-lg cursor-pointer backdrop-blur-md"
          :title="isSpeakingBubble(props.exchange.userSpeechText || props.exchange.userMessage.content, props.sheet?.name || 'You') ? 'Stop Audio' : 'Play Audio'"
        >
          <VolumeX v-if="isSpeakingBubble(props.exchange.userSpeechText || props.exchange.userMessage.content, props.sheet?.name || 'You')" class="w-3 h-3 text-red-400" />
          <Volume2 v-else class="w-3 h-3" />
          <span>{{ isSpeakingBubble(props.exchange.userSpeechText || props.exchange.userMessage.content, props.sheet?.name || 'You') ? 'Stop' : 'Audio' }}</span>
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
            :class="props.exchange.userIsDialogue ? 'italic text-white' : 'text-emerald-100'"
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
            <template v-if="props.exchange.userTargetName">
              <span class="inline-flex items-center align-baseline text-slate-400 mx-1 not-italic font-black text-xs select-none">
                ➔
              </span>
              <span
                class="inline-flex items-center align-baseline mr-2.5 not-italic select-none px-2 py-0.5 rounded-lg border font-black text-xs sm:text-sm uppercase tracking-wider bg-cyan-500/20 border-cyan-400/50 text-cyan-300 hover:bg-cyan-500/30 hover:border-cyan-400 cursor-pointer transition-all shadow-sm"
                @mouseenter="emit('npcHover', getEntityForHover(props.exchange.userTargetEntity || props.exchange.userTargetName), $event)"
                @mousemove="emit('npcHover', getEntityForHover(props.exchange.userTargetEntity || props.exchange.userTargetName), $event)"
                @mouseleave="emit('npcLeave')"
                @click="emit('npcClick', props.exchange.userTargetName)"
              >
                {{ props.exchange.userTargetName }}
              </span>
            </template>

            {{ props.exchange.userIsDialogue ? `"${props.exchange.userSpeechText}"` : props.exchange.userSpeechText }}
          </p>
        </div>
      </div>

      <!-- Animated Brain Thinking Indicator right next to the bubble -->
      <div
        v-if="props.isLatest && props.isEvaluating"
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
      v-else-if="props.isLatest && props.isEvaluating"
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

    <!-- 2) ENGINE EVENTS BEFORE THE NARRATION (rolls, rule checks, triggers) -->
    <ImmersiveSystemMessage
      v-for="(sysMsg, sysIdx) in props.exchange.systemMessages"
      :key="sysMsg.id || `pre-${sysIdx}`"
      :msg="sysMsg"
      :turn-error="props.turnError"
      :sheet="props.sheet"
      :game-id="props.gameId"
      :current-scene-description="props.currentSceneDescription"
      :npc-metadata="props.npcMetadata"
      @retry-turn="emit('retryTurn')"
      @cancel-turn-error="emit('cancelTurnError')"
    />

    <!-- 3) COMBINED GM NARRATION & NPC DIALOGUE BUBBLES -->
    <div
      v-for="(dlg, dIdx) in props.exchange.dialogues"
      :key="dIdx"
      class="flex flex-col gap-1 animate-fade-in items-start group shrink-0"
    >
      <!-- GM NARRATION BOX -->
      <div v-if="dlg.isNarration" class="relative group shrink-0 w-full max-w-2xl">
        <div
          class="relative bg-slate-900/95 border-2 border-amber-500/70 rounded-2xl p-4 sm:p-5 shadow-[0_12px_35px_rgba(0,0,0,0.7)] backdrop-blur-xl transition-all duration-300"
          :class="{'ring-2 ring-amber-400 shadow-[0_0_30px_rgba(251,191,36,0.5)] scale-[1.01]': isSpeakingBubble(dlg.text)}"
        >
          <!-- Overlay TTS Button -->
          <button
            v-if="configState.isTtsEnabled && !audioService.autoSpeechEnabled.value"
            type="button"
            @click.stop="speakBubble(dlg.text)"
            class="absolute -top-2.5 right-3 z-30 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-200 flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-950/90 hover:bg-amber-900 border border-amber-400/60 text-amber-300 text-[10px] font-black uppercase tracking-wider shadow-lg cursor-pointer backdrop-blur-md"
            :title="isSpeakingBubble(dlg.text) ? 'Stop Audio' : 'Play Audio'"
          >
            <VolumeX v-if="isSpeakingBubble(dlg.text)" class="w-3 h-3 text-red-400" />
            <Volume2 v-else class="w-3 h-3" />
            <span>{{ isSpeakingBubble(dlg.text) ? 'Stop' : 'Audio' }}</span>
          </button>

          <!-- Narrative Text with Inline "GAME MASTER" Badge -->
          <div class="comic-narration-text text-sm sm:text-base leading-relaxed text-slate-100">
            <span
              class="inline-flex items-center align-middle mr-2.5 not-italic select-none px-2 py-0.5 rounded-md bg-amber-500 text-slate-950 font-sans font-black text-[10px] uppercase tracking-[0.2em] shadow-sm"
            >
              Game Master
            </span>
            <span v-html="renderFormattedHtml(dlg.text)"></span>
          </div>
        </div>
      </div>

      <!-- NPC DIALOGUE COMIC SPEECH BUBBLE -->
      <div v-else class="relative max-w-2xl">
        <!-- Overlay TTS Button -->
        <button
          v-if="configState.isTtsEnabled && !audioService.autoSpeechEnabled.value"
          type="button"
          @click.stop="speakBubble(dlg.voiceTag ? `[${dlg.voiceTag}] ${dlg.text}` : dlg.text, dlg.speaker)"
          class="absolute -top-2.5 right-3 z-30 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-200 flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider shadow-lg cursor-pointer backdrop-blur-md border"
          :class="dlg.isPlayer ? 'bg-emerald-950/90 hover:bg-emerald-900 border-emerald-400/60 text-emerald-300' : 'bg-amber-950/90 hover:bg-amber-900 border-amber-400/60 text-amber-300'"
          :title="isSpeakingBubble(dlg.voiceTag ? `[${dlg.voiceTag}] ${dlg.text}` : dlg.text, dlg.speaker) ? 'Stop Audio' : 'Play Audio'"
        >
          <VolumeX v-if="isSpeakingBubble(dlg.voiceTag ? `[${dlg.voiceTag}] ${dlg.text}` : dlg.text, dlg.speaker)" class="w-3 h-3 text-red-400" />
          <Volume2 v-else class="w-3 h-3" />
          <span>{{ isSpeakingBubble(dlg.voiceTag ? `[${dlg.voiceTag}] ${dlg.text}` : dlg.text, dlg.speaker) ? 'Stop' : 'Audio' }}</span>
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
          class="relative p-3.5 sm:p-4.5 rounded-2xl border-2 shadow-[0_10px_30px_rgba(0,0,0,0.65)] backdrop-blur-xl bg-slate-900/95 transition-all duration-300"
          :class="[
            dlg.isPlayer ? 'border-emerald-400 text-slate-100' : 'border-amber-400 text-slate-100 shadow-[0_0_20px_rgba(251,191,36,0.25)]',
            isSpeakingBubble(dlg.voiceTag ? `[${dlg.voiceTag}] ${dlg.text}` : dlg.text, dlg.speaker) ? (dlg.isPlayer ? 'ring-2 ring-emerald-400 shadow-[0_0_30px_rgba(52,211,153,0.5)] scale-[1.01]' : 'ring-2 ring-amber-400 shadow-[0_0_30px_rgba(251,191,36,0.5)] scale-[1.01]') : ''
          ]"
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

            <!-- Emotion / Voice Tag Badge -->
            <span
              v-if="dlg.voiceTag"
              class="comic-voice-tag not-italic select-none align-baseline mr-1.5"
            >
              [{{ dlg.voiceTag }}]
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

    <!-- 4) ENGINE EVENTS AFTER THE NARRATION (items added, stat changes) -->
    <ImmersiveSystemMessage
      v-for="(sysMsg, sysIdx) in props.exchange.trailingSystemMessages"
      :key="sysMsg.id || `post-${sysIdx}`"
      :msg="sysMsg"
      :turn-error="props.turnError"
      :sheet="props.sheet"
      :game-id="props.gameId"
      :current-scene-description="props.currentSceneDescription"
      :npc-metadata="props.npcMetadata"
      @retry-turn="emit('retryTurn')"
      @cancel-turn-error="emit('cancelTurnError')"
    />

    <!-- 5) REVEALED ITEMS DISCOVERY CARDS -->
    <div v-if="props.exchange.revealedItemIds.length" class="flex flex-wrap gap-3 my-2 shrink-0">
      <div
        v-for="itemId in props.exchange.revealedItemIds"
        :key="itemId"
        v-show="findEntity(itemId)"
        class="flex items-center gap-3 p-2.5 rounded-xl bg-slate-900/90 border border-emerald-500/50 shadow-lg cursor-pointer hover:border-emerald-400"
        @click="emit('itemClick', findEntity(itemId))"
      >
        <div class="w-8 h-8 rounded-lg overflow-hidden bg-slate-950 border border-slate-700 flex items-center justify-center shrink-0">
          <img
            v-if="findEntity(itemId)?.image_url && showImage(findEntity(itemId).image_url)"
            :src="getImageUrl(findEntity(itemId).image_url, { thumbnail: true })"
            class="w-full h-full object-cover"
            @error="onImageLoadError($event, findEntity(itemId).image_url)"
          />
          <i v-else :class="['ra text-base', getItemIcon(findEntity(itemId)?.item_type), getTypeColor(findEntity(itemId)?.item_type)]"></i>
        </div>
        <div>
          <span class="text-xs font-bold text-white block">{{ findEntity(itemId)?.name }}</span>
          <span class="text-[10px] text-emerald-400 uppercase font-black tracking-wider">New Discovery!</span>
        </div>
        <button
          type="button"
          class="px-2 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[10px] font-black uppercase tracking-wider ml-2 cursor-pointer"
          @click.stop="emit('takeDirect', findEntity(itemId))"
        >
          Take
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
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
