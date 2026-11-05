/**
 * Fault-tolerant outline parser for Python-style scripts.
 *
 * Extracts `def` / `async def` entries with their enclosing scope (class or parent function)
 * and docstring in a single linear pass over the source. Comments and string literals
 * (including multi-line triple-quoted blocks) are masked out, so a `def` inside them is
 * ignored. Malformed input (unclosed brackets or strings, incomplete headers) never throws:
 * the parser captures whatever is available.
 */
import type { OutlineFunction } from '@/types/scriptOutline'

const TAB_WIDTH = 4
const DEF_RE = /^\s*(async\s+)?def\s+([\p{L}_][\p{L}\p{N}_]*)/u
const CLASS_RE = /^\s*class\s+([\p{L}_][\p{L}\p{N}_]*)/u
const PAREN_RE = /^\s*\(/
const DOC_START_RE = /^[rRuU]?("""|'''|"|')/
const OPENERS = '([{'
const CLOSERS = ')]}'

interface Scope {
  indent: number
  name: string
}

/** A `def` whose parameter list is still open at the end of a line. */
interface PendingDef {
  fn: OutlineFunction
  parts: string[]
}

/** A multi-line docstring being collected. */
interface DocCollector {
  fn: OutlineFunction
  delim: string
  parts: string[]
}

interface ParserState {
  functions: OutlineFunction[]
  scopes: Scope[]
  /** Open triple-quote delimiter carried over from the previous line. */
  stringDelim: string | null
  /** Bracket depth carried over from the previous line. */
  depth: number
  pending: PendingDef | null
  awaitingDoc: OutlineFunction | null
  doc: DocCollector | null
}

/** Character cursor used to mask one line. */
interface Cursor {
  line: string
  pos: number
  out: string
  delim: string | null
}

// ---------------------------------------------------------------------------
// Line masking: string contents become spaces, comments are cut off. The masked
// code keeps the raw column positions, so indexes map 1:1 back to the raw line.
// ---------------------------------------------------------------------------

function stepInString(c: Cursor): void {
  const delim = c.delim ?? ''
  if (c.line[c.pos] === '\\') {
    const width = Math.min(2, c.line.length - c.pos)
    c.out += ' '.repeat(width)
    c.pos += width
    return
  }
  if (c.line.startsWith(delim, c.pos)) {
    c.out += delim
    c.pos += delim.length
    c.delim = null
    return
  }
  c.out += ' '
  c.pos += 1
}

/** Advances over code; returns false once a comment starts. */
function stepInCode(c: Cursor): boolean {
  const ch = c.line[c.pos]
  if (ch === '#') {
    return false
  }
  if (ch !== '"' && ch !== "'") {
    c.out += ch
    c.pos += 1
    return true
  }
  const triple = ch.repeat(3)
  const delim = c.line.startsWith(triple, c.pos) ? triple : ch
  c.out += delim
  c.pos += delim.length
  c.delim = delim
  return true
}

function maskLine(line: string, delim: string | null): { code: string; delim: string | null } {
  const c: Cursor = { line, pos: 0, out: '', delim }
  while (c.pos < line.length) {
    if (c.delim) {
      stepInString(c)
      continue
    }
    if (!stepInCode(c)) {
      break
    }
  }
  // Single-quoted strings cannot span lines; only triple quotes carry over.
  const carried = c.delim && c.delim.length === 3 ? c.delim : null
  return { code: c.out, delim: carried }
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function nextDepth(depth: number, ch: string): number {
  if (OPENERS.includes(ch)) {
    return depth + 1
  }
  if (CLOSERS.includes(ch)) {
    return Math.max(0, depth - 1)
  }
  return depth
}

function countDepth(code: string, depth: number, from = 0): number {
  let level = depth
  for (let i = from; i < code.length; i++) {
    level = nextDepth(level, code[i])
  }
  return level
}

/** Collects raw parameter text from `start` until the bracket depth drops to zero. */
function collectParams(
  raw: string,
  code: string,
  start: number,
  depth: number
): { text: string; end: number } {
  let level = depth
  for (let i = start; i < code.length; i++) {
    level = nextDepth(level, code[i])
    if (level === 0) {
      return { text: raw.slice(start, i), end: i + 1 }
    }
  }
  return { text: raw.slice(start, code.length), end: -1 }
}

function normalizeParams(text: string): string {
  return text.replace(/\s+/g, ' ').replace(/,\s*$/, '').trim()
}

function measureIndent(raw: string): number {
  let width = 0
  for (const ch of raw) {
    if (ch !== ' ' && ch !== '\t') {
      break
    }
    width += ch === '\t' ? TAB_WIDTH - (width % TAB_WIDTH) : 1
  }
  return width
}

function isHeader(code: string): boolean {
  return DEF_RE.test(code) || CLASS_RE.test(code)
}

function setDocstring(fn: OutlineFunction, parts: string[]): void {
  const text = parts
    .map(part => part.trim())
    .join('\n')
    .trim()
  if (text) {
    fn.docstring = text
  }
}

// ---------------------------------------------------------------------------
// Docstrings
// ---------------------------------------------------------------------------

/** Starts docstring extraction if `text` begins with a string literal. */
function tryDocstring(state: ParserState, fn: OutlineFunction, text: string): boolean {
  const match = DOC_START_RE.exec(text)
  if (!match) {
    return false
  }
  const delim = match[1]
  const body = text.slice(match[0].length)
  const close = body.indexOf(delim)
  if (close >= 0 || delim.length === 1) {
    setDocstring(fn, [close >= 0 ? body.slice(0, close) : body])
    return true
  }
  state.doc = { fn, delim, parts: [body] }
  return true
}

function continueDocstring(state: ParserState, doc: DocCollector, raw: string, code: string): void {
  if (state.stringDelim !== null) {
    doc.parts.push(raw)
    return
  }
  const close = code.indexOf(doc.delim)
  doc.parts.push(close >= 0 ? raw.slice(0, close) : raw)
  setDocstring(doc.fn, doc.parts)
  state.doc = null
}

// ---------------------------------------------------------------------------
// Function headers
// ---------------------------------------------------------------------------

/** Handles the part of a header line after the closing paren of the parameter list. */
function finishHeader(
  state: ParserState,
  fn: OutlineFunction,
  raw: string,
  code: string,
  end: number
): void {
  state.depth = countDepth(code, 0, end)
  const colon = code.indexOf(':', end)
  if (colon < 0 || !code.slice(colon + 1).trim()) {
    state.awaitingDoc = fn
    return
  }
  tryDocstring(state, fn, raw.slice(colon + 1).trim())
}

function openFunction(
  state: ParserState,
  raw: string,
  code: string,
  match: RegExpExecArray,
  lineNo: number,
  indent: number
): void {
  const name = match[2]
  const headerEnd = match[0].length
  const fn: OutlineFunction = {
    name,
    params: '',
    line: lineNo,
    column: headerEnd - name.length,
    indent,
    isAsync: Boolean(match[1])
  }
  const scope = state.scopes[state.scopes.length - 1]
  if (scope) {
    fn.scope = scope.name
  }
  state.functions.push(fn)
  state.scopes.push({ indent, name })

  const paren = PAREN_RE.exec(code.slice(headerEnd))
  if (!paren) {
    state.awaitingDoc = fn
    return
  }
  const start = headerEnd + paren[0].length
  const { text, end } = collectParams(raw, code, start, 1)
  if (end < 0) {
    state.pending = { fn, parts: [text] }
    state.depth = countDepth(code, 0)
    return
  }
  fn.params = normalizeParams(text)
  finishHeader(state, fn, raw, code, end)
}

function flushPending(state: ParserState): void {
  const pending = state.pending
  state.pending = null
  state.depth = 0
  if (pending) {
    pending.fn.params = normalizeParams(pending.parts.join(' '))
  }
}

/** A dedented line or a new header ends an unclosed parameter list. */
function abortsPending(pending: PendingDef, code: string, indent: number): boolean {
  if (isHeader(code)) {
    return true
  }
  return indent <= pending.fn.indent && !code.trimStart().startsWith(')')
}

function continuePending(state: ParserState, pending: PendingDef, raw: string, code: string): void {
  const { text, end } = collectParams(raw, code, 0, state.depth)
  pending.parts.push(text)
  if (end < 0) {
    state.depth = countDepth(code, state.depth)
    return
  }
  flushPending(state)
  finishHeader(state, pending.fn, raw, code, end)
}

// ---------------------------------------------------------------------------
// Line dispatch
// ---------------------------------------------------------------------------

function handleStatement(
  state: ParserState,
  raw: string,
  code: string,
  lineNo: number,
  indent: number
): void {
  const awaiting = state.awaitingDoc
  state.awaitingDoc = null
  if (awaiting && tryDocstring(state, awaiting, raw.trim())) {
    return
  }
  while (state.scopes.length > 0 && state.scopes[state.scopes.length - 1].indent >= indent) {
    state.scopes.pop()
  }
  const def = DEF_RE.exec(code)
  if (def) {
    openFunction(state, raw, code, def, lineNo, indent)
    return
  }
  const cls = CLASS_RE.exec(code)
  if (cls) {
    state.scopes.push({ indent, name: cls[1] })
  }
  state.depth = countDepth(code, 0)
}

function processLine(state: ParserState, raw: string, lineNo: number): void {
  const startsInString = state.stringDelim !== null
  const { code, delim } = maskLine(raw, state.stringDelim)
  state.stringDelim = delim
  if (state.doc) {
    continueDocstring(state, state.doc, raw, code)
    return
  }
  if (startsInString || !code.trim()) {
    return
  }
  const indent = measureIndent(raw)
  if (state.pending && !abortsPending(state.pending, code, indent)) {
    continuePending(state, state.pending, raw, code)
    return
  }
  flushPending(state)
  if (state.depth > 0 && !isHeader(code)) {
    state.depth = countDepth(code, state.depth)
    return
  }
  handleStatement(state, raw, code, lineNo, indent)
}

function finalize(state: ParserState): void {
  flushPending(state)
  if (state.doc) {
    setDocstring(state.doc.fn, state.doc.parts)
    state.doc = null
  }
}

/**
 * Parses a Python-style script into a flat list of function outline entries.
 * Runs in O(N) time over the source and keeps O(M) state for M functions. Never throws.
 */
export function parseScriptOutline(source: string): OutlineFunction[] {
  const state: ParserState = {
    functions: [],
    scopes: [],
    stringDelim: null,
    depth: 0,
    pending: null,
    awaitingDoc: null,
    doc: null
  }
  if (typeof source !== 'string') {
    return state.functions
  }
  try {
    let start = 0
    let lineNo = 1
    let newline = source.indexOf('\n')
    while (newline >= 0) {
      processLine(state, source.slice(start, newline).replace(/\r$/, ''), lineNo)
      start = newline + 1
      lineNo += 1
      newline = source.indexOf('\n', start)
    }
    processLine(state, source.slice(start).replace(/\r$/, ''), lineNo)
    finalize(state)
  } catch {
    // Defensive: a parser bug must never break the editor; return what was collected.
  }
  return state.functions
}
