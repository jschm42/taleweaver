<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { configState } from '@/store/config'
import { audioService } from '@/services/audioService'
import { api } from '@/composables/useApi'
import { useGameSocket } from '@/composables/useGameSocket'
import { useNotifications } from '@/composables/useNotifications'

const props = defineProps<{
  open: boolean
  gameId: string
  title: string
  format: string
  content: string
  imageUrl?: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { language } = useGameSocket()
const { addNotification } = useNotifications()
const translatedContent = ref('')
const translatedLanguage = ref('')
const isTranslating = ref(false)

const formatLabel = (value: string) => {
  const normalized = String(value || '').toUpperCase()
  if (!normalized) return 'DOCUMENT'
  if (['DOCUMENT', 'SCROLL', 'BOOK', 'SIGN'].includes(normalized)) return normalized
  return 'DOCUMENT'
}

const normalizedFormat = computed(() => formatLabel(props.format))

const contentTypographyClass = computed(() => {
  switch (normalizedFormat.value) {
    case 'BOOK':
      return 'font-serif tracking-[0.01em] leading-8 text-[1.06rem]'
    case 'SCROLL':
      return "font-['Caveat'] tracking-[0.02em] leading-8 text-[1.22rem]"
    case 'SIGN':
      return 'font-mono uppercase tracking-[0.12em] leading-7 text-[1rem]'
    case 'DOCUMENT':
    default:
      return 'font-sans tracking-[0.015em] leading-7 text-[1.02rem]'
  }
})

const contentCardClass = computed(() => {
  switch (normalizedFormat.value) {
    case 'BOOK':
      return 'border-orange-300/25 bg-gradient-to-b from-amber-200/10 via-amber-100/5 to-slate-950/20 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
    case 'SCROLL':
      return 'border-yellow-200/30 bg-gradient-to-b from-yellow-100/10 via-amber-100/5 to-slate-950/20 shadow-[inset_0_1px_0_rgba(255,244,200,0.14)]'
    case 'SIGN':
      return 'border-cyan-300/30 bg-gradient-to-b from-cyan-200/10 via-sky-200/5 to-slate-950/20 shadow-[inset_0_1px_0_rgba(180,255,255,0.12)]'
    case 'DOCUMENT':
    default:
      return 'border-amber-500/20 bg-gradient-to-b from-amber-500/8 via-amber-500/4 to-slate-950/20 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]'
  }
})

const activeContent = computed(() => {
  const translated = String(translatedContent.value || '').trim()
  if (translated) return translated
  return String(props.content || '')
})

const targetLanguage = computed(() => String(language.value || '').trim())
const canTranslate = computed(() => {
  return Boolean(props.gameId && targetLanguage.value && String(props.content || '').trim().length > 0)
})

const canSpeak = computed(() => configState.isTtsEnabled && String(props.content || '').trim().length > 0)

const handleTranslateTextLog = async () => {
  if (!canTranslate.value || isTranslating.value) return

  isTranslating.value = true
  try {
    const result = await api.translateSessionText(props.gameId, {
      text: props.content,
      language: targetLanguage.value,
    })
    translatedContent.value = String(result.translated_text || '').trim()
    translatedLanguage.value = String(result.language || targetLanguage.value)
  } catch (error: any) {
    addNotification(error?.message || 'Failed to translate text log.', 'error')
  } finally {
    isTranslating.value = false
  }
}

const handleSpeakTextLog = () => {
  if (!canSpeak.value) return

  if (audioService.isPlaying.value) {
    audioService.stop()
    return
  }

  audioService.unlock()
  void audioService.speak(activeContent.value, {
    title: props.title,
    useTextChunking: false,
  })
}

watch(
  () => [props.open, props.content, targetLanguage.value],
  () => {
    translatedContent.value = ''
    translatedLanguage.value = ''
  },
)
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0 z-[120] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="emit('close')" />

        <div class="relative z-10 w-full max-w-2xl max-h-[85vh] overflow-hidden rounded-3xl border border-slate-700 bg-slate-950 shadow-2xl flex flex-col">
          <div class="flex items-center justify-between px-6 py-4 border-b border-slate-800">
            <div class="min-w-0 flex items-start gap-3">
              <div v-if="imageUrl" class="w-10 h-10 rounded-lg overflow-hidden border border-slate-800 bg-slate-900/80 shrink-0">
                <img :src="imageUrl" class="w-full h-full object-contain" />
              </div>
              <div class="min-w-0">
                <h3 class="text-lg font-black uppercase tracking-wide text-amber-100 truncate">{{ title }}</h3>
                <p class="text-[10px] uppercase tracking-[0.2em] text-amber-400/80 mt-1">{{ formatLabel(format) }}</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <button
                :disabled="!canTranslate || isTranslating"
                class="px-3 py-2 rounded-xl border text-[10px] font-black uppercase tracking-wider transition-all flex items-center gap-2"
                :class="[
                  canTranslate && !isTranslating
                    ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20 hover:text-emerald-100'
                    : 'border-slate-700 bg-slate-900/70 text-slate-500 cursor-not-allowed'
                ]"
                @click="handleTranslateTextLog"
                :title="canTranslate ? `Translate to ${targetLanguage}` : 'Select a Bable Fish language first'"
              >
                <i class="ra ra-fish"></i>
                <span>{{ isTranslating ? 'Translating...' : 'Translate' }}</span>
              </button>

              <button
                v-if="configState.isTtsEnabled"
                :disabled="!canSpeak || audioService.isGenerating.value"
                class="px-3 py-2 rounded-xl border text-[10px] font-black uppercase tracking-wider transition-all flex items-center gap-2"
                :class="[
                  canSpeak && !audioService.isGenerating.value
                    ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-200 hover:bg-cyan-500/20 hover:text-cyan-100'
                    : 'border-slate-700 bg-slate-900/70 text-slate-500 cursor-not-allowed'
                ]"
                @click="handleSpeakTextLog"
                :title="audioService.isPlaying.value ? 'Stop reading' : 'Read text log aloud'"
              >
                <i :class="audioService.isPlaying.value ? 'ra ra-audio-spectrum' : 'ra ra-microphone'"></i>
                <span>{{ audioService.isPlaying.value ? 'Stop' : 'Read' }}</span>
              </button>

              <button
                class="p-2 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                @click="emit('close')"
                title="Close"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          <div class="overflow-y-auto p-6 space-y-4">
            <div :class="['rounded-2xl border p-5 transition-colors duration-200', contentCardClass]">
              <p
                v-if="translatedContent"
                class="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-emerald-300/80"
              >
                Translated to {{ translatedLanguage || targetLanguage }}
              </p>
              <p :class="['text-base md:text-lg text-amber-50/90 leading-relaxed whitespace-pre-wrap', contentTypographyClass]">{{ activeContent || 'No text content found.' }}</p>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
