/**
 * gameClockTime — parsing of the in-game time shown by the footer clock.
 *
 * The backend sends the time as "HH:MM" or "hh:MM AM/PM" (calendar systems) or as a value in a
 * custom time unit (`isUnits`), which has no time of day.
 */

export interface GameTimeView {
  dateShort: string
  time: string
  isUnits?: boolean
  unitName?: string
  value?: string
}

export type DayPhase = 'dawn' | 'day' | 'dusk' | 'night'

export const DAY_PHASE_LABELS: Record<DayPhase, string> = {
  dawn: 'Dawn',
  day: 'Daytime',
  dusk: 'Dusk',
  night: 'Night',
}

/** Minutes since midnight, or null for time units and unparseable times. */
export function minuteOfDay(gameTime: GameTimeView | null | undefined): number | null {
  if (!gameTime || gameTime.isUnits) {
    return null
  }
  const match = /(\d{1,2}):(\d{2})\s*(AM|PM)?/i.exec(gameTime.time)
  if (!match) {
    return null
  }
  const meridiem = match[3]?.toUpperCase()
  let hours = Number(match[1]) % (meridiem ? 12 : 24)
  if (meridiem === 'PM') {
    hours += 12
  }
  return hours * 60 + Number(match[2])
}

/** Time of day for a minute of the day (noon when unknown). */
export function dayPhase(minute: number | null): DayPhase {
  const hour = (minute ?? 12 * 60) / 60
  if (hour >= 5 && hour < 7) {
    return 'dawn'
  }
  if (hour >= 7 && hour < 18) {
    return 'day'
  }
  if (hour >= 18 && hour < 20) {
    return 'dusk'
  }
  return 'night'
}
