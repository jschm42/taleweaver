/**
 * Autocomplete / IntelliSense integration for CodeMirror 5 Script Editor.
 * Provides context-aware completions for the `tw.*` API and proxy objects.
 */

import {
  TW_NAMESPACES,
  TW_ROOT_ITEMS,
  PROXY_ITEMS,
  type TwApiItem,
} from './twScriptApiDefinitions'
import { ensureCodeMirrorHintLoaded } from './cdnScriptLoader'

export interface CompletionEntry {
  text: string
  displayText: string
  className: string
  item: TwApiItem
  from?: { line: number; ch: number }
  to?: { line: number; ch: number }
  render: (element: HTMLElement, self: any, data: any) => void
  hint: (cm: any, data: any, cur: any) => void
}

/** Determines what items are available based on the token expression before cursor */
export function resolveCompletionsForLine(lineText: string): {
  items: TwApiItem[]
  queryPrefix: string
} {
  // 1. Check for method chained on proxies: e.g. tw.npcs.get(...)., npc.
  if (/tw\.npcs\.get\([^)]*\)\.([a-zA-Z0-9_]*)$/.test(lineText) || /(?:^|\s)npc\.([a-zA-Z0-9_]*)$/.test(lineText)) {
    const match = lineText.match(/(?:tw\.npcs\.get\([^)]*\)|(?:^|\s)npc)\.([a-zA-Z0-9_]*)$/)
    const prefix = match ? match[1] : ''
    return { items: PROXY_ITEMS.NPCProxy || [], queryPrefix: prefix }
  }

  if (
    /tw\.(?:objects|items)\.get\([^)]*\)\.([a-zA-Z0-9_]*)$/.test(lineText) ||
    /(?:^|\s)(?:item|obj|container)\.([a-zA-Z0-9_]*)$/.test(lineText)
  ) {
    const match = lineText.match(/(?:tw\.(?:objects|items)\.get\([^)]*\)|(?:^|\s)(?:item|obj|container))\.([a-zA-Z0-9_]*)$/)
    const prefix = match ? match[1] : ''
    return { items: PROXY_ITEMS.ObjectProxy || [], queryPrefix: prefix }
  }

  if (
    /tw\.switches\.get\([^)]*\)\.([a-zA-Z0-9_]*)$/.test(lineText) ||
    /tw\.switch\([^)]*\)\.([a-zA-Z0-9_]*)$/.test(lineText) ||
    /(?:^|\s)switch\b.*\.([a-zA-Z0-9_]*)$/.test(lineText)
  ) {
    const match = lineText.match(/(?:tw\.switches\.get\([^)]*\)|tw\.switch\([^)]*\)|(?:^|\s)switch\b.*?)\.([a-zA-Z0-9_]*)$/)
    const prefix = match ? match[1] : ''
    return { items: PROXY_ITEMS.SwitchProxy || [], queryPrefix: prefix }
  }

  // 2. Sub-namespaces: e.g. tw.story.narr
  const nsMatch = lineText.match(/tw\.([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]*)$/)
  if (nsMatch) {
    const nsKey = nsMatch[1].toLowerCase()
    const prefix = nsMatch[2] || ''
    const nsObj = TW_NAMESPACES[nsKey]
    if (nsObj) {
      return { items: nsObj.items, queryPrefix: prefix }
    }
    return { items: [], queryPrefix: prefix }
  }

  // 3. Root namespace: e.g. tw.
  const rootDotMatch = lineText.match(/tw\.([a-zA-Z0-9_]*)$/)
  if (rootDotMatch) {
    const prefix = rootDotMatch[1] || ''
    return { items: TW_ROOT_ITEMS, queryPrefix: prefix }
  }

  // 4. Starting to type tw
  const bareTwMatch = lineText.match(/(?:^|[^a-zA-Z0-9_])(tw?)$/)
  if (bareTwMatch) {
    const prefix = bareTwMatch[1]
    const rootEntry: TwApiItem = {
      name: 'tw',
      kind: 'namespace',
      doc: 'TaleWeaver scripting API root context.',
    }
    return { items: [rootEntry], queryPrefix: prefix }
  }

  return { items: [], queryPrefix: '' }
}

/** Custom DOM renderer for hint items with badges, signatures, and doc text */
function renderHintItem(element: HTMLElement, selfOrData: any, curOrData?: any): void {
  const entry: CompletionEntry =
    curOrData && curOrData.item ? curOrData : selfOrData && selfOrData.item ? selfOrData : curOrData || selfOrData
  const item: TwApiItem | undefined = entry?.item
  if (!item) {
    element.textContent = entry?.displayText || entry?.text || ''
    return
  }
  element.className += ' tw-hint-item'

  // Badge
  const badge = document.createElement('span')
  const kindCls = item.kind === 'method' ? 'tw-hint-method' : item.kind === 'property' ? 'tw-hint-prop' : 'tw-hint-ns'
  badge.className = `tw-hint-badge ${kindCls}`
  badge.textContent = item.kind === 'method' ? 'def' : item.kind === 'property' ? 'val' : 'mod'
  element.appendChild(badge)

  // Name
  const nameEl = document.createElement('span')
  nameEl.className = 'tw-hint-name'
  nameEl.textContent = item.name
  element.appendChild(nameEl)

  // Signature
  if (item.signature) {
    const sigEl = document.createElement('span')
    sigEl.className = 'tw-hint-sig'
    sigEl.textContent = item.signature
    element.appendChild(sigEl)
  }

  // Doc
  if (item.doc) {
    const docEl = document.createElement('span')
    docEl.className = 'tw-hint-doc'
    docEl.textContent = item.doc
    element.appendChild(docEl)
  }
}

/** Handles insertion of the completion into the CodeMirror editor */
function applyHint(cm: any, data: any, entry: CompletionEntry): void {
  const from = entry.from || data.from
  const to = entry.to || data.to
  const item = entry.item

  if (item.kind === 'namespace') {
    // Insert name + dot and trigger hint again
    const textToInsert = item.name === 'tw' ? 'tw.' : `${item.name}.`
    cm.replaceRange(textToInsert, from, to)
    const nextCursor = { line: from.line, ch: from.ch + textToInsert.length }
    cm.setCursor(nextCursor)
    setTimeout(() => {
      triggerTwHint(cm, false)
    }, 20)
    return
  }

  if (item.kind === 'method') {
    const textToInsert = `${item.name}()`
    cm.replaceRange(textToInsert, from, to)
    // If method takes parameters, place cursor inside parens
    const hasParams = item.signature && !item.signature.startsWith('()')
    const offset = hasParams ? item.name.length + 1 : item.name.length + 2
    cm.setCursor({ line: from.line, ch: from.ch + offset })
    return
  }

  // Property
  cm.replaceRange(item.name, from, to)
  cm.setCursor({ line: from.line, ch: from.ch + item.name.length })
}

/** CodeMirror hint function */
export function twScriptHint(cm: any): any {
  const cur = cm.getCursor()
  const line = cm.getLine(cur.line)
  const lineUpToCursor = line.slice(0, cur.ch)

  const { items, queryPrefix } = resolveCompletionsForLine(lineUpToCursor)
  if (!items.length) {
    return null
  }

  const filtered = items.filter((it) =>
    it.name.toLowerCase().startsWith(queryPrefix.toLowerCase())
  )

  if (!filtered.length) {
    return null
  }

  const CodeMirror = typeof window !== 'undefined' ? (window as any).CodeMirror : null
  const Pos = CodeMirror?.Pos || ((line: number, ch: number) => ({ line, ch }))
  const from = Pos(cur.line, cur.ch - queryPrefix.length)
  const to = Pos(cur.line, cur.ch)

  const list: CompletionEntry[] = filtered.map((item) => {
    const entry: CompletionEntry = {
      text: item.name,
      displayText: item.name,
      className: `tw-cm-hint tw-cm-${item.kind}`,
      item,
      from,
      to,
      render: renderHintItem,
      hint: (editor, data) => applyHint(editor, data, entry),
    }
    return entry
  })

  return {
    list,
    from,
    to,
  }
}

/** Programmatically triggers CodeMirror showHint with TaleWeaver provider */
export async function triggerTwHint(cm: any, completeSingle = false): Promise<void> {
  if (!cm) return
  if (typeof cm.showHint !== 'function') {
    const loaded = await ensureCodeMirrorHintLoaded()
    const CodeMirror = typeof window !== 'undefined' ? (window as any).CodeMirror : null
    if (loaded && typeof cm.showHint !== 'function' && CodeMirror?.prototype?.showHint) {
      cm.showHint = CodeMirror.prototype.showHint
    }
  }
  if (typeof cm.showHint !== 'function') {
    console.warn('[ScriptEditor] cm.showHint is not available. Hint addon could not be loaded.')
    return
  }
  cm.showHint({
    hint: twScriptHint,
    completeSingle,
    closeOnUnfocus: true,
  })
}

