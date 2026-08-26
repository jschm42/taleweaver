import { ref, watch, type Ref } from 'vue'
import { audioService } from '@/services/audioService'

const AUTO_SPEAK_DEBOUNCE_MS = 350
const MAX_TRACKED_SIGNATURES = 200

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

function computeContentHash(content: string): string {
  const normalized = String(content || '').trim()
  let hash = 5381
  for (let i = 0; i < normalized.length; i++) {
    hash = ((hash << 5) + hash) ^ normalized.charCodeAt(i)
  }
  return `${normalized.length}_${(hash >>> 0).toString(36)}`
}

function getMessageSignature(message: { id?: string; content: string }, index: number): string {
  const hash = computeContentHash(message.content)
  if (message.id) {
    return `id:${message.id}|${hash}`
  }
  return `idx:${index}|${hash}`
}

function findLatestSpeakableAssistantMessage(messages: any[]): { index: number; message: { id?: string; timestamp?: Date; content: string } } | null {
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

  const spokenSignatures = new Set<string>()
  const lastSpokenSignature = ref<string | null>(null)
  const lastSpokenContent = ref<string | null>(null)
  const lastAutoSpeakAt = ref(0)

  function pruneSpokenSignatures(): void {
    if (spokenSignatures.size > MAX_TRACKED_SIGNATURES) {
      const entries = Array.from(spokenSignatures)
      const toRemove = entries.slice(0, entries.length - MAX_TRACKED_SIGNATURES)
      for (const entry of toRemove) {
        spokenSignatures.delete(entry)
      }
    }
  }

  function markMessageAsSpoken(message: { id?: string; content: string }, index: number): void {
    const signature = getMessageSignature(message, index)
    spokenSignatures.add(signature)
    if (message.id) {
      spokenSignatures.add(`id:${message.id}`)
    }
    const hash = computeContentHash(message.content)
    spokenSignatures.add(`hash:${hash}`)
    lastSpokenSignature.value = signature
    lastSpokenContent.value = String(message.content || '').trim()
    pruneSpokenSignatures()
  }

  function isMessageAlreadySpoken(message: { id?: string; content: string }, index: number): boolean {
    const signature = getMessageSignature(message, index)
    if (spokenSignatures.has(signature)) return true
    if (message.id && spokenSignatures.has(`id:${message.id}`)) return true
    const hash = computeContentHash(message.content)
    if (spokenSignatures.has(`hash:${hash}`)) return true
    if (signature === lastSpokenSignature.value) return true
    const trimmed = String(message.content || '').trim()
    if (lastSpokenContent.value && trimmed === lastSpokenContent.value) return true
    return false
  }

  function seedExistingMessagesAsSpoken(): void {
    if (!Array.isArray(messages.value)) return
    for (let i = 0; i < messages.value.length; i++) {
      const msg = messages.value[i]
      if (msg && msg.role === 'assistant' && !msg.is_debug && String(msg.content || '').trim()) {
        markMessageAsSpoken(msg, i)
      }
    }
  }

  // Pre-seed any existing messages on initial mount so old log history isn't auto-spoken.
  seedExistingMessagesAsSpoken()

  function speakLatestAssistantMessage(params: { force?: boolean } = {}): void {
    const { force = false } = params
    if (!audioService.autoSpeechEnabled.value) return
    if (!audioService.isUnlocked.value) return
    if (isCombatActive.value) return
    if (!force && (status.value === 'connecting' || status.value === 'loading' || inputLocked.value)) return

    const now = Date.now()
    if (!force && now - lastAutoSpeakAt.value < AUTO_SPEAK_DEBOUNCE_MS) return

    const latest = findLatestSpeakableAssistantMessage(messages.value)
    if (!latest) return
    const { index, message: lastMsg } = latest

    if (!force && isMessageAlreadySpoken(lastMsg, index)) return

    lastAutoSpeakAt.value = now
    markMessageAsSpoken(lastMsg, index)

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

  watch(() => sessionId.value, (newSessionId, oldSessionId) => {
    if (newSessionId !== oldSessionId) {
      spokenSignatures.clear()
      lastSpokenSignature.value = null
      lastSpokenContent.value = null
      lastAutoSpeakAt.value = 0
      seedExistingMessagesAsSpoken()
    }
  })

  watch(() => inputLocked.value, (isLocked) => {
    if (isLocked || status.value === 'connecting' || status.value === 'loading') return
    speakLatestAssistantMessage()
  })

  watch(
    () => status.value,
    (newStatus, oldStatus) => {
      const wasBusy = oldStatus === 'connecting' || oldStatus === 'loading'
      const isReady = newStatus === 'connected' || newStatus === 'completed'
      if (!wasBusy || !isReady || inputLocked.value) return
      speakLatestAssistantMessage()
    }
  )

  watch(
    () => {
      const latest = findLatestSpeakableAssistantMessage(messages.value)
      if (!latest) return ''
      return `${latest.message.id || latest.index}|${computeContentHash(latest.message.content)}`
    },
    (snapshot, previous) => {
      if (!snapshot || snapshot === previous) return
      if (inputLocked.value || status.value === 'connecting' || status.value === 'loading') return
      speakLatestAssistantMessage()
    }
  )

  watch(() => audioService.autoSpeechEnabled.value, (enabled) => {
    if (enabled) {
      // Pre-seed all current messages so autoplay only triggers for subsequent turns.
      seedExistingMessagesAsSpoken()
      return
    }

    // On disable: reset state and stop any running audio.
    lastSpokenSignature.value = null
    lastSpokenContent.value = null
    lastAutoSpeakAt.value = 0
    audioService.stop()
  })

  return { speakLatestAssistantMessage }
}
