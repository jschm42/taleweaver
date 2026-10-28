<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Backpack, AudioLines } from 'lucide-vue-next'
import { configState } from '@/store/config'
import { audioService } from '@/services/audioService'
import { api } from '@/composables/useApi'
import { useGameSocket } from '@/composables/useGameSocket'
import { useNotifications } from '@/composables/useNotifications'
import { formatEntityRefs } from '@/utils/entityRefs'
import { getImageUrl, hasRenderableImagePath } from '@/utils/game_icons'
import InlinePromptPanel from './InlinePromptPanel.vue'

/** Readable item (document, scroll, book, sign), shown inline at the end of the story feed. */
const props = defineProps<{
  open: boolean
  gameId: string
  title: string
  format: string
  content: string
  imageUrl?: string | null
  canTake?: boolean
  isTaking?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'take'): void
}>()

const READABLE_FORMATS: Record<string, string> = {
  DOCUMENT: 'ra-quill-ink',
  SCROLL: 'ra-scroll-unfurled',
  BOOK: 'ra-book',
  SIGN: 'ra-wooden-sign',
}

const { language } = useGameSocket()
const { addNotification } = useNotifications()
const translatedContent = ref('')
const translatedLanguage = ref('')
const isTranslating = ref(false)

const normalizedFormat = computed(() => {
  const normalized = String(props.format || '').toUpperCase()
  return normalized in READABLE_FORMATS ? normalized : 'DOCUMENT'
})
const formatIcon = computed(() => READABLE_FORMATS[normalizedFormat.value])

const resolvedImageUrl = computed(() => {
  if (!hasRenderableImagePath(props.imageUrl)) return null
  return getImageUrl(props.imageUrl, { thumbnail: true }) || props.imageUrl || null
})

const activeContent = computed(() => {
  const translated = String(translatedContent.value || '').trim()
  return translated || String(props.content || '')
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
  <InlinePromptPanel
    :open="open"
    :label="normalizedFormat"
    :title="title"
    :image-url="resolvedImageUrl"
    :reveal-key="title"
    scroll-block="start"
    @close="emit('close')"
  >
    <template #label-icon><i :class="['ra', formatIcon]"></i></template>

    <template #aside>
      <div class="flex flex-wrap gap-2">
        <button
          v-if="canTake"
          type="button"
          :disabled="isTaking"
          class="tw-prompt-action tw-prompt-action--ghost"
          title="Take this item into your inventory"
          @click="emit('take')"
        >
          <i v-if="isTaking" class="ra ra-hourglass"></i>
          <Backpack v-else class="w-3.5 h-3.5" />
          <span>{{ isTaking ? 'Taking...' : 'Take' }}</span>
        </button>
        <button
          type="button"
          :disabled="!canTranslate || isTranslating"
          class="tw-prompt-action tw-prompt-action--ghost"
          :title="canTranslate ? `Translate to ${targetLanguage}` : 'Select a Bable Fish language first'"
          @click="handleTranslateTextLog"
        >
          <i class="ra ra-fish"></i>
          <span>{{ isTranslating ? 'Translating...' : 'Translate' }}</span>
        </button>
        <button
          v-if="configState.isTtsEnabled"
          type="button"
          :disabled="!canSpeak || audioService.isGenerating.value"
          class="tw-prompt-action tw-prompt-action--ghost"
          :title="audioService.isPlaying.value ? 'Stop reading' : 'Read text log aloud'"
          @click="handleSpeakTextLog"
        >
          <AudioLines v-if="audioService.isPlaying.value" class="w-3.5 h-3.5" />
          <i v-else class="ra ra-microphone"></i>
          <span>{{ audioService.isPlaying.value ? 'Stop' : 'Read' }}</span>
        </button>
      </div>
    </template>

    <div :class="['tw-readable', `tw-readable--${normalizedFormat.toLowerCase()}`]">
      <p v-if="translatedContent" class="tw-readable-note">
        Translated to {{ translatedLanguage || targetLanguage }}
      </p>
      <p v-html="formatEntityRefs(activeContent || 'No text content found.')"></p>
    </div>
  </InlinePromptPanel>
</template>
