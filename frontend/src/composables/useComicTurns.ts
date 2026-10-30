import { ref, computed, watch, type Ref } from 'vue'
import DOMPurify from 'dompurify'
import type { ChatMessage } from '@/types'
import { buildComicPages, type ComicTurn, type DialogueSegment } from './comicPages'
import { renderEntityRefsHtml } from '@/utils/entityRefs'

export type { ComicExchange, ComicTurn, DialogueSegment } from './comicPages'

export interface UseComicTurnsOptions {
  messages: Ref<ChatMessage[]>
  entities: Ref<any[]>
  npcMetadata: Ref<Record<string, any>>
  sheet: Ref<any>
}

export function resolveNpcMetadata(nameOrId: string, metadataMap?: Record<string, any>) {
  if (!nameOrId || !metadataMap) return null
  const norm = String(nameOrId).trim().toLowerCase()
  if (metadataMap[nameOrId]) return metadataMap[nameOrId]
  if (metadataMap[norm]) return metadataMap[norm]
  for (const [k, v] of Object.entries(metadataMap)) {
    if (k.toLowerCase() === norm || (v as any)?.name?.toLowerCase() === norm || (v as any)?.id?.toLowerCase() === norm) {
      return v
    }
  }
  return null
}

export function resolveNpc(name: string, entities: any[] = [], metadataMap?: Record<string, any>) {
  if (!name) return null
  const norm = name.trim().toLowerCase()
  let foundEntity = (entities || []).find(
    (e) => e.entity_type === 'NPC' && (e.name?.toLowerCase() === norm || e.id?.toLowerCase() === norm)
  ) || (entities || []).find(
    (e) => e.name?.toLowerCase() === norm || e.id?.toLowerCase() === norm
  )

  if (!foundEntity) {
    foundEntity = (entities || []).find(
      (e) => e.name && (e.name.toLowerCase().startsWith(norm) || norm.startsWith(e.name.toLowerCase()))
    )
  }

  const meta = resolveNpcMetadata(name, metadataMap) || (foundEntity ? resolveNpcMetadata(foundEntity.id, metadataMap) || resolveNpcMetadata(foundEntity.name, metadataMap) : null)

  if (foundEntity || meta) {
    return {
      id: foundEntity?.id || meta?.id || norm,
      entity_type: foundEntity?.entity_type || meta?.entity_type || 'NPC',
      name: foundEntity?.name || meta?.name || name,
      description: foundEntity?.description || meta?.description || meta?.backstory || 'A character in this adventure.',
      image_url: foundEntity?.image_url || meta?.image_url || null,
      role: foundEntity?.role || meta?.role || null,
      hp: foundEntity?.hp != null ? foundEntity.hp : meta?.hp != null ? meta.hp : 100,
      max_hp: foundEntity?.max_hp != null ? foundEntity.max_hp : meta?.max_hp != null ? meta.max_hp : 100,
      stamina: foundEntity?.stamina != null ? foundEntity.stamina : meta?.stamina != null ? meta.stamina : 50,
      max_stamina: foundEntity?.max_stamina != null ? foundEntity.max_stamina : meta?.max_stamina != null ? meta.max_stamina : 50,
      mana: foundEntity?.mana != null ? foundEntity.mana : meta?.mana != null ? meta.mana : 50,
      max_mana: foundEntity?.max_mana != null ? foundEntity.max_mana : meta?.max_mana != null ? meta.max_mana : 50,
      inventory: Array.isArray(foundEntity?.inventory) ? foundEntity.inventory : Array.isArray(meta?.inventory) ? meta.inventory : [],
      stat_modifiers: foundEntity?.stat_modifiers || meta?.stat_modifiers || {},
      metadata_json: foundEntity?.metadata_json || meta?.metadata_json || {},
    }
  }
  return null
}

const NON_SPEAKER_LABELS = new Set([
  'note', 'warning', 'caution', 'info', 'location', 'status', 'time', 'goal', 'quest', 'tip'
])

// Labels the model sometimes puts in front of plain narration ("Narrator:", "**GM:**").
// A leading voice tag is captured so it survives the replacement.
const NARRATOR_LABEL = /^(\[[^\]\n]+\]\s*)?\**(?:narrator|narration|game master|gm)\**\s*:\**\s*/i
// Leftovers of weaker models the narration prompt forbids: braces and a closing "What will you do?".
const STRAY_BRACES = /[{}]+/g
const PLAYER_PROMPT_LINE = /^(?:\[[^\]\n]+\]\s*)*what (?:will|do|would) you do(?: next| now)?\s*\?*$/i

export function parseUserMessage(
  msg: ChatMessage | null | undefined,
  entities: any[] = [],
  metadataMap?: Record<string, any>
): {
  isDialogue: boolean
  targetName?: string | null
  targetEntity?: any
  speechText: string
} {
  if (!msg || !msg.content) return { isDialogue: false, speechText: '' }
  const raw = msg.content.trim()

  if (raw.toLowerCase().startsWith('/say to ')) {
    const after = raw.slice(8).trim()
    const colonIdx = after.indexOf(':')
    if (colonIdx > 0) {
      const targetCandidate = after.slice(0, colonIdx).trim()
      const speech = after.slice(colonIdx + 1).trim().replace(/^["“„»]+|["”«]+$/g, '')
      const targetEntity = resolveNpc(targetCandidate, entities, metadataMap)
      return {
        isDialogue: true,
        targetName: targetEntity?.name || targetCandidate,
        targetEntity,
        speechText: speech,
      }
    } else {
      for (const ent of (entities || [])) {
        if (ent.entity_type === 'NPC' && ent.name) {
          const entName = ent.name.toLowerCase()
          if (after.toLowerCase().startsWith(entName)) {
            const speech = after.slice(ent.name.length).trim().replace(/^[:,"“„»\s]+|["”«]+$/g, '')
            return {
              isDialogue: true,
              targetName: ent.name,
              targetEntity: resolveNpc(ent.name, entities, metadataMap),
              speechText: speech,
            }
          }
        }
      }
      return { isDialogue: true, speechText: after }
    }
  }

  if (raw.toLowerCase().startsWith('/say ')) {
    const speech = raw.slice(5).trim().replace(/^["“„»]+|["”«]+$/g, '')
    const colonIdx = speech.indexOf(':')
    if (colonIdx > 0) {
      const targetCandidate = speech.slice(0, colonIdx).trim()
      const targetEntity = resolveNpc(targetCandidate, entities, metadataMap)
      if (targetEntity) {
        return {
          isDialogue: true,
          targetName: targetEntity.name,
          targetEntity,
          speechText: speech.slice(colonIdx + 1).trim().replace(/^["“„»]+|["”«]+$/g, ''),
        }
      }
    }
    return { isDialogue: true, speechText: speech }
  }

  if ((raw.startsWith('"') || raw.startsWith('„') || raw.startsWith('“') || raw.startsWith('»')) && raw.length > 2) {
    const unquoted = raw.replace(/^["“„»]+|["”«]+$/g, '').trim()
    const colonIdx = unquoted.indexOf(':')
    if (colonIdx > 0) {
      const targetCandidate = unquoted.slice(0, colonIdx).trim()
      const targetEntity = resolveNpc(targetCandidate, entities, metadataMap)
      if (targetEntity) {
        return {
          isDialogue: true,
          targetName: targetEntity.name,
          targetEntity,
          speechText: unquoted.slice(colonIdx + 1).trim().replace(/^["“„»]+|["”«]+$/g, ''),
        }
      }
    }
    return { isDialogue: true, speechText: unquoted }
  }

  return { isDialogue: false, speechText: raw }
}

// One tag format everywhere: [lowercase tag]. Mirrors backend/engine/tts_tag_format.py.
const ANGLE_TAG = /<\s*([A-Za-z][A-Za-z '-]{0,40}?)\s*>/g
// Parentheses become tags only for known sounds, never for prose asides.
const PAREN_SOUND =
  /\(\s*(sighs?|laughs?|chuckles?|coughs?|gasps?|groans?|gulps|snorts|breath|heavy breath|exhales(?: sharply)?|inhales deeply|throat-clearing|clears throat|(?:short |long )?pause)\s*\)/gi

/** Rewrites <sigh> and (sigh) to [sigh] so tags look and sound the same everywhere. */
export function normalizeTagSyntax(text: string): string {
  if (!text) return ''
  return text
    .replace(ANGLE_TAG, (_m, tag: string) => `[${tag.trim().toLowerCase()}]`)
    .replace(PAREN_SOUND, (_m, tag: string) => `[${tag.trim().toLowerCase()}]`)
}

/** Voice tags are always English; only normalize casing and whitespace. */
export function normalizeVoiceTag(tag: string): string {
  return tag.trim().toLowerCase()
}

// Speaker line whose quote is closed too early: Name: [tag] "It" comes whether we see it."
const STRAY_CLOSING_QUOTE = /^([^"\n]*:\s*(?:\[[^\]\n]+\]\s*)?"[^"\n]+)"(\s+\p{Ll}[^"\n]*")$/gmu

/**
 * Drops a stray closing quote the model put after the first words of a speech. Only lines with
 * exactly three straight quotes whose text after the second one continues in lowercase and ends
 * with the third are touched, so a quote followed by narration stays split.
 */
export function repairStrayQuotes(text: string): string {
  return text.replace(STRAY_CLOSING_QUOTE, '$1$2')
}

// Sentence end (optionally closed by a quote) or a line break inside a captured speaker name.
const SPEAKER_SENTENCE_BOUNDARY = /[.!?…]["”»]?\s+|\n+/g

/**
 * The plain speaker pattern allows periods and spaces (for names like "Dr. Holmes"), so it can
 * swallow the preceding sentence: "She taps the pad. Betty: "…"". Moves such text in front of
 * the speaker onto its own line. A boundary only counts when the text before it is more than a
 * single word, so titles like "Dr." or "Mr." stay part of the name.
 */
function splitLeadingNarration(match: string, plainSpeaker?: string): string {
  if (!plainSpeaker) {
    return match
  }
  const speaker = plainSpeaker.trim()
  let cut = -1
  for (const boundary of speaker.matchAll(SPEAKER_SENTENCE_BOUNDARY)) {
    const start = boundary.index ?? 0
    const before = speaker.slice(cut < 0 ? 0 : cut, start).trim()
    if (boundary[0].includes('\n') || before.includes(' ')) {
      cut = start + boundary[0].length
    }
  }
  if (cut < 0) {
    return match
  }
  const speakerStart = match.indexOf(speaker)
  const narration = match.slice(0, speakerStart + cut).trim()
  const speech = match.slice(speakerStart + cut).trim()
  return narration ? `${narration}\n\n${speech}` : speech
}

export function parseAssistantContent(
  content: string,
  playerSheet?: any,
  entities: any[] = [],
  metadataMap?: Record<string, any>
): { narration: string; dialogues: DialogueSegment[] } {
  if (!content) return { narration: '', dialogues: [] }

  const dialogues: DialogueSegment[] = []
  let cleanContent = repairStrayQuotes(normalizeTagSyntax(content.replace(/\\n/g, '\n')).trim())

  // 1) Pre-split embedded/inline dialogues onto separate lines:
  // Detects: (Sentence end, voice tag, or line boundary) -> Speaker: "Dialogue"
  // Follow-up quotes joined only by whitespace, a vocal burst (<short pause>) or a voice tag
  // belong to the same speaker: Betty: "We're closed." <short pause> "Looking for something?"
  const inlineSpeechSplitter = /(?:^|\n|(?<=[.!?»”"“]\s+)|(?<=\]\s*))(?:\*\*([^*\n:]{2,60}?):\*\*|\*\*([^*\n:]{2,60}?)\*\*:|([A-Z\p{Lu}][\p{L}\p{N}_\s'’\-,.()]{1,60}?):)\s*(?:(?:\[[^\]\n]+\]|"[^"\n]+")\s*)?(["“„»][\s\S]*?["”«](?:[ \t]*(?:<[^>\n]{1,30}>|\[[^\]\n]{1,40}\])?[ \t]*["“„»][^"“”„«»\n]*["”«])*)/gu
  cleanContent = cleanContent.replace(
    inlineSpeechSplitter,
    (m, _bold1, _bold2, plainSpeaker?: string) => '\n\n' + splitLeadingNarration(m.trim(), plainSpeaker) + '\n\n'
  )

  const lines = cleanContent.split('\n')
  const narrationLines: string[] = []

  // Matches:
  // - [tag] Character Name: "Dialogue"
  // - Character Name: [tag] "Dialogue"
  // - Character Name: "[tag]" "Dialogue"
  // - Character Name: "[tag] "Dialogue"
  // - Character Name: "Dialogue"
  const speechRegex = /^(?:\[([^\]\n]+)\]\s*)?(?:(\*\*([^*:\n]+?):\*\*)|(\*\*([^*:\n]+?)\*\*:)|([\p{L}\p{N}_\s'’\-,.()]{2,60}):)\s*(.*)$/u

  for (const rawLine of lines) {
    // "Narrator: ..." is a format leak, not a character; keep only the prose.
    const line = rawLine.trim().replace(NARRATOR_LABEL, '$1').replace(STRAY_BRACES, '').trim()
    if (!line || PLAYER_PROMPT_LINE.test(line)) continue

    const match = line.match(speechRegex)
    if (match) {
      const isBold = Boolean(match[2] || match[4])
      let speakerName = (match[3] || match[5] || match[6] || '').trim()
      const rawSpeech = (match[7] || '').trim()
      let voiceTag = match[1] ? normalizeVoiceTag(match[1]) : undefined
      let speechText = rawSpeech

      // Check if rawSpeech starts with a voice tag (e.g. [amused] "Ah...", "[amused]" "Ah...", "[amused] "Ah...")
      const tagInSpeechMatch = speechText.match(/^"?\[([^\]\n]+)\]"?\s*"?\s*([\s\S]*)$/)
      if (tagInSpeechMatch) {
        if (!voiceTag) {
          voiceTag = normalizeVoiceTag(tagInSpeechMatch[1])
        }
        speechText = tagInSpeechMatch[2].trim()
      }

      const hasQuotes = /^["“„»]/.test(speechText) || /["”«]$/.test(speechText)
      // Several quoted parts ("A." <pause> "B.") keep their own quotes; stripping only the
      // outer ones would leave the inner ones unbalanced.
      const quoteCount = (speechText.match(/["“„»”«]/g) || []).length
      if (quoteCount <= 2) {
        speechText = speechText.replace(/^["“„»\s]+|["”«\s]+$/g, '').trim()
        // Clean accidental leftover opening quotes from malformed tags like "[amused] ""
        speechText = speechText.replace(/^["“„»\s]+/, '').trim()
      }

      // Guard against non-speaker labels (e.g. "Hinweis: ...", "Note: ...") when unquoted and not bold
      if (!hasQuotes && !isBold && NON_SPEAKER_LABELS.has(speakerName.toLowerCase())) {
        const last = dialogues[dialogues.length - 1]
        if (last && last.isNarration) {
          last.text += '\n\n' + line
        } else {
          dialogues.push({ speaker: 'Game Master', text: line, isNarration: true })
        }
        continue
      }

      let targetName: string | undefined = undefined
      let targetEntity: any = undefined

      const toMatch = speakerName.match(/^(.+?)\s+(?:to|\(to)\s+(.+?)\)?$/i)
      if (toMatch) {
        speakerName = toMatch[1].trim()
        targetName = toMatch[2].trim()
        targetEntity = resolveNpc(targetName, entities, metadataMap)
      }

      const resolvedNpc = resolveNpc(speakerName, entities, metadataMap)
      if (speakerName.toLowerCase() === 'you' || speakerName.toLowerCase() === (playerSheet?.name || '').toLowerCase()) {
        dialogues.push({
          speaker: playerSheet?.name || 'You',
          isPlayer: true,
          target: targetName,
          targetEntity,
          avatarUrl: playerSheet?.profile_image,
          text: speechText,
          voiceTag,
        })
      } else {
        dialogues.push({
          speaker: resolvedNpc?.name || speakerName,
          speakerEntity: resolvedNpc,
          target: targetName,
          targetEntity,
          avatarUrl: resolvedNpc?.image_url,
          isPlayer: false,
          text: speechText,
          voiceTag,
        })
      }
    } else {
      let narrationText = line
      let voiceTag: string | undefined = undefined
      // The first leading tag becomes the voice tag; further leading tags are dropped so the
      // prose (and its drop cap) always starts with a letter.
      const tagMatch = narrationText.match(/^\[([^\]\n]+)\](?:\s*\[[^\]\n]+\])*\s*(.*)$/)
      if (tagMatch) {
        voiceTag = normalizeVoiceTag(tagMatch[1])
        narrationText = tagMatch[2].trim()
      }

      const last = dialogues[dialogues.length - 1]
      if (last && last.isNarration) {
        // A lone voice tag line ("[calm]") leaves an empty narration to continue from.
        last.text = last.text ? `${last.text}\n\n${narrationText}` : narrationText
        // Use the voice tag from the first paragraph if the new one doesn't have one
        if (voiceTag && !last.voiceTag) {
          last.voiceTag = voiceTag
        }
      } else {
        dialogues.push({ speaker: 'Game Master', text: narrationText, isNarration: true, voiceTag })
      }
    }
  }

  // To keep compatibility, extract the first narration block as .narration
  // though the UI should iterate dialogues.
  const firstNarration = dialogues.find(d => d.isNarration)
  return {
    narration: firstNarration ? firstNarration.text : '',
    dialogues,
  }
}

const PAUSE_TAG = /\s*\[(?:short |medium |long )?pause\]\s*/gi
const QUOTE_CHARS = /["„“”«»]/

/** Escapes the text and renders voice tags, bold text and object ids as markup. */
export function renderFormattedHtml(text: string): string {
  if (!text) return ''
  // Pauses only shape the speech output and are not shown.
  const displayText = normalizeTagSyntax(text).replace(PAUSE_TAG, ' ').trim()
  const escaped = displayText.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
  const withVoiceTags = escaped.replace(/(\[[^\]\n]+\])/g, (match, tag) => {
    const raw = tag.slice(1, -1).trim()
    if (/^DEBUG/i.test(raw)) return match
    const en = normalizeVoiceTag(raw)
    return `<span class="comic-voice-tag">${en}</span>`
  })
  const withBolds = withVoiceTags.replace(/\*\*(.*?)\*\*/g, '<strong class="text-amber-200 font-bold">$1</strong>')
  const withObjectIds = renderEntityRefsHtml(withBolds, 'comic-object-tag')
    // Merged narration paragraphs keep their breaks instead of running together into one block.
    // A short gap (not a full empty line) lets the next paragraph still flow beside a drop cap.
    .replace(/\n{2,}/g, '<span class="tw-para-break"></span>')
    .replace(/\n/g, '<br>')

  return DOMPurify.sanitize(withObjectIds, {
    ALLOWED_TAGS: ['span', 'strong', 'em', 'br', 'div'],
    ALLOWED_ATTR: ['class'],
  })
}

/** Verbatim text (tw.story.narrate_raw): only escaped, line breaks kept, no markup parsing. */
export function renderPlainHtml(text: string): string {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n{2,}/g, '<span class="tw-para-break"></span>')
    .replace(/\n/g, '<br>')
}

/**
 * Dialogue bubble text: like renderFormattedHtml, wrapped in quotes unless the line already
 * carries its own (e.g. `"Coffee?" She chews slower.`).
 */
export function renderDialogueHtml(text: string): string {
  const html = renderFormattedHtml(text)
  if (!html || QUOTE_CHARS.test(text)) {
    return html
  }
  return `&quot;${html}&quot;`
}

export function useComicTurns(options: UseComicTurnsOptions) {
  const { messages, entities, npcMetadata, sheet } = options
  const viewingTurnIndex = ref<number | null>(null)

  const gameTurns = computed<ComicTurn[]>(() =>
    buildComicPages(messages.value || [], {
      parseUser: (msg) => parseUserMessage(msg, entities.value, npcMetadata.value),
      parseAssistant: (content) =>
        parseAssistantContent(content, sheet.value, entities.value, npcMetadata.value),
    })
  )

  const activeTurnIndex = computed(() => {
    if (viewingTurnIndex.value !== null && viewingTurnIndex.value >= 0 && viewingTurnIndex.value < gameTurns.value.length) {
      return viewingTurnIndex.value
    }
    return Math.max(0, gameTurns.value.length - 1)
  })

  const activeTurn = computed<ComicTurn | null>(() => {
    if (!gameTurns.value.length) return null
    return gameTurns.value[activeTurnIndex.value] || null
  })

  watch(
    () => messages.value.length,
    () => {
      if (viewingTurnIndex.value === null || viewingTurnIndex.value >= gameTurns.value.length - 2) {
        viewingTurnIndex.value = null
      }
    }
  )

  function goToTurn(idx: number) {
    viewingTurnIndex.value = Math.max(0, Math.min(gameTurns.value.length - 1, idx))
  }

  function goToLatestTurn() {
    viewingTurnIndex.value = null
  }

  const activeSpeakers = computed<Set<string>>(() => {
    const speakers = new Set<string>()
    // Highlight the NPCs speaking in the latest exchange of the page.
    const latestExchange = activeTurn.value?.exchanges[activeTurn.value.exchanges.length - 1]
    if (!latestExchange) return speakers
    for (const d of latestExchange.dialogues) {
      if (d.isPlayer) continue
      if (d.speaker) speakers.add(d.speaker.toLowerCase())
      if (d.speakerEntity?.id) speakers.add(String(d.speakerEntity.id).toLowerCase())
      if (d.speakerEntity?.name) speakers.add(String(d.speakerEntity.name).toLowerCase())
    }
    return speakers
  })

  function isNpcSpeaking(npc: any): boolean {
    if (!npc) return false
    const nameMatch = npc.name && activeSpeakers.value.has(npc.name.toLowerCase())
    const idMatch = npc.id && activeSpeakers.value.has(String(npc.id).toLowerCase())
    return Boolean(nameMatch || idMatch)
  }

  const npcs = computed(() => {
    const worldNpcs = (entities.value || [])
      .filter((e) => String(e.entity_type || e.type || '').toUpperCase() === 'NPC')
      .map((e) => {
        const meta = resolveNpcMetadata(e.name, npcMetadata.value) || resolveNpcMetadata(e.id, npcMetadata.value)
        return {
          ...e,
          entity_type: 'NPC',
          image_url: e.image_url || meta?.image_url || null,
          role: e.role || meta?.role || null,
        }
      })

    // The hero is not listed here; portrait and bio live in the character sheet's Hero tab.
    return [...worldNpcs].sort((a, b) => {
      const aSpeaking = isNpcSpeaking(a) ? 1 : 0
      const bSpeaking = isNpcSpeaking(b) ? 1 : 0
      return bSpeaking - aSpeaking
    })
  })

  function getEntityForHover(nameOrEntity: any) {
    if (typeof nameOrEntity === 'object' && nameOrEntity && nameOrEntity.id) {
      const cloned = { ...nameOrEntity }
      if (!cloned.entity_type) cloned.entity_type = 'NPC'
      if (!cloned.description) {
        const meta = resolveNpcMetadata(cloned.name || cloned.id, npcMetadata.value)
        if (meta?.description || meta?.backstory) cloned.description = meta.description || meta.backstory
      }
      return cloned
    }
    const name = typeof nameOrEntity === 'string' ? nameOrEntity.trim() : String(nameOrEntity?.name || '').trim()
    const norm = name.toLowerCase()
    if (norm === 'you' || norm === (sheet.value?.name || '').toLowerCase() || norm === `you (${sheet.value?.name || ''})`.toLowerCase()) {
      return {
        id: 'PLAYER',
        name: sheet.value?.name || 'You',
        entity_type: 'NPC',
        description: sheet.value?.description || 'Your hero character.',
        image_url: sheet.value?.profile_image || null,
        role: sheet.value?.role || 'Hero',
        hp: typeof sheet.value?.hp === 'number' ? sheet.value?.hp : 100,
        max_hp: typeof sheet.value?.max_hp === 'number' ? sheet.value?.max_hp : 100,
        mana: typeof sheet.value?.mana === 'number' ? sheet.value?.mana : 50,
        max_mana: typeof sheet.value?.max_mana === 'number' ? sheet.value?.max_mana : 50,
        stamina: typeof sheet.value?.stamina === 'number' ? sheet.value?.stamina : 50,
        max_stamina: typeof sheet.value?.max_stamina === 'number' ? sheet.value?.max_stamina : 50,
        inventory: Array.isArray(sheet.value?.inventory) ? sheet.value?.inventory : [],
        stats: sheet.value?.stats,
      }
    }
    const found = npcs.value.find((n) => n.name?.toLowerCase() === norm || n.id?.toLowerCase() === norm)
    if (found) {
      return {
        ...found,
        entity_type: 'NPC',
        description:
          found.description ||
          resolveNpcMetadata(found.name || found.id, npcMetadata.value)?.description ||
          resolveNpcMetadata(found.name || found.id, npcMetadata.value)?.backstory ||
          'A character in this adventure.',
      }
    }
    const resolved = resolveNpc(name, entities.value, npcMetadata.value)
    if (resolved) return resolved
    return { name, entity_type: 'NPC', description: 'A character in this adventure.' }
  }

  return {
    gameTurns,
    activeTurnIndex,
    activeTurn,
    viewingTurnIndex,
    activeSpeakers,
    npcs,
    goToTurn,
    goToLatestTurn,
    isNpcSpeaking,
    getEntityForHover,
    renderFormattedHtml,
  }
}
