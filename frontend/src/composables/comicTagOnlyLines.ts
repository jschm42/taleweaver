/**
 * comicTagOnlyLines — handling of story lines that hold nothing but voice tags (e.g. "[coughs]").
 *
 * Such a line must never become an empty Game Master block. The inline speech splitter in
 * useComicTurns cuts a speech line right after its closing quote, which strands a trailing cue
 * like `Bram: "Fine." [coughs]` on a line of its own; that cue goes back to the speaker it
 * followed. Anywhere else the caller keeps the tag for the next narration paragraph.
 */
import type { DialogueSegment } from './comicPages'

const QUOTE_CHARS = /["„“”«»]/

/** Attaches a stranded tag line to the preceding speech bubble; false if there is none. */
export function attachCueToSpeech(dialogues: DialogueSegment[], tagLine: string): boolean {
  const last = dialogues[dialogues.length - 1]
  if (!last || last.isNarration || !last.text) {
    return false
  }
  // Re-quote the speech so the cue renders after the closing quote, not inside it.
  const quoted = QUOTE_CHARS.test(last.text) ? last.text : `"${last.text}"`
  last.text = `${quoted} ${tagLine.trim()}`
  return true
}
