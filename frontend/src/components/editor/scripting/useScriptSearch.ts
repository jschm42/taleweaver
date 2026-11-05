import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import type { CmEditor, CmPosition, CmTextMarker } from './codeMirrorTypes'

export interface SearchMatch {
  start: number
  end: number
  line?: number
  ch?: number
}

/** Upper bound for collected matches; keeps marker creation cheap on huge scripts. */
export const MAX_SEARCH_MATCHES = 5000

const MATCH_CLASS = 'cm-search-match'
const CURRENT_MATCH_CLASS = 'cm-search-match-current'

interface SearchOptions {
  query: string
  matchCase: boolean
  wholeWord: boolean
  useRegex: boolean
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Builds the global search pattern, or throws a SyntaxError for an invalid user regex. */
export function buildPattern(opts: SearchOptions): RegExp {
  const source = opts.useRegex ? opts.query : escapeRegExp(opts.query)
  const wrapped = opts.wholeWord ? `\\b(?:${source})\\b` : source
  return new RegExp(wrapped, opts.matchCase ? 'gm' : 'gim')
}

/** Finds all matches in a single pass and annotates them with line/ch positions. */
export function findMatches(text: string, pattern: RegExp): SearchMatch[] {
  const matches: SearchMatch[] = []
  let line = 0
  let lineStart = 0
  let scanned = 0
  let found = pattern.exec(text)
  while (found && matches.length < MAX_SEARCH_MATCHES) {
    if (found[0].length === 0) {
      pattern.lastIndex += 1
      found = pattern.exec(text)
      continue
    }
    for (; scanned < found.index; scanned++) {
      if (text.charCodeAt(scanned) !== 10) continue
      line++
      lineStart = scanned + 1
    }
    matches.push({
      start: found.index,
      end: found.index + found[0].length,
      line,
      ch: found.index - lineStart
    })
    found = pattern.exec(text)
  }
  return matches
}

function endPosition(match: SearchMatch, text: string): CmPosition {
  const matched = text.slice(match.start, match.end)
  const lastBreak = matched.lastIndexOf('\n')
  const line = (match.line ?? 0) + (matched.split('\n').length - 1)
  const ch = lastBreak === -1 ? (match.ch ?? 0) + matched.length : matched.length - lastBreak - 1
  return { line, ch }
}

export function useScriptSearch(
  cmInstance: Ref<CmEditor | null>,
  fallbackTextarea: Ref<HTMLTextAreaElement | null>,
  code: Ref<string>,
  onCodeChange: (val: string) => void
) {
  const isOpen = ref(false)
  const query = ref('')
  const replaceText = ref('')
  const matchCase = ref(false)
  const wholeWord = ref(false)
  const useRegex = ref(false)
  const currentMatchIndex = ref(-1)
  const searchMatches = ref<SearchMatch[]>([])
  const searchError = ref<string | null>(null)

  const totalMatches = computed(() => searchMatches.value.length)
  const limitReached = computed(() => totalMatches.value >= MAX_SEARCH_MATCHES)

  let marks: CmTextMarker[] = []
  let currentMark: CmTextMarker | null = null

  function currentPattern(): RegExp | null {
    if (!query.value) return null
    try {
      searchError.value = null
      return buildPattern({
        query: query.value,
        matchCase: matchCase.value,
        wholeWord: wholeWord.value,
        useRegex: useRegex.value
      })
    } catch (err) {
      searchError.value = err instanceof Error ? err.message : 'Invalid regular expression'
      return null
    }
  }

  function toRange(match: SearchMatch): { from: CmPosition; to: CmPosition } {
    const cm = cmInstance.value
    if (cm) {
      try {
        return {
          from: cm.posFromIndex(match.start),
          to: cm.posFromIndex(match.end)
        }
      } catch {
        // Fallback to manual line/ch calculation if posFromIndex fails
      }
    }
    const from = { line: match.line ?? 0, ch: match.ch ?? 0 }
    return { from, to: endPosition(match, code.value) }
  }

  function safeClear(mark: CmTextMarker | null | undefined): void {
    if (!mark) return
    try {
      mark.clear()
    } catch {
      // CodeMirror TextMarker can throw if line spans were adjusted or detached
    }
  }

  function clearMarks() {
    marks.forEach(mark => safeClear(mark))
    marks = []
    safeClear(currentMark)
    currentMark = null
  }

  function applyMarks() {
    const cm = cmInstance.value
    if (!cm) return
    cm.operation(() => {
      clearMarks()
      if (!isOpen.value) return
      marks = searchMatches.value
        .map(match => {
          const { from, to } = toRange(match)
          try {
            return cm.markText(from, to, { className: MATCH_CLASS })
          } catch {
            return null
          }
        })
        .filter((m): m is CmTextMarker => m !== null)
      highlightCurrent()
    })
  }

  function highlightCurrent() {
    const cm = cmInstance.value
    const match = searchMatches.value[currentMatchIndex.value]
    safeClear(currentMark)
    currentMark = null
    if (!cm || !match) return
    const { from, to } = toRange(match)
    try {
      currentMark = cm.markText(from, to, { className: CURRENT_MATCH_CLASS })
    } catch {
      // ignore
    }
  }

  function cursorIndex(): number {
    const cm = cmInstance.value
    if (cm) return cm.indexFromPos(cm.getCursor('from'))
    return fallbackTextarea.value?.selectionStart ?? 0
  }

  /** Recomputes matches; `anchor` selects the first match at or after that offset. */
  function refresh(anchor?: number) {
    const pattern = isOpen.value ? currentPattern() : null
    searchMatches.value = pattern ? findMatches(code.value, pattern) : []
    const matches = searchMatches.value
    if (!matches.length) {
      currentMatchIndex.value = -1
    } else if (anchor !== undefined) {
      const idx = matches.findIndex(m => m.start >= anchor)
      currentMatchIndex.value = idx === -1 ? 0 : idx
    } else {
      currentMatchIndex.value = Math.min(Math.max(currentMatchIndex.value, 0), matches.length - 1)
    }
    applyMarks()
  }

  function revealTextarea(match: SearchMatch) {
    const textarea = fallbackTextarea.value
    if (!textarea) return
    textarea.setSelectionRange(match.start, match.end)
    const lineHeight = parseFloat(getComputedStyle(textarea).lineHeight) || 18
    const targetTop = (match.line ?? 0) * lineHeight - textarea.clientHeight / 2
    textarea.scrollTop = Math.max(0, targetTop)
    textarea.scrollIntoView({ block: 'nearest' })
  }

  function revealCurrent() {
    const match = searchMatches.value[currentMatchIndex.value]
    if (!match) return
    const cm = cmInstance.value
    if (!cm) {
      revealTextarea(match)
      return
    }
    const { from, to } = toRange(match)
    try {
      cm.setSelection(from, to, { scroll: false })
      cm.scrollIntoView({ from, to }, 60)
    } catch {
      // ignore
    }
    highlightCurrent()
  }

  function step(delta: number) {
    const total = totalMatches.value
    if (!total) return
    currentMatchIndex.value = (currentMatchIndex.value + delta + total) % total
    revealCurrent()
  }

  function findNext() {
    step(1)
  }

  function findPrev() {
    step(-1)
  }

  /** Replacement text for one match; regex mode expands $1-style group references. */
  function replacementFor(match: SearchMatch, pattern: RegExp): string {
    if (!useRegex.value) return replaceText.value
    const single = new RegExp(pattern.source, pattern.flags.replace('g', ''))
    return code.value.slice(match.start, match.end).replace(single, replaceText.value)
  }

  function writeRange(text: string, start: number, end: number) {
    const cm = cmInstance.value
    if (!cm) {
      onCodeChange(code.value.slice(0, start) + text + code.value.slice(end))
      return
    }
    cm.replaceRange(text, cm.posFromIndex(start), cm.posFromIndex(end), '+replace')
  }

  function replaceCurrent() {
    const match = searchMatches.value[currentMatchIndex.value]
    const pattern = currentPattern()
    if (!match || !pattern) return
    const replacement = replacementFor(match, pattern)
    writeRange(replacement, match.start, match.end)
    refresh(match.start + replacement.length)
    revealCurrent()
  }

  function replaceAll() {
    const pattern = currentPattern()
    const matches = searchMatches.value
    if (!pattern || !matches.length) return
    const source = code.value
    const parts: string[] = []
    let cursor = 0
    for (const match of matches) {
      parts.push(source.slice(cursor, match.start), replacementFor(match, pattern))
      cursor = match.end
    }
    parts.push(source.slice(cursor))
    writeRange(parts.join(''), 0, source.length)
    refresh(0)
  }

  function openSearch() {
    const selected = cmInstance.value?.getSelection() ?? ''
    if (selected && !selected.includes('\n')) query.value = selected
    isOpen.value = true
    refresh(cursorIndex())
  }

  function closeSearch() {
    isOpen.value = false
    clearMarks()
    searchMatches.value = []
    currentMatchIndex.value = -1
    try {
      cmInstance.value?.focus()
    } catch {
      // ignore
    }
  }

  function toggleSearch() {
    if (isOpen.value) {
      closeSearch()
      return
    }
    openSearch()
  }

  watch([query, matchCase, wholeWord, useRegex], () => {
    if (!isOpen.value) return
    refresh(cursorIndex())
    revealCurrent()
  })

  watch(code, () => {
    if (!isOpen.value) return
    refresh(searchMatches.value[currentMatchIndex.value]?.start)
  })

  onBeforeUnmount(clearMarks)

  return {
    isOpen,
    query,
    replaceText,
    matchCase,
    wholeWord,
    useRegex,
    currentMatchIndex,
    totalMatches,
    limitReached,
    searchMatches,
    searchError,
    openSearch,
    closeSearch,
    toggleSearch,
    findNext,
    findPrev,
    replaceCurrent,
    replaceAll,
    clearMarks
  }
}

export type ScriptSearch = ReturnType<typeof useScriptSearch>
