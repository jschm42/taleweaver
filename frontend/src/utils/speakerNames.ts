/**
 * Matching of a dialogue speaker label to a character name.
 *
 * The narrator often shortens or reorders names: "Pip Fenwick" or "Fenwick" for
 * "Professor Pip Fenwick", "Grimsby" for "Grimsby the Gargoyle". A label counts as a short
 * name when its words appear as a contiguous run of whole words in the full name.
 */

function nameWords(name: string): string[] {
  return name
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s'’-]/gu, ' ')
    .split(/\s+/)
    .filter(Boolean)
}

/** True when the shorter name's words appear as a contiguous whole-word run in the longer one. */
export function isShortNameOf(speaker: string, name: string): boolean {
  const a = nameWords(speaker)
  const b = nameWords(name)
  if (!a.length || !b.length || a.length === b.length) return false
  const [shortWords, longWords] = a.length < b.length ? [a, b] : [b, a]
  for (let start = 0; start + shortWords.length <= longWords.length; start++) {
    if (shortWords.every((word, i) => longWords[start + i] === word)) return true
  }
  return false
}

/**
 * The single candidate whose name the speaker label shortens, or undefined when none or
 * several match (two "Captain ..." characters must never swap portraits or voices).
 */
export function uniqueShortNameMatch<T>(speaker: string, candidates: T[], nameOf: (candidate: T) => string): T | undefined {
  const matches = candidates.filter((candidate) => isShortNameOf(speaker, nameOf(candidate)))
  return matches.length === 1 ? matches[0] : undefined
}
