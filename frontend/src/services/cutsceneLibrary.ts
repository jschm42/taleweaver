/**
 * Pure helpers for the cut-scene library (`AdventureTemplate.cutscenes`): reading the editor
 * payload, new ids and new entries. No imports besides types, so tests can load it directly.
 */
import type { CutsceneDefinition, CutsceneDefinitionSlide } from '@/types'

export const MAX_SLIDES = 12
export const MAX_PASSAGES = 6
const ID_MAX = 40

function newSlideId(): string {
  return Math.random().toString(16).slice(2, 10)
}

/** The cut-scene list as the editor payload holds it (adventure.cutscenes). */
export function cutscenesOf(adventure: { cutscenes?: unknown } | null | undefined): CutsceneDefinition[] {
  const raw = Array.isArray(adventure?.cutscenes) ? adventure.cutscenes : []
  return raw
    .filter((c): c is CutsceneDefinition => Boolean(c && typeof c === 'object' && (c as CutsceneDefinition).id))
    .map((c) => ({
      id: c.id,
      title: c.title || '',
      audio_track_id: c.audio_track_id || null,
      image_style: c.image_style || '',
      slides: (c.slides || []).map((s) => ({
        id: s.id || newSlideId(),
        passages: slidePassages(s),
        image_url: s.image_url || null,
        image_prompt: s.image_prompt || '',
      })),
    }))
}

/** An upper-case id from a title, unique among `taken` (`The Debt` -> `THE_DEBT`, `THE_DEBT_2`). */
export function suggestCutsceneId(title: string, taken: Set<string>): string {
  const plain = title.normalize('NFKD').replace(/[^\x20-\x7E]/g, '')
  const stem = plain.replace(/[^A-Za-z0-9]+/g, '_').replace(/^_+|_+$/g, '').toUpperCase().slice(0, ID_MAX) || 'CUTSCENE'
  let candidate = stem
  let number = 2
  while (taken.has(candidate)) {
    const suffix = `_${number}`
    candidate = `${stem.slice(0, ID_MAX - suffix.length)}${suffix}`
    number += 1
  }
  return candidate
}

/** A slide's passages; older data has one `text` instead. Always at least one entry. */
function slidePassages(slide: { passages?: unknown, text?: unknown }): string[] {
  const listed = Array.isArray(slide.passages) ? slide.passages.map((p) => String(p ?? '')) : []
  const legacy = typeof slide.text === 'string' && slide.text ? [slide.text] : []
  const passages = [...legacy, ...listed]
  return passages.length ? passages : ['']
}

/** All passages of a slide as one text (for the image prompt). */
export function slideText(slide: { passages: string[] }): string {
  return slide.passages.map((p) => p.trim()).filter(Boolean).join(' ')
}

export function newSlide(text = ''): CutsceneDefinitionSlide {
  return { id: newSlideId(), passages: [text], image_url: null, image_prompt: '' }
}

export function newCutscene(title: string, taken: Set<string>): CutsceneDefinition {
  return { id: suggestCutsceneId(title, taken), title, audio_track_id: null, image_style: '', slides: [newSlide()] }
}
