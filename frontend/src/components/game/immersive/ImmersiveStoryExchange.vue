<script setup lang="ts">
/**
 * ImmersiveStoryExchange — One exchange of a story page: protagonist speech/action bubble,
 * GM narration caption boxes, NPC dialogue bubbles, and item discovery cards.
 *
 * Colors, fonts and shapes come from the active dialog skin (tw-* classes, see src/skins).
 * Engine events appear inline as compact skinned notes (full list in the System tab);
 * failed-turn notices keep their Retry/Cancel actions.
 */
import { ref, computed } from 'vue'
import { configState } from '@/store/config'
import { audioService } from '@/services/audioService'
import { getItemIcon, getTypeColor, getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'
import type { ComicExchange, DialogueSegment } from '@/composables/useComicTurns'
import { renderDialogueHtml, renderFormattedHtml, resolveNpc } from '@/composables/useComicTurns'
import { useStoryBubbleAudio } from '@/composables/useStoryBubbleAudio'
import ImmersiveSystemMessage from '@/components/game/immersive/ImmersiveSystemMessage.vue'
import ImmersiveSystemNote from './ImmersiveSystemNote.vue'
import { isDebugMessage, isTurnErrorMessage } from './systemMessages'
import type { ChatMessage } from '@/types'
import { Volume2, VolumeX } from 'lucide-vue-next'
import ThinkingIndicator from './ThinkingIndicator.vue'
import { vDropCap } from '@/skins/vDropCap'

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

const playerName = computed(() => props.sheet?.name || 'You')
const userSpeech = computed(
  () => props.exchange.userSpeechText || props.exchange.userMessage?.content || ''
)

/** Engine events shown inline: failed turns as full notices, the rest as compact notes (no debug output). */
function storyEvents(messages: ChatMessage[]) {
  return messages
    .map((msg) => ({ msg, isError: isTurnErrorMessage(msg, props.turnError) }))
    .filter((event) => event.isError || !isDebugMessage(event.msg))
}

const leadingEvents = computed(() => storyEvents(props.exchange.systemMessages))
const trailingEvents = computed(() => storyEvents(props.exchange.trailingSystemMessages))

const revealedItems = computed(() =>
  props.exchange.revealedItemIds
    .map((itemId) => props.entities.find((e) => e.id === itemId))
    .filter((item): item is any => Boolean(item))
)

function dialogueSpeech(dlg: DialogueSegment): string {
  return dlg.voiceTag ? `[${dlg.voiceTag}] ${dlg.text}` : dlg.text
}

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
  <div class="tw-exchange flex flex-col">
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
          @click.stop="speakBubble(userSpeech, playerName)"
          class="absolute -top-2.5 right-3 z-30 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-200 flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/90 hover:bg-emerald-900 border border-emerald-400/60 text-emerald-300 text-[10px] font-black uppercase tracking-wider shadow-lg cursor-pointer backdrop-blur-md"
          :title="isSpeakingBubble(userSpeech, playerName) ? 'Stop Audio' : 'Play Audio'"
        >
          <VolumeX v-if="isSpeakingBubble(userSpeech, playerName)" class="w-3 h-3 text-red-400" />
          <Volume2 v-else class="w-3 h-3" />
          <span>{{ isSpeakingBubble(userSpeech, playerName) ? 'Stop' : 'Audio' }}</span>
        </button>

        <div class="tw-bubble tw-bubble--player">
          <!-- Speech tail pointing to the speaker on the left -->
          <svg class="tw-bubble-tail" viewBox="0 0 16 24" aria-hidden="true">
            <polygon points="16,0 0,12 16,24" />
            <rect x="14" y="1" width="4" height="22" />
          </svg>

          <p
            class="tw-bubble-text font-semibold"
            :class="{ italic: props.exchange.userIsDialogue }"
          >
            <span
              class="tw-speaker tw-speaker--player tw-speaker--primary mr-1.5 font-black text-xs sm:text-sm uppercase tracking-wider"
              @mouseenter="emit('npcHover', getEntityForHover(playerName), $event)"
              @mousemove="emit('npcHover', getEntityForHover(playerName), $event)"
              @mouseleave="emit('npcLeave')"
              @click="emit('openSheet')"
            >
              {{ playerName }}
            </span>

            <template v-if="props.exchange.userTargetName">
              <span class="tw-arrow mx-1 font-black text-xs">➔</span>
              <span
                class="tw-speaker tw-speaker--target mr-2.5 font-black text-xs sm:text-sm uppercase tracking-wider"
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

      <!-- Thinking indicator right next to the bubble -->
      <ThinkingIndicator
        v-if="props.isLatest && props.isEvaluating"
        class="self-center"
        :status-text="props.statusText"
      />
    </div>

    <!-- Fallback thinking indicator if evaluating without a user message -->
    <ThinkingIndicator
      v-else-if="props.isLatest && props.isEvaluating"
      class="self-start my-1"
      :status-text="props.statusText"
    />

    <!-- 2) ENGINE EVENTS BEFORE THE NARRATION (compact notes; failed turns keep Retry/Cancel) -->
    <template v-for="(event, sysIdx) in leadingEvents" :key="event.msg.id || `leading-${sysIdx}`">
      <ImmersiveSystemMessage
        v-if="event.isError"
        :msg="event.msg"
        :turn-error="props.turnError"
        :sheet="props.sheet"
        :game-id="props.gameId"
        :current-scene-description="props.currentSceneDescription"
        :npc-metadata="props.npcMetadata"
        @retry-turn="emit('retryTurn')"
        @cancel-turn-error="emit('cancelTurnError')"
      />
      <ImmersiveSystemNote v-else :msg="event.msg" />
    </template>

    <!-- 3) COMBINED GM NARRATION & NPC DIALOGUE BUBBLES -->
    <div
      v-for="(dlg, dIdx) in props.exchange.dialogues"
      :key="dIdx"
      class="flex flex-col gap-1 animate-fade-in items-start group shrink-0"
    >
      <!-- GM NARRATION BOX -->
      <div v-if="dlg.isNarration" class="relative group shrink-0 w-full max-w-2xl">
        <div class="tw-narration" :class="{ 'is-speaking': isSpeakingBubble(dlg.text) }">
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

          <div>
            <span class="tw-narration-label">Game Master</span>
            <span v-drop-cap class="tw-narration-text" v-html="renderFormattedHtml(dlg.text)"></span>
          </div>
        </div>
      </div>

      <!-- NPC DIALOGUE SPEECH BUBBLE -->
      <div v-else class="relative max-w-2xl">
        <!-- Overlay TTS Button -->
        <button
          v-if="configState.isTtsEnabled && !audioService.autoSpeechEnabled.value"
          type="button"
          @click.stop="speakBubble(dialogueSpeech(dlg), dlg.speaker)"
          class="absolute -top-2.5 right-3 z-30 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-200 flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider shadow-lg cursor-pointer backdrop-blur-md border"
          :class="dlg.isPlayer ? 'bg-emerald-950/90 hover:bg-emerald-900 border-emerald-400/60 text-emerald-300' : 'bg-amber-950/90 hover:bg-amber-900 border-amber-400/60 text-amber-300'"
          :title="isSpeakingBubble(dialogueSpeech(dlg), dlg.speaker) ? 'Stop Audio' : 'Play Audio'"
        >
          <VolumeX v-if="isSpeakingBubble(dialogueSpeech(dlg), dlg.speaker)" class="w-3 h-3 text-red-400" />
          <Volume2 v-else class="w-3 h-3" />
          <span>{{ isSpeakingBubble(dialogueSpeech(dlg), dlg.speaker) ? 'Stop' : 'Audio' }}</span>
        </button>

        <div
          class="tw-bubble"
          :class="{
            'tw-bubble--player': dlg.isPlayer,
            'is-speaking': isSpeakingBubble(dialogueSpeech(dlg), dlg.speaker),
          }"
        >
          <!-- Speech tail pointing left towards the NPC portrait card -->
          <svg class="tw-bubble-tail" viewBox="0 0 16 24" aria-hidden="true">
            <polygon points="16,0 0,12 16,24" />
            <rect x="14" y="1" width="4" height="22" />
          </svg>

          <p class="tw-bubble-text font-medium italic">
            <span
              class="tw-speaker tw-speaker--primary mr-1.5 font-black text-xs sm:text-sm uppercase tracking-wider"
              :class="{ 'tw-speaker--player': dlg.isPlayer }"
              @mouseenter="emit('npcHover', getEntityForHover(dlg.speakerEntity || dlg.speaker), $event)"
              @mousemove="emit('npcHover', getEntityForHover(dlg.speakerEntity || dlg.speaker), $event)"
              @mouseleave="emit('npcLeave')"
              @contextmenu.prevent="emit('npcContextmenu', resolveNpc(dlg.speaker, props.entities, props.npcMetadata) || { name: dlg.speaker, entity_type: 'NPC' }, $event)"
              @click="dlg.isPlayer ? emit('openSheet') : emit('npcClick', dlg.speaker)"
            >
              {{ dlg.speaker }}
            </span>

            <!-- Emotion / Voice Tag Badge -->
            <span v-if="dlg.voiceTag" class="comic-voice-tag select-none align-baseline mr-1.5">
              {{ dlg.voiceTag }}
            </span>

            <template v-if="dlg.target">
              <span class="tw-arrow mx-1 font-black text-xs">➔</span>
              <span
                class="tw-speaker tw-speaker--target mr-2.5 font-black text-xs sm:text-sm uppercase tracking-wider"
                @mouseenter="emit('npcHover', getEntityForHover(dlg.targetEntity || dlg.target), $event)"
                @mousemove="emit('npcHover', getEntityForHover(dlg.targetEntity || dlg.target), $event)"
                @mouseleave="emit('npcLeave')"
                @click="emit('npcClick', dlg.target)"
              >
                {{ dlg.target }}
              </span>
            </template>

            <span v-html="renderDialogueHtml(dlg.text)"></span>
          </p>
        </div>
      </div>
    </div>

    <!-- 4) ENGINE EVENTS AFTER THE NARRATION (items added, stat changes) -->
    <template v-for="(event, sysIdx) in trailingEvents" :key="event.msg.id || `trailing-${sysIdx}`">
      <ImmersiveSystemMessage
        v-if="event.isError"
        :msg="event.msg"
        :turn-error="props.turnError"
        :sheet="props.sheet"
        :game-id="props.gameId"
        :current-scene-description="props.currentSceneDescription"
        :npc-metadata="props.npcMetadata"
        @retry-turn="emit('retryTurn')"
        @cancel-turn-error="emit('cancelTurnError')"
      />
      <ImmersiveSystemNote v-else :msg="event.msg" />
    </template>

    <!-- 5) REVEALED ITEMS DISCOVERY CARDS -->
    <div v-if="revealedItems.length" class="flex flex-wrap gap-3 my-2 shrink-0">
      <div
        v-for="item in revealedItems"
        :key="item.id"
        class="tw-card tw-card--interactive flex items-center gap-3 p-2.5 shadow-lg"
        @click="emit('itemClick', item)"
      >
        <div class="w-8 h-8 rounded-lg overflow-hidden bg-slate-950 border border-slate-700 flex items-center justify-center shrink-0">
          <img
            v-if="item.image_url && showImage(item.image_url)"
            :src="getImageUrl(item.image_url, { thumbnail: true })"
            :alt="item.name"
            class="w-full h-full object-cover"
            @error="onImageLoadError($event, item.image_url)"
          />
          <i v-else :class="['ra text-base', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
        </div>
        <div>
          <span class="text-xs font-bold block">{{ item.name }}</span>
          <span class="tw-muted text-[10px] uppercase font-black tracking-wider">New Discovery!</span>
        </div>
        <button
          type="button"
          class="px-2 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[10px] font-black uppercase tracking-wider ml-2 cursor-pointer"
          @click.stop="emit('takeDirect', item)"
        >
          Take
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
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
