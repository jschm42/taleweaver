import { ref, watch, type Ref } from 'vue'
import { audioService } from '@/services/audioService'
import { parseAssistantContent, type DialogueSegment } from '@/composables/useComicTurns'

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
  autoSpeakNarration?: Ref<boolean>
  autoSpeakDialogues?: Ref<boolean>
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

/**
 * The newest GM message that answers the player's latest action. Older messages never count:
 * otherwise the previous turn would be read again while the new narration is still on its way
 * (e.g. when history loaded after auto-speech was switched on and was never marked as spoken).
 */
function findLatestSpeakableAssistantMessage(messages: any[]): { index: number; message: { id?: string; timestamp?: Date; content: string } } | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const candidate = messages[index]
    if (!candidate) continue
    if (candidate.role === 'user') return null
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
  // Per streamed message: how many parsed segments were already queued for speech.
  const streamedSegmentCounts = new WeakMap<object, number>()
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
  // History usually arrives after mount (the list is replaced as a whole): it is old, not new.
  watch(() => messages.value, () => seedExistingMessagesAsSpoken())

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

    // Lines already spoken while the turn was streaming are skipped.
    const alreadyStreamed = streamedSegmentCounts.get(lastMsg) ?? 0
    const parsed = parseAssistantContent(lastMsg.content, sheet.value, [], npcMetadata.value)
    enqueueDialogues(parsed.dialogues.slice(alreadyStreamed))
  }

  function enqueueDialogues(dialogues: DialogueSegment[]): void {
    const speakNarration = options.autoSpeakNarration?.value ?? true
    const speakDialogues = options.autoSpeakDialogues?.value ?? true

    for (const dlg of dialogues) {
      if (!dlg.text.trim()) continue
      if (dlg.isNarration && !speakNarration) continue
      if (!dlg.isNarration && !speakDialogues) continue

      // One tag format ([tag]); the backend converts it for the active TTS provider.
      const textToSpeak = dlg.voiceTag ? `[${dlg.voiceTag}] ${dlg.text}` : dlg.text
      const isNpcLine = Boolean(dlg.speaker) && dlg.speaker !== 'Game Master'

      // The speaker is passed as a voice hint (resolved via npcMetadata), never
      // prefixed into the text, so the name is not read aloud.
      void audioService.enqueueSpeak(textToSpeak, {
        sceneDescription: currentSceneDescription.value,
        adventureId: sheet.value?.adventure_id || undefined,
        sessionId: sessionId.value,
        title: sheet.value?.adventure_title || undefined,
        sceneName: sheet.value?.current_scene || undefined,
        tone: sheet.value?.adventure_tone || undefined,
        npcMetadata: npcMetadata.value,
        voiceOverride: isNpcLine ? dlg.speaker : undefined,
        style: dlg.voiceTag || undefined,
      })
    }
  }

  /**
   * Speaks finished lines of the narration while it is still streaming, so the first voice
   * starts long before the turn is complete. Only complete lines are parsed, and the last
   * parsed segment is held back because the next chunk may still extend it.
   */
  function speakStreamingProgress(): void {
    if (status.value !== 'connecting' && status.value !== 'loading') return
    if (!audioService.autoSpeechEnabled.value || !audioService.isUnlocked.value) return
    if (isCombatActive.value) return

    const latest = findLatestSpeakableAssistantMessage(messages.value)
    if (!latest || isMessageAlreadySpoken(latest.message, latest.index)) return

    const content = String(latest.message.content || '')
    const completeText = content.slice(0, content.lastIndexOf('\n') + 1)
    if (!completeText.trim()) return

    const { dialogues } = parseAssistantContent(completeText, sheet.value, [], npcMetadata.value)
    const stableCount = dialogues.length - 1
    const spokenCount = streamedSegmentCounts.get(latest.message) ?? 0
    if (stableCount <= spokenCount) return

    streamedSegmentCounts.set(latest.message, stableCount)
    enqueueDialogues(dialogues.slice(spokenCount, stableCount))
  }

  watch(
    () => findLatestSpeakableAssistantMessage(messages.value)?.message.content,
    () => speakStreamingProgress(),
  )

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
