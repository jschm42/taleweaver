<script setup lang="ts">
/**
 * ImmersiveSystemMessage — One system / debug / error announcement in the story feed,
 * with optional TTS and inline Retry/Cancel actions for failed turns.
 */
import { computed } from 'vue'
import { configState } from '@/store/config'
import { renderFormattedHtml } from '@/composables/useComicTurns'
import { useStoryBubbleAudio } from '@/composables/useStoryBubbleAudio'
import { Volume2, VolumeX, RotateCcw } from 'lucide-vue-next'

const props = defineProps<{
  msg: any
  turnError?: { message: string; action: string } | null
  sheet?: any
  gameId?: string
  currentSceneDescription?: string | null
  npcMetadata: Record<string, any>
}>()

const emit = defineEmits<{
  retryTurn: []
  cancelTurnError: []
}>()

const { isSpeakingBubble, speakBubble } = useStoryBubbleAudio(() => props)

const isDebug = computed(() => {
  if (props.msg?.is_debug) return true
  const c = String(props.msg?.content || '').trim()
  return c.startsWith('[DEBUG') || c.startsWith('DEBUG:') || c.startsWith('--- DEBUG')
})

const isError = computed(() =>
  Boolean(props.turnError?.message && String(props.msg?.content || '').includes(props.turnError.message))
)

const cleanContent = computed(() => {
  const content = String(props.msg?.content || '')
  if (isDebug.value) return content
  return content
    .replace(/\s*\[DEBUG:\s*Trigger fired\][^\n]*/gi, '')
    .replace(/\s*\[DEBUG\][^\n]*/gi, '')
    .trim()
})
</script>

<template>
  <div class="animate-fade-in relative group my-1 shrink-0">
    <div
      :class="[
        'relative rounded-r-2xl p-4 sm:p-5 shadow-[0_12px_35px_rgba(0,0,0,0.7)] backdrop-blur-xl border-y border-r text-slate-100 transition-all',
        isError
          ? 'bg-red-950/80 border-l-4 border-l-red-500 border-red-500/40 shadow-red-950/40'
          : isDebug
            ? 'bg-slate-950/90 border-l-4 border-l-cyan-400 border-cyan-500/30 shadow-cyan-950/20'
            : 'bg-slate-900/95 border-l-4 border-emerald-500 border-emerald-500/30'
      ]"
    >
      <!-- Overlay TTS Button -->
      <button
        v-if="configState.isTtsEnabled && !isDebug"
        type="button"
        @click.stop="speakBubble(cleanContent, 'System')"
        class="absolute -top-2.5 right-3 z-30 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-200 flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/90 hover:bg-emerald-900 border border-emerald-400/60 text-emerald-300 text-[10px] font-black uppercase tracking-wider shadow-lg cursor-pointer backdrop-blur-md"
        :title="isSpeakingBubble(cleanContent, 'System') ? 'Stop Audio' : 'Play Audio'"
      >
        <VolumeX v-if="isSpeakingBubble(cleanContent, 'System')" class="w-3 h-3 text-red-400" />
        <Volume2 v-else class="w-3 h-3" />
        <span>{{ isSpeakingBubble(cleanContent, 'System') ? 'Stop' : 'Audio' }}</span>
      </button>

      <!-- System Header & Content -->
      <div
        :class="[
          'comic-narration-text text-sm sm:text-base leading-relaxed',
          isError ? 'text-red-100' : isDebug ? 'text-cyan-100' : 'text-emerald-100'
        ]"
      >
        <span
          :class="[
            'inline-flex items-center align-middle mr-2.5 not-italic select-none px-2 py-0.5 rounded-md font-sans font-black text-[10px] uppercase tracking-[0.2em] shadow-sm',
            isError
              ? 'bg-red-500/20 text-red-400 border border-red-500/40'
              : isDebug
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
          ]"
        >
          {{ isError ? 'Error' : isDebug ? 'Debug' : 'System' }}
        </span>
        <pre v-if="isDebug && (props.msg.content.includes('\n') || props.msg.content.length > 90)" class="mt-2 p-3 rounded-xl bg-black/60 border border-cyan-500/20 text-cyan-300/90 text-xs font-mono whitespace-pre-wrap break-all custom-scrollbar">{{ props.msg.content }}</pre>
        <span v-else class="italic font-medium" :class="{ 'font-mono text-xs text-cyan-200/90 not-italic': isDebug }" v-html="renderFormattedHtml(cleanContent)"></span>
      </div>

      <!-- Inline Action Buttons (Retry & Cancel) -->
      <div v-if="isError" class="mt-3.5 pt-3 border-t border-red-500/25 flex items-center gap-2.5 not-italic">
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
</template>

<style scoped>
.comic-narration-text {
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
</style>
