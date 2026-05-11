import { ref, watch, type Ref } from 'vue'
import { audioService } from '@/services/audioService'

const AUTO_SPEAK_DEBOUNCE_MS = 350

type AutoSpeakOptions = {
  messages: Ref<any[]>
  status: Ref<string>
  inputLocked: Ref<boolean>
  isCombatActive: Ref<boolean>
  currentSceneDescription: Ref<string>
  sheet: Ref<any>
  npcMetadata: Ref<Record<string, any>>
  sessionId: Ref<string>
}

function getMessageSignature(message: { timestamp?: Date; content: string }, index: number): string {
  const ts = message.timestamp instanceof Date ? message.timestamp.toISOString() : ''
  return `${index}|${ts}`
}

function findLatestSpeakableAssistantMessage(messages: any[]): { index: number; message: { timestamp?: Date; content: string } } | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const candidate = messages[index]
    if (!candidate) continue
    if (candidate.role !== 'assistant') continue
    if (candidate.is_debug) continue
    if (!String(candidate.content || '').trim()) continue
    return { index, message: candidate }
  }
  return null
}

export function useGameAutoSpeak(options: AutoSpeakOptions): { speakLatestAssistantMessage: (params?: { force?: boolean }) => void } {
  const {
    messages,
    status,
    inputLocked,
    isCombatActive,
    currentSceneDescription,
    sheet,
    npcMetadata,
    sessionId,
  } = options

  const lastAutoSpokenSignature = ref<string | null>(null)
  const lastAutoSpeakAt = ref(0)

  function speakLatestAssistantMessage(params: { force?: boolean } = {}): void {
    const { force = false } = params
    if (!audioService.autoSpeechEnabled.value) return
    if (!audioService.isUnlocked.value) return
    if (isCombatActive.value) return
    if (!force && (status.value === 'connecting' || status.value === 'loading')) return

    const now = Date.now()
    if (!force && now - lastAutoSpeakAt.value < AUTO_SPEAK_DEBOUNCE_MS) return

    const latest = findLatestSpeakableAssistantMessage(messages.value)
    if (!latest) return
    const { index, message: lastMsg } = latest

    const signature = getMessageSignature(lastMsg, index)
    if (!force && signature === lastAutoSpokenSignature.value) return

    lastAutoSpeakAt.value = now
    lastAutoSpokenSignature.value = signature

    void audioService.enqueueSpeak(lastMsg.content, {
      sceneDescription: currentSceneDescription.value,
      adventureId: sheet.value?.adventure_id || undefined,
      sessionId: sessionId.value,
      title: sheet.value?.adventure_title || undefined,
      sceneName: sheet.value?.current_scene || undefined,
      tone: sheet.value?.adventure_tone || undefined,
      npcMetadata: npcMetadata.value,
    })
  }

  watch(() => inputLocked.value, (isLocked) => {
    if (isLocked || status.value === 'connecting' || status.value === 'loading') return
    speakLatestAssistantMessage()
  })

  watch(() => messages.value.length, (newLength, oldLength) => {
    if (newLength <= oldLength) return
    const appended = messages.value[newLength - 1] as any
    if (!appended) return
    if (appended.role !== 'assistant') return
    if (appended.is_debug) return
    if (!String(appended.content || '').trim()) return
    speakLatestAssistantMessage()
  })

  watch(
    () => {
      const latest = findLatestSpeakableAssistantMessage(messages.value)
      if (!latest) return ''
      return `${latest.index}|${String(latest.message.content || '').trim()}`
    },
    (snapshot, previous) => {
      if (!snapshot || snapshot === previous) return
      speakLatestAssistantMessage()
    }
  )

  watch(
    () => status.value,
    (newStatus, oldStatus) => {
      const wasBusy = oldStatus === 'connecting' || oldStatus === 'loading'
      const isReady = newStatus === 'connected' || newStatus === 'completed'
      if (!wasBusy || !isReady) return
      speakLatestAssistantMessage()
    }
  )

  watch(() => audioService.autoSpeechEnabled.value, (enabled) => {
    if (enabled) {
      setTimeout(() => {
        if (!audioService.autoSpeechEnabled.value) return
        speakLatestAssistantMessage({ force: true })
      }, AUTO_SPEAK_DEBOUNCE_MS)
      return
    }

    lastAutoSpokenSignature.value = null
    lastAutoSpeakAt.value = 0
    audioService.stop()
  })

  return { speakLatestAssistantMessage }
}
