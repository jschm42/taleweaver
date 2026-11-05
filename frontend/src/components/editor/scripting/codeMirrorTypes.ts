/**
 * The subset of the CodeMirror 5 editor API (loaded from the CDN, see cdnScriptLoader)
 * that the script editor and its composables use.
 */
export interface CmPosition {
  line: number
  ch: number
}

export interface CmTextMarker {
  clear(): void
}

export interface CmEditor {
  getValue(): string
  setValue(value: string): void
  getCursor(which?: 'from' | 'to' | 'head' | 'anchor'): CmPosition
  setCursor(pos: CmPosition): void
  getSelection(): string
  setSelection(anchor: CmPosition, head?: CmPosition, options?: { scroll?: boolean }): void
  replaceSelection(text: string, select?: 'around' | 'start' | 'end'): void
  replaceRange(text: string, from: CmPosition, to?: CmPosition, origin?: string): void
  posFromIndex(index: number): CmPosition
  indexFromPos(pos: CmPosition): number
  lastLine(): number
  getLine(line: number): string
  markText(from: CmPosition, to: CmPosition, options: { className: string }): CmTextMarker
  scrollIntoView(range: { from: CmPosition; to: CmPosition }, margin?: number): void
  operation<T>(fn: () => T): T
  setOption(option: string, value: unknown): void
  on(event: string, handler: () => void): void
  getWrapperElement(): HTMLElement
  refresh(): void
  focus(): void
}

export type CmFactory = (host: HTMLElement, options: Record<string, unknown>) => CmEditor
