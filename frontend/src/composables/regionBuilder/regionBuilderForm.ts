/**
 * Form state of the Region Builder and the pure steps around it: defaults, the stored
 * settings of a region, the simple-mode reset, size presets, the request payload and the token
 * labels. No API calls here (see useRegionBuilder). Spec: docs/specs/region_builder.md.
 */

export type RegionMode = 'simple' | 'advanced'
export type Detail = 'off' | 'compact' | 'full'
export type ContextKey = 'regions' | 'outline' | 'sequences' | 'quests' | 'plot' | 'rules' | 'npcs' | 'scenes' | 'items'
export type SizePreset = 'small' | 'medium' | 'large'
export type CountKey = 'scenes' | 'items' | 'quests' | 'sequences' | 'containers' | 'text_logs' | 'awards'

export type RegionContext = Record<ContextKey, Detail> & { walkthroughs: boolean }

export interface RegionOptions {
  generation_strictness: 'creative' | 'strict'
  min_scenes: number | null
  max_scenes: number | null
  min_items: number | null
  max_items: number | null
  min_quests: number | null
  max_quests: number | null
  min_sequences: number | null
  max_sequences: number | null
  min_containers: number | null
  max_containers: number | null
  min_text_logs: number | null
  max_text_logs: number | null
  min_awards: number | null
  max_awards: number | null
  quest_generation_enabled: boolean
  container_generation_enabled: boolean
  scripts_generation_enabled: boolean
  text_log_generation_enabled: boolean
  award_generation_enabled: boolean
}

export interface RegionBuilderForm {
  mode: RegionMode
  label: string
  description: string
  brief: string
  size: SizePreset
  context: RegionContext
  options: RegionOptions
}

/** What a region stores as `generation_settings` (POST .../generate keeps it). */
export interface StoredRegionSettings {
  mode?: string
  context?: Record<string, unknown>
  options?: Record<string, unknown>
}

export interface RegionSource {
  label: string
  description: string
  brief: string
  generation_settings?: StoredRegionSettings | null
}

export interface ContextOptionInfo {
  key: ContextKey
  label: string
  description: string
  /** Offers compact / full in advanced mode (plot, rules and the outline have one level). */
  hasDetail: boolean
}

/** Display order of the World context card (spec 5.1). */
export const CONTEXT_OPTIONS: ContextOptionInfo[] = [
  { key: 'regions', label: 'Other regions', description: 'Names, summaries and links of the other regions.', hasDetail: true },
  { key: 'outline', label: 'Campaign outline', description: 'Premise, arc and the story threads that run across regions.', hasDetail: false },
  { key: 'sequences', label: 'Chapters', description: 'The existing chapters with their goals.', hasDetail: true },
  { key: 'quests', label: 'Quests', description: 'Side quests with their goals and requirements.', hasDetail: true },
  { key: 'plot', label: 'Global plot', description: 'The adventure teaser and plot.', hasDetail: false },
  { key: 'rules', label: 'World rules', description: 'The rules text, combat damage and the game-over rule.', hasDetail: false },
  { key: 'npcs', label: 'Characters', description: 'Existing characters and where they are.', hasDetail: true },
  { key: 'scenes', label: 'Scenes', description: 'Existing scenes, grouped by region.', hasDetail: true },
  { key: 'items', label: 'Items', description: 'Existing items, where they are and what they unlock.', hasDetail: true },
]

export const DEFAULT_CONTEXT: RegionContext = {
  regions: 'full',
  outline: 'full',
  sequences: 'full',
  quests: 'full',
  plot: 'full',
  rules: 'full',
  npcs: 'compact',
  scenes: 'compact',
  items: 'compact',
  walkthroughs: true,
}

export const SIZE_PRESETS: Record<SizePreset, { label: string; scenes: [number, number] }> = {
  small: { label: 'Small', scenes: [3, 5] },
  medium: { label: 'Medium', scenes: [6, 10] },
  large: { label: 'Large', scenes: [11, 16] },
}

/** Above this the token total turns into a warning (spec 5.4). */
export const LARGE_PROMPT_TOKENS = 40000

const DETAILS: Detail[] = ['off', 'compact', 'full']

export function defaultOptions(): RegionOptions {
  return {
    generation_strictness: 'creative',
    min_scenes: null,
    max_scenes: null,
    min_items: null,
    max_items: null,
    min_quests: null,
    max_quests: null,
    min_sequences: null,
    max_sequences: null,
    min_containers: null,
    max_containers: null,
    min_text_logs: null,
    max_text_logs: null,
    min_awards: null,
    max_awards: null,
    quest_generation_enabled: true,
    container_generation_enabled: true,
    scripts_generation_enabled: true,
    text_log_generation_enabled: true,
    award_generation_enabled: true,
  }
}

function storedContext(raw: Record<string, unknown> | undefined): RegionContext {
  const context: RegionContext = { ...DEFAULT_CONTEXT }
  for (const option of CONTEXT_OPTIONS) {
    const value = raw?.[option.key]
    if (DETAILS.includes(value as Detail)) context[option.key] = value as Detail
  }
  if (raw?.walkthroughs === false) context.walkthroughs = false
  return context
}

function storedOptions(raw: Record<string, unknown> | undefined): RegionOptions {
  const options = defaultOptions() as unknown as Record<string, unknown>
  for (const [key, fallback] of Object.entries(options)) {
    const value = raw?.[key]
    if (value === undefined) continue
    const sameType = typeof value === typeof fallback || (fallback === null && typeof value === 'number')
    if (sameType || (typeof fallback === 'number' && value === null)) options[key] = value
  }
  if (!['creative', 'strict'].includes(String(options.generation_strictness))) options.generation_strictness = 'creative'
  return options as unknown as RegionOptions
}

function presetOf(options: RegionOptions): SizePreset {
  const match = (Object.keys(SIZE_PRESETS) as SizePreset[]).find((key) => {
    const [low, high] = SIZE_PRESETS[key].scenes
    return options.min_scenes === low && options.max_scenes === high
  })
  return match || 'medium'
}

/** The form for a region: its last stored settings, or the defaults. */
export function formFor(region: RegionSource): RegionBuilderForm {
  const stored = region.generation_settings || null
  const options = storedOptions(stored?.options)
  return {
    mode: stored?.mode === 'advanced' ? 'advanced' : 'simple',
    label: region.label,
    description: region.description,
    brief: region.brief,
    size: presetOf(options),
    context: storedContext(stored?.context),
    options,
  }
}

/** Simple mode: every option back to its default, context keeps on / off at default detail. */
export function applySimpleDefaults(form: RegionBuilderForm): void {
  form.options = defaultOptions()
  for (const option of CONTEXT_OPTIONS) {
    if (form.context[option.key] !== 'off') form.context[option.key] = DEFAULT_CONTEXT[option.key]
  }
  form.context.walkthroughs = true
}

export function isContextOn(form: RegionBuilderForm, key: ContextKey): boolean {
  return form.context[key] !== 'off'
}

export function setContextOn(form: RegionBuilderForm, key: ContextKey, on: boolean): void {
  form.context[key] = on ? DEFAULT_CONTEXT[key] : 'off'
}

export function setAllContext(form: RegionBuilderForm, on: boolean): void {
  for (const option of CONTEXT_OPTIONS) setContextOn(form, option.key, on)
}

/** The options sent: in simple mode the defaults with the size preset's scene range. */
export function payloadOptions(form: RegionBuilderForm): RegionOptions {
  if (form.mode === 'advanced') return { ...form.options }
  const [low, high] = SIZE_PRESETS[form.size].scenes
  return { ...defaultOptions(), min_scenes: low, max_scenes: high }
}

/** Request body of POST .../sections/{id}/generate (and of its preview). */
export function buildPayload(form: RegionBuilderForm): Record<string, unknown> {
  return {
    brief: form.brief.trim(),
    mode: form.mode,
    context: { ...form.context },
    options: payloadOptions(form),
  }
}

/** `≈ 840 tokens`, `≈ 1.2k tokens`. */
export function formatTokens(tokens: number): string {
  if (tokens < 1000) return `≈ ${tokens} tokens`
  return `≈ ${(tokens / 1000).toFixed(tokens < 10000 ? 1 : 0)}k tokens`
}
