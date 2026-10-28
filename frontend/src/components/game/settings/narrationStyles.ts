/** Narration styles; ids mirror backend/core/narration_styles.py. */
export const NARRATION_STYLES = ['terse', 'dialogue', 'balanced', 'rich', 'epic'] as const

export type NarrationStyle = (typeof NARRATION_STYLES)[number]

export const DEFAULT_NARRATION_STYLE: NarrationStyle = 'balanced'

export type NarrationStyleOption = {
  id: NarrationStyle
  label: string
  length: string
  description: string
}

export const NARRATION_STYLE_OPTIONS: NarrationStyleOption[] = [
  {
    id: 'terse',
    label: 'Terse',
    length: '1-2 sentences',
    description: 'Quick story snippets. Only what changed and who reacts.',
  },
  {
    id: 'dialogue',
    label: 'Dialogue',
    length: 'Short beats, lots of talk',
    description: 'Plays like a radio drama. Characters talk; the narrator only bridges.',
  },
  {
    id: 'balanced',
    label: 'Balanced',
    length: '1-2 short paragraphs',
    description: 'Atmosphere and pace in balance. The default.',
  },
  {
    id: 'rich',
    label: 'Rich',
    length: '2-3 paragraphs',
    description: 'Descriptive prose with sensory detail and livelier characters.',
  },
  {
    id: 'epic',
    label: 'Epic',
    length: '3-5 paragraphs',
    description: 'Reads like a novel: deep atmosphere, tension and expansive dialogue.',
  },
]

export function isNarrationStyle(value: unknown): value is NarrationStyle {
  return typeof value === 'string' && (NARRATION_STYLES as readonly string[]).includes(value)
}
