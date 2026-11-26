/**
 * Form state of the "Generate adventure" page and the pure steps around it: defaults, the
 * simple-mode reset, the title fallback, the create payload, the "Surprise me" preset and
 * reading a cover source adventure. No API calls here (see useCreateAdventure).
 */
import type { CatalogTile } from '@/types'

export type RuleMode = 'rpg' | 'story' | 'chat'
export type TimeSystem = 'calendar' | 'units'
export type GeneratorMode = 'simple' | 'advanced'

export interface TimeConfigData {
  day_label?: string
  initial_day?: number
  start_time?: string
  time_format?: '24h' | '12h'
  pacing_minutes?: number
  max_time_per_turn?: number | null
  unit_name?: string
  initial_units?: number
  units_per_turn?: number
  max_units_per_turn?: number | null
}

/** Min/max pairs of the world size section; null/null means "the AI decides". */
export type LimitKey = 'scenes' | 'items' | 'quests' | 'sequences' | 'containers' | 'text_logs' | 'awards'

export interface CreateAdventureForm {
  title: string
  storyIdea: string
  generation_strictness: 'creative' | 'strict'
  generate_npc_images: boolean
  generate_item_images: boolean
  generate_scene_images: boolean
  automatic_npc_voice_assignment: boolean
  automatic_cover_generation: boolean
  clock_enabled: boolean
  pacing_minutes: number
  rule_enforcement_mode: RuleMode
  selected_style_id: string
  selected_tone_id: string
  min_scenes: number | null
  max_scenes: number | null
  quest_generation_enabled: boolean
  min_quests: number | null
  max_quests: number | null
  min_items: number | null
  max_items: number | null
  container_generation_enabled: boolean
  scripts_generation_enabled: boolean
  auto_validate_and_fix: boolean
  min_sequences: number | null
  max_sequences: number | null
  min_containers: number | null
  max_containers: number | null
  text_log_generation_enabled: boolean
  min_text_logs: number | null
  max_text_logs: number | null
  can_damage_npcs: boolean
  npcs_can_damage_protagonist: boolean
  award_generation_enabled: boolean
  min_awards: number | null
  max_awards: number | null
  language: string
  cover_similarity_percent: number
  allow_reuse_source_assets: boolean
  time_auto: boolean
  time_system: TimeSystem
  time_config: TimeConfigData | null
}

export const TITLE_MAX_LENGTH = 50

const LIMIT_KEYS: LimitKey[] = ['scenes', 'items', 'quests', 'sequences', 'containers', 'text_logs', 'awards']

const MEDIA_KEYS = [
  'automatic_cover_generation',
  'generate_npc_images',
  'generate_item_images',
  'generate_scene_images',
  'automatic_npc_voice_assignment',
] as const

export function defaultForm(): CreateAdventureForm {
  return {
    title: '',
    storyIdea: '',
    generation_strictness: 'creative',
    generate_npc_images: true,
    generate_item_images: true,
    generate_scene_images: true,
    automatic_npc_voice_assignment: true,
    automatic_cover_generation: true,
    clock_enabled: true,
    pacing_minutes: 5,
    rule_enforcement_mode: 'story',
    selected_style_id: '',
    selected_tone_id: '',
    min_scenes: null,
    max_scenes: null,
    quest_generation_enabled: true,
    min_quests: null,
    max_quests: null,
    min_items: null,
    max_items: null,
    container_generation_enabled: true,
    scripts_generation_enabled: true,
    auto_validate_and_fix: true,
    min_sequences: null,
    max_sequences: null,
    min_containers: null,
    max_containers: null,
    text_log_generation_enabled: true,
    min_text_logs: null,
    max_text_logs: null,
    can_damage_npcs: false,
    npcs_can_damage_protagonist: false,
    award_generation_enabled: true,
    min_awards: null,
    max_awards: null,
    language: '',
    cover_similarity_percent: 50,
    allow_reuse_source_assets: true,
    time_auto: true,
    time_system: 'calendar',
    time_config: null,
  }
}

/** Simple mode lets the AI decide everything except story, play style, look and tone. */
export function applySimpleDefaults(form: CreateAdventureForm): void {
  form.scripts_generation_enabled = true
  form.time_auto = true
  for (const key of LIMIT_KEYS) {
    form[`min_${key}`] = null
    form[`max_${key}`] = null
  }
  form.quest_generation_enabled = true
  form.container_generation_enabled = true
  form.text_log_generation_enabled = true
  form.award_generation_enabled = true
  for (const key of MEDIA_KEYS) form[key] = true
  form.generation_strictness = 'creative'
}

/** First words of the story idea (without blueprint tags) as a title. */
export function deriveTitle(storyIdea: string): string {
  const clean = storyIdea.trim().replace(/^(\[.*?\]|\W)+/, '')
  const firstLine = (clean.split('\n')[0] || '').replace(/[.!?].*$/, '')
  const words = firstLine.split(/\s+/).slice(0, 5).join(' ')
  return words.slice(0, 45) || 'A New Adventure'
}

function catalogEntry(items: CatalogTile[], id: string): CatalogTile {
  return items.find((item) => item.id === id) || { id, name: id }
}

function timePayload(form: CreateAdventureForm): { config: Record<string, unknown> | null; pacing: number } {
  const tc = form.time_config
  if (form.time_auto || !tc) return { config: null, pacing: form.pacing_minutes || 5 }
  if (form.time_system === 'units') {
    return {
      config: {
        time_system: 'units',
        unit_name: tc.unit_name || 'Units',
        initial_units: tc.initial_units ?? 0,
        units_per_turn: tc.units_per_turn ?? 1,
        max_units_per_turn: tc.max_units_per_turn ?? null,
      },
      pacing: tc.units_per_turn ?? 1,
    }
  }
  return {
    config: {
      time_system: 'calendar',
      day_label: tc.day_label || 'Day',
      initial_day: tc.initial_day ?? 1,
      start_time: tc.start_time || '08:00',
      time_format: tc.time_format || '24h',
      pacing_minutes: tc.pacing_minutes ?? 5,
      max_time_per_turn: tc.max_time_per_turn ?? null,
    },
    pacing: tc.pacing_minutes ?? 5,
  }
}

export interface CoverSource {
  id: string
  title?: string
}

/** Request body of POST /adventures. Combat permissions only apply in RPG mode. */
export function buildCreatePayload(
  form: CreateAdventureForm,
  catalogs: { styles: CatalogTile[]; tones: CatalogTile[] },
  cover: CoverSource | null,
  id: string,
): Record<string, unknown> {
  const isRpg = form.rule_enforcement_mode === 'rpg'
  const time = timePayload(form)
  return {
    ...form,
    id,
    title: (form.title.trim() || 'Untitled Odyssey').slice(0, TITLE_MAX_LENGTH),
    original_prompt: form.storyIdea.trim(),
    time_system: form.time_system || 'calendar',
    time_per_turn: time.pacing,
    pacing_minutes: time.pacing,
    time_config: time.config,
    can_damage_npcs: isRpg ? form.can_damage_npcs : false,
    npcs_can_damage_protagonist: isRpg ? form.npcs_can_damage_protagonist : false,
    selected_image_styles: form.selected_style_id ? [catalogEntry(catalogs.styles, form.selected_style_id)] : [],
    selected_tone: form.selected_tone_id ? catalogEntry(catalogs.tones, form.selected_tone_id) : null,
    cover_source_adventure_id: cover ? cover.id : undefined,
    cover_source_adventure_name: cover ? cover.title || undefined : undefined,
    cover_similarity_percent: cover ? form.cover_similarity_percent : undefined,
    allow_reuse_source_assets: cover ? form.allow_reuse_source_assets : undefined,
  }
}

/** Catalog id for a value the LLM named by id or name (case-insensitive); unknown values stay. */
export function matchCatalogId(items: CatalogTile[], value: string): string {
  const needle = value.toLowerCase()
  const found = items.find((item) => item.id.toLowerCase() === needle || (item.name || '').toLowerCase() === needle)
  return found ? found.id : value
}

export interface SurprisePreset {
  title?: string
  story_idea?: string
  selected_tone?: string
  selected_style?: string
  rule_enforcement_mode?: RuleMode
  generate_scene_images?: boolean
  generate_npc_images?: boolean
  generate_item_images?: boolean
  clock_enabled?: boolean
  time_system?: TimeSystem
  pacing_minutes?: number
  unit_name?: string
  initial_units?: number
  units_per_turn?: number
  day_label?: string
  initial_day?: number
  start_time?: string
  time_format?: '24h' | '12h'
  min_scenes?: number
  max_scenes?: number
  min_quests?: number
  max_quests?: number
}

function presetTimeConfig(preset: SurprisePreset): TimeConfigData {
  if (preset.time_system === 'units') {
    return { unit_name: preset.unit_name || 'Units', initial_units: preset.initial_units ?? 0, units_per_turn: preset.units_per_turn ?? 1 }
  }
  return {
    day_label: preset.day_label || 'Day',
    initial_day: preset.initial_day ?? 1,
    start_time: preset.start_time || '08:00',
    time_format: preset.time_format || '24h',
    pacing_minutes: preset.pacing_minutes ?? 5,
  }
}

/** Copies a "Surprise me" preset into the form (only the fields the preset sets). */
export function applySurprisePreset(
  form: CreateAdventureForm,
  preset: SurprisePreset,
  catalogs: { styles: CatalogTile[]; tones: CatalogTile[] },
): void {
  if (preset.title) form.title = preset.title.slice(0, TITLE_MAX_LENGTH)
  if (preset.story_idea) form.storyIdea = preset.story_idea
  if (preset.selected_tone) form.selected_tone_id = matchCatalogId(catalogs.tones, preset.selected_tone)
  if (preset.selected_style) form.selected_style_id = matchCatalogId(catalogs.styles, preset.selected_style)
  if (preset.rule_enforcement_mode) form.rule_enforcement_mode = preset.rule_enforcement_mode
  const flags = ['generate_scene_images', 'generate_npc_images', 'generate_item_images', 'clock_enabled'] as const
  for (const key of flags) {
    if (preset[key] !== undefined) form[key] = preset[key] as boolean
  }
  if (preset.time_system) form.time_system = preset.time_system
  if (preset.pacing_minutes !== undefined) form.pacing_minutes = preset.pacing_minutes
  form.time_config = presetTimeConfig(preset)
  form.time_auto = false
  const limits = ['min_scenes', 'max_scenes', 'min_quests', 'max_quests'] as const
  for (const key of limits) {
    if (preset[key] !== undefined) form[key] = preset[key] as number
  }
}

function firstStyleId(adventure: Record<string, any>): string {
  const first = Array.isArray(adventure?.selected_image_styles) ? adventure.selected_image_styles[0] : null
  if (!first) return ''
  if (typeof first === 'string') return first
  return String(first.id || first.name || '').trim()
}

function toneId(adventure: Record<string, any>): string {
  const raw = adventure?.selected_tone
  if (!raw) return ''
  if (typeof raw === 'object') return String(raw.id || raw.name || '').trim()
  const trimmed = String(raw).trim()
  if (!trimmed.startsWith('{')) return trimmed
  try {
    const parsed = JSON.parse(trimmed)
    return String(parsed?.id || parsed?.name || '').trim()
  } catch {
    return trimmed
  }
}

function ruleMode(adventure: Record<string, any>): RuleMode | null {
  const raw = String(adventure?.rule_enforcement_mode || '').trim().toLowerCase()
  if (raw === 'rpg' || raw === 'story' || raw === 'chat') return raw
  return raw === 'strict' ? 'rpg' : null
}

/** Prefills the form from the adventure a cover is based on. Empty title and idea only. */
export function applyCoverSource(form: CreateAdventureForm, source: Record<string, any>): void {
  if (!form.title.trim()) form.title = `(Cover) ${source.title || 'Adventure'}`.slice(0, TITLE_MAX_LENGTH)
  if (!form.storyIdea.trim()) form.storyIdea = source.original_prompt || source.plot || source.teaser || ''
  form.selected_style_id = firstStyleId(source) || form.selected_style_id
  form.selected_tone_id = toneId(source) || form.selected_tone_id
  form.rule_enforcement_mode = ruleMode(source) || form.rule_enforcement_mode
  if (source.clock_enabled !== undefined) form.clock_enabled = !!source.clock_enabled
  if (source.time_system) form.time_system = source.time_system === 'units' ? 'units' : 'calendar'
  if (source.time_config) {
    form.time_config = source.time_config
    form.time_auto = false
  }
  form.scripts_generation_enabled = true
}
