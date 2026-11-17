/**
 * In-game clock settings of the adventure editor (`editor.form`): unit conversion for the
 * calendar system, validation and the HUD preview. Pure functions, shared by the Time & pacing
 * page and the editor's save bar (invalid settings block saving).
 */

export type TimeConfig = Record<string, unknown> & {
  start_time?: string
  day_label?: string
  initial_day?: number
  time_format?: '24h' | '12h'
  unit_name?: string
  initial_value?: number
  calendar_pacing_value?: number | null
  calendar_pacing_unit?: string
  calendar_max_value?: number | null
  calendar_max_unit?: string
}

export interface TimeForm {
  clock_enabled?: boolean
  time_system?: string
  time_per_turn?: number | null
  max_time_per_turn?: number | null
  gm_time_control?: boolean
  time_config?: TimeConfig | null
}

export const CALENDAR_UNITS = ['Minutes', 'Hours', 'Days', 'Weeks', 'Years'] as const

const UNIT_MINUTES: Record<string, number> = { minutes: 1, hours: 60, days: 1440, weeks: 10080, years: 525600 }
const LIMIT = 10000

export function unitMinutes(unit: string | undefined): number {
  return UNIT_MINUTES[String(unit || 'minutes').toLowerCase()] ?? 1
}

/** Largest calendar unit that divides the minutes evenly, as a value in that unit. */
function inLargestUnit(minutes: number): number {
  for (const factor of [525600, 10080, 1440, 60]) {
    if (minutes >= factor && minutes % factor === 0) return minutes / factor
  }
  return minutes
}

export const isUnitsSystem = (form: TimeForm): boolean => form.time_system === 'units'

export function pacingUnit(form: TimeForm): string {
  return form.time_config?.calendar_pacing_unit || 'Minutes'
}

export function pacingValue(form: TimeForm): number {
  const stored = form.time_config?.calendar_pacing_value
  if (stored !== undefined && stored !== null) {
    const parsed = Number(stored)
    return Number.isNaN(parsed) || parsed < 1 ? 5 : parsed
  }
  return inLargestUnit(form.time_per_turn || 5)
}

export function maxUnit(form: TimeForm): string {
  return form.time_config?.calendar_max_unit || 'Minutes'
}

/** GM limit in the chosen calendar unit; null when uncapped. */
export function maxValue(form: TimeForm): number | null {
  const stored = form.time_config?.calendar_max_value
  if (stored !== undefined && stored !== null) return Number(stored)
  if (form.max_time_per_turn === undefined || form.max_time_per_turn === null) return null
  return inLargestUnit(form.max_time_per_turn)
}

const isWhole = (value: number): boolean => Number.isFinite(value) && Number.isInteger(value)

function calendarErrors(form: TimeForm, cfg: TimeConfig): Record<string, string> {
  const errors: Record<string, string> = {}
  const dayLabel = String(cfg.day_label ?? 'Day').trim()
  if (!dayLabel) errors.day_label = 'A day label is required (e.g. "Day", "Sol").'
  else if (dayLabel.length > 30) errors.day_label = 'At most 30 characters.'

  const day = Number(cfg.initial_day ?? 1)
  if (!isWhole(day) || day < 1) errors.initial_day = 'A whole number of at least 1.'
  else if (day > LIMIT) errors.initial_day = 'At most 10,000.'

  if (!cfg.start_time || !/^([01]\d|2[0-3]):([0-5]\d)$/.test(cfg.start_time)) {
    errors.start_time = 'A time from 00:00 to 23:59.'
  }

  const pacing = pacingValue(form)
  if (!Number.isFinite(pacing) || pacing < 1) errors.pacing = 'At least 1.'
  else if (pacing > LIMIT) errors.pacing = 'At most 10,000.'

  const max = maxValue(form)
  if (max === null) return errors
  if (!Number.isFinite(max) || max < 1) errors.max_time = 'At least 1.'
  else if (max > LIMIT) errors.max_time = 'At most 10,000.'
  else if (max * unitMinutes(maxUnit(form)) < pacing * unitMinutes(pacingUnit(form))) {
    errors.max_time = 'Cannot be less than the time per turn.'
  }
  return errors
}

function unitsErrors(form: TimeForm, cfg: TimeConfig): Record<string, string> {
  const errors: Record<string, string> = {}
  const unitName = String(cfg.unit_name ?? 'Blobs').trim()
  if (!unitName) errors.unit_name = 'A unit name is required (e.g. "Lightyears").'
  else if (unitName.length > 30) errors.unit_name = 'At most 30 characters.'

  const initial = Number(cfg.initial_value ?? 0)
  if (!Number.isFinite(initial) || initial < 0) errors.initial_value = 'A number from 0 to 10,000.'
  else if (initial > LIMIT) errors.initial_value = 'At most 10,000.'

  const pacing = Number(form.time_per_turn ?? 1)
  if (!Number.isFinite(pacing) || pacing <= 0) errors.units_pacing = 'Greater than 0.'
  else if (pacing > LIMIT) errors.units_pacing = 'At most 10,000.'

  const max = form.max_time_per_turn
  if (max === null || max === undefined) return errors
  const maxNum = Number(max)
  if (!Number.isFinite(maxNum) || maxNum <= 0) errors.units_max = 'Greater than 0.'
  else if (maxNum > LIMIT) errors.units_max = 'At most 10,000.'
  else if (Number.isFinite(pacing) && maxNum < pacing) errors.units_max = 'Cannot be less than the time per turn.'
  return errors
}

/** Field errors of the clock settings (empty when the clock is off or everything is valid). */
export function timeSettingErrors(form: TimeForm): Record<string, string> {
  if (!form.clock_enabled) return {}
  const cfg = form.time_config || {}
  return isUnitsSystem(form) ? unitsErrors(form, cfg) : calendarErrors(form, cfg)
}

export interface ClockPreview {
  date: string
  time: string
  isUnits: boolean
}

/** What the in-game clock widget shows at the start of the adventure. */
export function clockPreview(form: TimeForm): ClockPreview {
  const cfg = form.time_config || {}
  if (isUnitsSystem(form)) {
    const initial = Number(cfg.initial_value ?? 0)
    return { date: String(cfg.unit_name || '').trim() || 'Blobs', time: Number.isNaN(initial) ? '0' : String(initial), isUnits: true }
  }
  const start = cfg.start_time || '08:00'
  const day = Math.max(1, Number(cfg.initial_day ?? 1) || 1)
  const date = `${String(cfg.day_label || '').trim() || 'Day'} ${day}`
  if (cfg.time_format !== '12h') return { date, time: start, isUnits: false }
  const [h, m] = start.split(':').map(Number)
  if (Number.isNaN(h) || Number.isNaN(m)) return { date, time: start, isUnits: false }
  const time = `${String(h % 12 || 12).padStart(2, '0')}:${String(m).padStart(2, '0')} ${h >= 12 ? 'PM' : 'AM'}`
  return { date, time, isUnits: false }
}

/** Splits "HH:MM" (24h) into the 12h hour, minute and AM/PM. */
export function to12h(start: string | undefined): { hour: number; minute: number; ampm: 'AM' | 'PM' } {
  const [h, m] = String(start || '08:00').split(':').map(Number)
  const hour24 = Number.isNaN(h) ? 8 : h
  return { hour: hour24 % 12 || 12, minute: Number.isNaN(m) ? 0 : m, ampm: hour24 >= 12 ? 'PM' : 'AM' }
}

/** Joins a 12h hour, minute and AM/PM into "HH:MM" (24h); values are clamped. */
export function from12h(hour: number, minute: number, ampm: 'AM' | 'PM'): string {
  const h12 = Math.max(1, Math.min(12, Number(hour) || 12))
  const m = Math.max(0, Math.min(59, Number(minute) || 0))
  const h24 = (h12 % 12) + (ampm === 'PM' ? 12 : 0)
  return `${String(h24).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}
