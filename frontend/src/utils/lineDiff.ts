/** Line-based diff (longest common subsequence) for showing proposed code changes. */

export type DiffLineType = 'same' | 'add' | 'del'

export interface DiffLine {
  type: DiffLineType
  text: string
  /** Line number in the old text ('same' and 'del'). */
  oldNo?: number
  /** Line number in the new text ('same' and 'add'). */
  newNo?: number
}

function splitLines(text: string): string[] {
  return text === '' ? [] : text.replace(/\r\n/g, '\n').split('\n')
}

/** LCS lengths: table[i][j] = common lines of oldLines[i..] and newLines[j..]. */
function lcsTable(oldLines: string[], newLines: string[]): number[][] {
  const table = Array.from({ length: oldLines.length + 1 }, () =>
    new Array<number>(newLines.length + 1).fill(0),
  )
  for (let i = oldLines.length - 1; i >= 0; i--) {
    for (let j = newLines.length - 1; j >= 0; j--) {
      table[i][j] =
        oldLines[i] === newLines[j]
          ? table[i + 1][j + 1] + 1
          : Math.max(table[i + 1][j], table[i][j + 1])
    }
  }
  return table
}

export function diffLines(oldText: string, newText: string): DiffLine[] {
  const oldLines = splitLines(oldText)
  const newLines = splitLines(newText)
  const table = lcsTable(oldLines, newLines)
  const result: DiffLine[] = []
  let i = 0
  let j = 0
  while (i < oldLines.length || j < newLines.length) {
    if (i < oldLines.length && j < newLines.length && oldLines[i] === newLines[j]) {
      result.push({ type: 'same', text: oldLines[i], oldNo: i + 1, newNo: j + 1 })
      i++
      j++
    } else if (i < oldLines.length && (j >= newLines.length || table[i + 1][j] >= table[i][j + 1])) {
      // Removed lines come before the added ones that replace them.
      result.push({ type: 'del', text: oldLines[i], oldNo: i + 1 })
      i++
    } else {
      result.push({ type: 'add', text: newLines[j], newNo: j + 1 })
      j++
    }
  }
  return result
}

export function diffStats(lines: DiffLine[]): { added: number; removed: number } {
  return {
    added: lines.filter((l) => l.type === 'add').length,
    removed: lines.filter((l) => l.type === 'del').length,
  }
}
