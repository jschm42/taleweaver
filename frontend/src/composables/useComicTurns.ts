import { ref, computed, watch, type Ref } from 'vue'
import DOMPurify from 'dompurify'
import type { ChatMessage } from '@/types'

export interface DialogueSegment {
  speaker: string
  speakerEntity?: any
  target?: string
  targetEntity?: any
  avatarUrl?: string | null
  isPlayer?: boolean
  text: string
  isAction?: boolean
}

export interface ComicTurn {
  index: number
  userMessage?: ChatMessage | null
  userIsDialogue?: boolean
  userTargetName?: string | null
  userTargetEntity?: any
  userSpeechText?: string
  assistantMessage?: ChatMessage | null
  systemMessages: ChatMessage[]
  licenseMessage?: ChatMessage | null
  narration: string
  dialogues: DialogueSegment[]
  revealedItemIds: string[]
  timestamp?: string
}

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
  const foundEntity = (entities || []).find(
    (e) => e.entity_type === 'NPC' && (e.name?.toLowerCase() === norm || e.id?.toLowerCase() === norm)
  )
  const meta = resolveNpcMetadata(name, metadataMap) || (foundEntity ? resolveNpcMetadata(foundEntity.id, metadataMap) || resolveNpcMetadata(foundEntity.name, metadataMap) : null)

  if (foundEntity || meta) {
    return {
      id: foundEntity?.id || meta?.id || norm,
      entity_type: 'NPC',
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
      const speech = after.slice(colonIdx + 1).trim().replace(/^["“]|["”]$/g, '')
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
            const speech = after.slice(ent.name.length).trim().replace(/^[:,"“\s]+|["”]$/g, '')
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
    const speech = raw.slice(5).trim().replace(/^["“]|["”]$/g, '')
    const colonIdx = speech.indexOf(':')
    if (colonIdx > 0) {
      const targetCandidate = speech.slice(0, colonIdx).trim()
      const targetEntity = resolveNpc(targetCandidate, entities, metadataMap)
      if (targetEntity) {
        return {
          isDialogue: true,
          targetName: targetEntity.name,
          targetEntity,
          speechText: speech.slice(colonIdx + 1).trim().replace(/^["“]|["”]$/g, ''),
        }
      }
    }
    return { isDialogue: true, speechText: speech }
  }

  if (raw.startsWith('"') && raw.endsWith('"') && raw.length > 2) {
    const unquoted = raw.slice(1, -1).trim()
    const colonIdx = unquoted.indexOf(':')
    if (colonIdx > 0) {
      const targetCandidate = unquoted.slice(0, colonIdx).trim()
      const targetEntity = resolveNpc(targetCandidate, entities, metadataMap)
      if (targetEntity) {
        return {
          isDialogue: true,
          targetName: targetEntity.name,
          targetEntity,
          speechText: unquoted.slice(colonIdx + 1).trim().replace(/^["“]|["”]$/g, ''),
        }
      }
    }
    return { isDialogue: true, speechText: unquoted }
  }

  return { isDialogue: false, speechText: raw }
}

export function parseAssistantContent(
  content: string,
  playerSheet?: any,
  entities: any[] = [],
  metadataMap?: Record<string, any>
): { narration: string; dialogues: DialogueSegment[] } {
  if (!content) return { narration: '', dialogues: [] }

  const dialogues: DialogueSegment[] = []
  const cleanContent = content.replace(/\\n/g, '\n').trim()
  const lines = cleanContent.split('\n')
  const narrationLines: string[] = []

  const speechRegex = /^(?:\*\*([^*:\n]+?):\*\*|\*\*([^*:\n]+?)\*\*:|([A-Za-z0-9_\s'-]{2,30}):)\s*(?:["“](.+?)["”]|(.+))$/

  for (const rawLine of lines) {
    const line = rawLine.trim()
    if (!line) continue

    const match = line.match(speechRegex)
    if (match) {
      let speakerName = (match[1] || match[2] || match[3] || '').trim()
      let targetName: string | undefined = undefined
      let targetEntity: any = undefined

      const toMatch = speakerName.match(/^(.+?)\s+(?:to|\(to)\s+(.+?)\)?$/i)
      if (toMatch) {
        speakerName = toMatch[1].trim()
        targetName = toMatch[2].trim()
        targetEntity = resolveNpc(targetName, entities, metadataMap)
      }

      const speechText = (match[4] || match[5] || '').trim().replace(/^["“]|["”]$/g, '')

      const resolvedNpc = resolveNpc(speakerName, entities, metadataMap)
      if (speakerName.toLowerCase() === 'you' || speakerName.toLowerCase() === (playerSheet?.name || '').toLowerCase()) {
        dialogues.push({
          speaker: playerSheet?.name || 'You',
          isPlayer: true,
          target: targetName,
          targetEntity,
          avatarUrl: playerSheet?.profile_image,
          text: speechText,
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
        })
      }
    } else {
      narrationLines.push(line)
    }
  }

  return {
    narration: narrationLines.join('\n\n'),
    dialogues,
  }
}

export function renderFormattedHtml(text: string): string {
  if (!text) return ''
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
  const withVoiceTags = escaped.replace(/(\[[^\]\n]+\])/g, '<span class="comic-voice-tag">$1</span>')
  const withBolds = withVoiceTags.replace(/\*\*(.*?)\*\*/g, '<strong class="text-amber-200 font-bold">$1</strong>')
  const withObjectIds = withBolds.replace(/##([A-Za-z0-9_-]+)/g, '<span class="comic-object-tag">$1</span>')

  return DOMPurify.sanitize(withObjectIds, {
    ALLOWED_TAGS: ['span', 'strong', 'em', 'br', 'div'],
    ALLOWED_ATTR: ['class'],
  })
}

export function useComicTurns(options: UseComicTurnsOptions) {
  const { messages, entities, npcMetadata, sheet } = options
  const viewingTurnIndex = ref<number | null>(null)

  const gameTurns = computed<ComicTurn[]>(() => {
    const msgs = messages.value || []
    if (!msgs.length) return []

    const turns: ComicTurn[] = []
    let currentTurn: ComicTurn = {
      index: 0,
      systemMessages: [],
      licenseMessage: null,
      narration: '',
      dialogues: [],
      revealedItemIds: [],
    }

    for (let i = 0; i < msgs.length; i++) {
      const msg = msgs[i]
      if (msg.role === 'license_info') {
        currentTurn.licenseMessage = msg
        continue
      }

      if (msg.role === 'user') {
        if (
          currentTurn.userMessage ||
          currentTurn.assistantMessage ||
          currentTurn.narration ||
          currentTurn.systemMessages.length ||
          currentTurn.licenseMessage
        ) {
          turns.push(currentTurn)
          currentTurn = {
            index: turns.length,
            systemMessages: [],
            licenseMessage: null,
            narration: '',
            dialogues: [],
            revealedItemIds: [],
          }
        }
        currentTurn.userMessage = msg
        const userParsed = parseUserMessage(msg, entities.value, npcMetadata.value)
        currentTurn.userIsDialogue = userParsed.isDialogue
        currentTurn.userTargetName = userParsed.targetName
        currentTurn.userTargetEntity = userParsed.targetEntity
        currentTurn.userSpeechText = userParsed.speechText
        currentTurn.timestamp = msg.timestamp
      } else if (msg.role === 'assistant') {
        currentTurn.assistantMessage = msg
        currentTurn.timestamp = msg.timestamp || currentTurn.timestamp
        if (msg.itemIds && Array.isArray(msg.itemIds)) {
          currentTurn.revealedItemIds.push(...msg.itemIds)
        }
        const parsed = parseAssistantContent(msg.content, sheet.value, entities.value, npcMetadata.value)
        currentTurn.narration = parsed.narration
        currentTurn.dialogues.push(...parsed.dialogues)
      } else if (msg.role === 'system') {
        currentTurn.systemMessages.push(msg)
      }
    }

    if (
      currentTurn.userMessage ||
      currentTurn.assistantMessage ||
      currentTurn.narration ||
      currentTurn.systemMessages.length ||
      currentTurn.licenseMessage
    ) {
      turns.push(currentTurn)
    }

    return turns
  })

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
    if (!activeTurn.value) return speakers
    for (const d of activeTurn.value.dialogues) {
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

    const sortedWorldNpcs = [...worldNpcs].sort((a, b) => {
      const aSpeaking = isNpcSpeaking(a) ? 1 : 0
      const bSpeaking = isNpcSpeaking(b) ? 1 : 0
      return bSpeaking - aSpeaking
    })

    if (sheet.value && sheet.value.name) {
      const playerEntity = {
        id: 'PLAYER',
        entity_type: 'NPC',
        name: sheet.value.name ? `You (${sheet.value.name})` : 'You',
        description: sheet.value.description || 'Your hero character.',
        image_url: sheet.value.profile_image || null,
        role: sheet.value.role || 'Hero',
        hp: typeof sheet.value.hp === 'number' ? sheet.value.hp : 100,
        max_hp: typeof sheet.value.max_hp === 'number' ? sheet.value.max_hp : 100,
        mana: typeof sheet.value.mana === 'number' ? sheet.value.mana : 50,
        max_mana: typeof sheet.value.max_mana === 'number' ? sheet.value.max_mana : 50,
        stamina: typeof sheet.value.stamina === 'number' ? sheet.value.stamina : 50,
        max_stamina: typeof sheet.value.max_stamina === 'number' ? sheet.value.max_stamina : 50,
        inventory: Array.isArray(sheet.value.inventory) ? sheet.value.inventory : [],
        stats: sheet.value.stats,
      }
      return [playerEntity, ...sortedWorldNpcs]
    }
    return sortedWorldNpcs
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
