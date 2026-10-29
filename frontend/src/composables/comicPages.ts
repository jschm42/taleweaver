/**
 * Groups the chat log into story pages.
 *
 * A page covers one scene + sequence (chapter). It only changes when the player enters
 * another scene or the sequence advances — not for every player message. Each page holds
 * the exchanges (player action → events → narration → follow-up events) of that scene.
 */
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
  voiceTag?: string
  isNarration?: boolean
  /** Verbatim script narration: rendered as plain text, never split into speakers. */
  isRaw?: boolean
}

export interface ComicExchange {
  userMessage?: ChatMessage | null
  userIsDialogue?: boolean
  userTargetName?: string | null
  userTargetEntity?: any
  userSpeechText?: string
  assistantMessage?: ChatMessage | null
  /** Events before the narration (dice rolls, guardrail messages, scene triggers). */
  systemMessages: ChatMessage[]
  /** Events after the narration (items added, stat changes). */
  trailingSystemMessages: ChatMessage[]
  narration: string
  dialogues: DialogueSegment[]
  revealedItemIds: string[]
  timestamp?: Date | string
}

export interface ComicTurn {
  index: number
  /** `${scene_id}|${sequence_id}` of the page, or null for legacy messages without scene info. */
  sceneKey: string | null
  exchanges: ComicExchange[]
  licenseMessage?: ChatMessage | null
  /** All system messages of the page (for the SYSTEM tab). */
  systemMessages: ChatMessage[]
}

export interface ComicPageParsers {
  parseUser: (msg: ChatMessage) => {
    isDialogue: boolean
    targetName?: string | null
    targetEntity?: any
    speechText: string
  }
  parseAssistant: (content: string) => { narration: string; dialogues: DialogueSegment[] }
}

/** A raw message (tw.story.narrate_raw) is one Game Master block with its text untouched. */
export function rawAssistantContent(content: string): { narration: string; dialogues: DialogueSegment[] } {
  const text = (content || '').trim()
  if (!text) return { narration: '', dialogues: [] }
  return { narration: text, dialogues: [{ speaker: 'Game Master', text, isNarration: true, isRaw: true }] }
}

// Fallback for messages saved before scene info existed: these engine messages mark a
// scene/sequence change. Display-only grouping, never used for game logic.
const LEGACY_PAGE_BREAK = /^(You have entered:|New Sequence unlocked:)/

function pageKeyOf(msg: ChatMessage): string | null {
  return msg.scene_id ? `${msg.scene_id}|${msg.sequence_id ?? ''}` : null
}

function newExchange(): ComicExchange {
  return {
    systemMessages: [],
    trailingSystemMessages: [],
    narration: '',
    dialogues: [],
    revealedItemIds: [],
  }
}

function hasContent(exchange: ComicExchange): boolean {
  return Boolean(
    exchange.userMessage ||
      exchange.assistantMessage ||
      exchange.systemMessages.length ||
      exchange.trailingSystemMessages.length
  )
}

class PageBuilder {
  pages: ComicTurn[] = []
  page: ComicTurn = this.newPage(null)
  exchange: ComicExchange = newExchange()

  constructor(private readonly parsers: ComicPageParsers) {}

  newPage(sceneKey: string | null): ComicTurn {
    return { index: 0, sceneKey, exchanges: [], licenseMessage: null, systemMessages: [] }
  }

  flushExchange(): void {
    if (hasContent(this.exchange)) this.page.exchanges.push(this.exchange)
    this.exchange = newExchange()
  }

  flushPage(): void {
    this.flushExchange()
    if (this.page.exchanges.length || this.page.licenseMessage) {
      this.page.index = this.pages.length
      this.page.systemMessages = this.page.exchanges.flatMap((ex) => [
        ...ex.systemMessages,
        ...ex.trailingSystemMessages,
      ])
      this.pages.push(this.page)
    }
  }

  isPageBreak(msg: ChatMessage, key: string | null): boolean {
    if (key !== null) return this.page.sceneKey !== null && key !== this.page.sceneKey
    const pageHasContent = this.page.exchanges.length > 0 || hasContent(this.exchange)
    return msg.role === 'system' && pageHasContent && LEGACY_PAGE_BREAK.test(msg.content.trim())
  }

  startPage(key: string | null): void {
    // The player action that led into the new scene (no narration yet) moves along.
    const pending = this.exchange.userMessage && !this.exchange.assistantMessage ? this.exchange : null
    if (pending) this.exchange = newExchange()
    this.flushPage()
    this.page = this.newPage(key)
    if (pending) this.exchange = pending
  }

  addUser(msg: ChatMessage): void {
    this.flushExchange()
    const parsed = this.parsers.parseUser(msg)
    Object.assign(this.exchange, {
      userMessage: msg,
      userIsDialogue: parsed.isDialogue,
      userTargetName: parsed.targetName,
      userTargetEntity: parsed.targetEntity,
      userSpeechText: parsed.speechText,
      timestamp: msg.timestamp,
    })
  }

  addAssistant(msg: ChatMessage): void {
    if (this.exchange.assistantMessage) {
      // A narration without a new player message (e.g. pickup reaction) starts a new
      // exchange and takes the events that led up to it.
      const carried = this.exchange.trailingSystemMessages
      this.exchange.trailingSystemMessages = []
      this.flushExchange()
      this.exchange.systemMessages.push(...carried)
    }
    const parsed = msg.raw ? rawAssistantContent(msg.content) : this.parsers.parseAssistant(msg.content)
    this.exchange.assistantMessage = msg
    this.exchange.timestamp = msg.timestamp || this.exchange.timestamp
    this.exchange.narration = parsed.narration
    this.exchange.dialogues.push(...parsed.dialogues)
    if (Array.isArray(msg.itemIds)) this.exchange.revealedItemIds.push(...msg.itemIds)
  }

  addSystem(msg: ChatMessage): void {
    const target = this.exchange.assistantMessage
      ? this.exchange.trailingSystemMessages
      : this.exchange.systemMessages
    target.push(msg)
  }

  add(msg: ChatMessage): void {
    if (msg.role === 'license_info') {
      this.page.licenseMessage = msg
      return
    }
    const key = pageKeyOf(msg)
    if (this.isPageBreak(msg, key)) this.startPage(key)
    if (key !== null && this.page.sceneKey === null) this.page.sceneKey = key

    if (msg.role === 'user') this.addUser(msg)
    else if (msg.role === 'assistant') this.addAssistant(msg)
    else if (msg.role === 'system') this.addSystem(msg)
  }
}

export function buildComicPages(messages: ChatMessage[], parsers: ComicPageParsers): ComicTurn[] {
  const builder = new PageBuilder(parsers)
  for (const msg of messages) builder.add(msg)
  builder.flushPage()
  return builder.pages
}
