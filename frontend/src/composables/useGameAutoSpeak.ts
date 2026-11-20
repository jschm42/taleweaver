import { ref, watch, type Ref } from 'vue'
import { audioService } from '@/services/audioService'
import { parseAssistantContent, parseUserMessage, type DialogueSegment } from '@/composables/useComicTurns'
import { rawAssistantContent } from '@/composables/comicPages'
import { resolveEntityRefsText } from '@/utils/entityRefs'
import type { AutoSpeakSettings } from '@/types/tts'
import { currentTurnAssistantMessages, unspokenTurnMessages } from '@/utils/autoSpeakQueue'

const AUTO_SPEAK_DEBOUNCE_MS = 350
/** Lets the travel overlay finish fading out before the new scene's narration starts. */
const DEFERRED_SPEECH_DELAY_MS = 500
const MAX_TRACKED_SIGNATURES = 200
/** Speech fades out this fast when a fight opens. */
const COMBAT_SPEECH_FADE_SECONDS = 0.4

type AutoSpeakOptions = {
  messages: Ref<any[]>
  status: Ref<string>
  inputLocked: Ref<boolean>
  isCombatActive: Ref<boolean>
  currentSceneDescription: Ref<string>
  sheet: Ref<any>
  npcMetadata: Ref<Record<string, any>>
  sessionId: Ref<string>
  /** Which voices are spoken; a missing setting falls back to speaking everything except system messages. */
  autoSpeakSettings?: Ref<AutoSpeakSettings>
  /** While true (e.g. a choice dialog waits for the player), nothing is spoken and running speech stops. */
  speechSuppressed?: Ref<boolean>
  /** While true (tw.audio.stop_speech() until the next action), new text is not read and is not
   *  replayed later; unlike speechSuppressed, running speech is left to its own fade-out. */
  speechHeld?: Ref<boolean>
  /** While true (e.g. the travel overlay is shown), new text waits and is spoken once it turns false. */
  speechDeferred?: Ref<boolean>
  /** True while the player walks through an exit: that overlay only stops speech, nothing is replayed. */
  playerTravel?: Ref<boolean>
}

function computeContentHash(content: string): string {
  const normalized = String(content || '').trim()
  let hash = 5381
  for (let i = 0; i < normalized.length; i++) {
    hash = ((hash << 5) + hash) ^ normalized.charCodeAt(i)
  }
  return `${normalized.length}_${(hash >>> 0).toString(36)}`
}

/** System notes may carry markdown, emoji and entity references that must not be read aloud. */
function speakableSystemText(content: string): string {
  return resolveEntityRefsText(content)
    .replace(/\p{Extended_Pictographic}/gu, '')
    .replace(/[*_`#>~|]+/g, '')
    .replace(/\s+/g, ' ')
    .trim()
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
function findLatestSpeakableAssistantMessage(messages: any[]): { index: number; message: { id?: string; timestamp?: Date; content: string; raw?: boolean } } | null {
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
  // Content hashes of the lines spoken since the player's latest action began (a request or an
  // opened dialog). Only these may be read again when a script teleport's overlay cuts them off.
  // Hashes, not positions: a history reload after a turn shifts the message indices.
  const actionSpokenHashes = new Set<string>()

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
    actionSpokenHashes.add(hash)
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

  /** Lets a message be read again (its speech was cut off before it finished). */
  function unmarkMessageAsSpoken(message: { id?: string; content: string }, index: number): void {
    spokenSignatures.delete(getMessageSignature(message, index))
    if (message.id) spokenSignatures.delete(`id:${message.id}`)
    spokenSignatures.delete(`hash:${computeContentHash(message.content)}`)
    if (lastSpokenContent.value === String(message.content || '').trim()) {
      lastSpokenSignature.value = null
      lastSpokenContent.value = null
    }
    streamedSegmentCounts.delete(message)
  }

  function seedExistingMessagesAsSpoken(): void {
    if (!Array.isArray(messages.value)) return
    for (let i = 0; i < messages.value.length; i++) {
      const msg = messages.value[i]
      if (msg && msg.role === 'assistant' && !msg.is_debug && String(msg.content || '').trim()) {
        markMessageAsSpoken(msg, i)
      }
    }
    // Old history was never spoken in this view, so it can never be replayed either.
    actionSpokenHashes.clear()
  }

  // Pre-seed any existing messages on initial mount so old log history isn't auto-spoken.
  seedExistingMessagesAsSpoken()
  // History usually arrives after mount: its first arrival is old, not new. Later reloads (e.g.
  // after a turn or scene change) may carry fresh GM text and must not be marked as spoken.
  let historySeeded = messages.value.length > 0
  watch(() => messages.value.length, (length) => {
    if (historySeeded || length === 0) return
    historySeeded = true
    seedExistingMessagesAsSpoken()
  })

  function speakLatestAssistantMessage(params: { force?: boolean } = {}): void {
    const { force = false } = params
    if (!audioService.autoSpeechEnabled.value) return
    if (!audioService.isUnlocked.value) return
    if (isCombatActive.value) return
    if (!force && (status.value === 'connecting' || status.value === 'loading' || inputLocked.value)) return
    // Not marked as spoken: the deferral watcher speaks it once the overlay is gone.
    if (options.speechDeferred?.value) return

    const now = Date.now()
    if (!force && now - lastAutoSpeakAt.value < AUTO_SPEAK_DEBOUNCE_MS) return

    // Every GM message of this turn that was not read yet, in order (script lines, narration, ...).
    let pending = unspokenTurnMessages(messages.value, isMessageAlreadySpoken)
    if (force && pending.length === 0) {
      const latest = findLatestSpeakableAssistantMessage(messages.value)
      pending = latest ? [latest] : []
    }
    if (pending.length === 0) return

    lastAutoSpeakAt.value = now
    for (const { index, message } of pending) speakWholeMessage(message, index)
  }

  function isSilenced(): boolean {
    return Boolean(options.speechSuppressed?.value || options.speechHeld?.value)
  }

  /** Reads one message, skipping the lines already spoken while it was streaming. */
  function speakWholeMessage(message: { id?: string; content: string; raw?: boolean }, index: number): void {
    markMessageAsSpoken(message, index)
    // Text that arrives while speech is suppressed or held is skipped, not replayed later.
    if (isSilenced()) return
    const alreadyStreamed = streamedSegmentCounts.get(message) ?? 0
    const parsed = message.raw
      ? rawAssistantContent(message.content)
      : parseAssistantContent(message.content, sheet.value, [], npcMetadata.value)
    enqueueDialogues(parsed.dialogues.slice(alreadyStreamed))
  }

  function isVoiceEnabled(dlg: DialogueSegment): boolean {
    const settings = options.autoSpeakSettings?.value
    if (dlg.isNarration) return settings?.gm ?? true
    if (dlg.isPlayer) return settings?.protagonist ?? true
    return settings?.npcs ?? true
  }

  /** Without a speaker the line is read in the Game Master's voice. */
  function enqueueSpeech(text: string, speaker?: string, voiceTag?: string): void {
    // One tag format ([tag]); the backend converts it for the active TTS provider.
    const textToSpeak = voiceTag ? `[${voiceTag}] ${text}` : text
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
      voiceOverride: speaker,
      speaker,
      style: voiceTag || undefined,
    })
  }

  function enqueueDialogues(dialogues: DialogueSegment[]): void {
    if (isSilenced()) return
    for (const dlg of dialogues) {
      if (!dlg.text.trim() || !isVoiceEnabled(dlg)) continue
      const isNpcLine = Boolean(dlg.speaker) && dlg.speaker !== 'Game Master'
      enqueueSpeech(dlg.text, isNpcLine ? dlg.speaker : undefined, dlg.voiceTag)
    }
  }

  function canSpeakNow(): boolean {
    if (!audioService.autoSpeechEnabled.value || !audioService.isUnlocked.value) return false
    return !isCombatActive.value && !isSilenced()
  }

  /** The player's own spoken line (/say or quoted speech), read in the protagonist's voice. */
  function speakPlayerLine(message: any): void {
    if (!canSpeakNow()) return
    const { isDialogue, speechText } = parseUserMessage(message, [], npcMetadata.value)
    if (!isDialogue || !speechText.trim()) return
    // The player's name resolves to the protagonist's voice via npcMetadata.
    enqueueDialogues([{ speaker: sheet.value?.name || 'You', text: speechText, isPlayer: true }])
  }

  /** Dice rolls, status updates and other system notes, read in the Game Master's voice. */
  function speakSystemMessage(message: any): void {
    if (!options.autoSpeakSettings?.value.system || message?.is_debug) return
    if (!canSpeakNow()) return
    const text = speakableSystemText(String(message?.content || ''))
    if (text) enqueueSpeech(text)
  }

  // A single message the player just sent (not a history load) is spoken right away, so it is
  // heard before the GM's answer; plain actions ("look around") are not dialogue and stay silent.
  // A single new system note is spoken the same way when the player wants to hear them.
  watch(() => messages.value.length, (length, previous) => {
    if (!historySeeded || length !== previous + 1) return
    const last = messages.value[length - 1]
    if (last?.role === 'user') speakPlayerLine(last)
    if (last?.role === 'system') speakSystemMessage(last)
  })

  /**
   * Speaks finished lines of the narration while it is still streaming, so the first voice
   * starts long before the turn is complete. Only complete lines are parsed, and the last
   * parsed segment is held back because the next chunk may still extend it.
   */
  function speakStreamingProgress(): void {
    if (status.value !== 'connecting' && status.value !== 'loading') return
    if (options.speechDeferred?.value) return
    if (!audioService.autoSpeechEnabled.value || !audioService.isUnlocked.value) return
    if (isCombatActive.value) return

    const latest = findLatestSpeakableAssistantMessage(messages.value)
    if (!latest || isMessageAlreadySpoken(latest.message, latest.index)) return
    // Earlier GM messages of this turn (e.g. script lines before a chained narration) go first.
    for (const earlier of unspokenTurnMessages(messages.value, isMessageAlreadySpoken)) {
      if (earlier.index !== latest.index) speakWholeMessage(earlier.message, earlier.index)
    }
    // Raw script narration arrives complete and is spoken as one block once the turn ends.
    if (latest.message.raw) return

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
      actionSpokenHashes.clear()
      spokenSignatures.clear()
      lastSpokenSignature.value = null
      lastSpokenContent.value = null
      lastAutoSpeakAt.value = 0
      seedExistingMessagesAsSpoken()
      // The new session's history may still be loading; its first arrival is old again.
      historySeeded = messages.value.length > 0
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

  // A fight takes over the screen: the narration still being read ends (short fade, queue
  // dropped). No new line starts while the fight runs, see the isCombatActive guards above.
  watch(isCombatActive, (active) => {
    if (active) void audioService.fadeOutAndStop(COMBAT_SPEECH_FADE_SECONDS)
  })

  watch(() => options.speechSuppressed?.value, (suppressed) => {
    if (!suppressed) return
    audioService.stop()
    // Everything after an opened dialog is the answer to the player's choice.
    actionSpokenHashes.clear()
  })

  // A new request is a new action: lines of the previous one are never replayed.
  watch(() => status.value, (newStatus, oldStatus) => {
    const isBusy = (value: string): boolean => value === 'connecting' || value === 'loading'
    if (!isBusy(newStatus) || isBusy(oldStatus)) return
    // Everything shown so far belongs to earlier actions. Silent commands (an exit click sends
    // /traverse_exit) add no player message, so without this the previous scene's narration
    // would still count as part of this turn and be read again after the travel overlay.
    seedExistingMessagesAsSpoken()
    actionSpokenHashes.clear()
    // The player acts again: a tw.audio.stop_speech() hold of the last action ends.
    if (options.speechHeld) options.speechHeld.value = false
  })

  // Leaving the scene silences the old narration; the new scene is read once the overlay is gone.
  let deferredSpeechTimer: ReturnType<typeof setTimeout> | null = null
  watch(() => options.speechDeferred?.value, (deferred) => {
    if (deferredSpeechTimer) clearTimeout(deferredSpeechTimer)
    deferredSpeechTimer = null
    if (deferred) {
      audioService.stop()
      // Walking through an exit leaves the old scene's text behind.
      if (options.playerTravel?.value) return
      // A script teleport cut off the lines of the action that caused it: read them once the
      // new scene is shown. Lines of earlier actions stay silent.
      for (const { message, index } of currentTurnAssistantMessages(messages.value)) {
        if (actionSpokenHashes.has(computeContentHash(message.content))) {
          unmarkMessageAsSpoken(message, index)
        }
      }
      return
    }
    deferredSpeechTimer = setTimeout(() => {
      deferredSpeechTimer = null
      // A chained turn may already be streaming: its progress reader also catches up on the
      // lines that were cut off by the overlay.
      const busy = status.value === 'connecting' || status.value === 'loading'
      if (busy) {
        speakStreamingProgress()
        return
      }
      speakLatestAssistantMessage()
      // The cut-off lines are queued again; the next scene change must not repeat them.
      actionSpokenHashes.clear()
    }, DEFERRED_SPEECH_DELAY_MS)
  })

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
