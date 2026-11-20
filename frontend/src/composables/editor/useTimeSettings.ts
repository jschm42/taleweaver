/**
 * Clock settings of the editor form for the Time & pacing page. Every setter writes to
 * `editor.form` (the shell's save bar saves it) and keeps `time_per_turn` / `max_time_per_turn`
 * in minutes in sync with the calendar value and unit shown on the page.
 */
import { computed, type ComputedRef } from 'vue'
import { useEditor } from '@/composables/editor/editorContext'
import {
  maxUnit,
  maxValue,
  pacingUnit,
  pacingValue,
  timeSettingErrors,
  unitMinutes,
  type TimeConfig,
  type TimeForm,
} from '@/utils/timeSettings'

export interface TimeSettings {
  form: TimeForm
  errors: ComputedRef<Record<string, string>>
  setConfig: (key: keyof TimeConfig, value: unknown) => void
  setPacingValue: (value: number | null) => void
  setPacingUnit: (unit: string) => void
  setMaxValue: (value: number | null) => void
  setMaxUnit: (unit: string) => void
}

export function useTimeSettings(): TimeSettings {
  const editor = useEditor()
  const form = editor.form as TimeForm

  const errors = computed(() => timeSettingErrors(form))

  function setConfig(key: keyof TimeConfig, value: unknown): void {
    form.time_config = { ...(form.time_config || {}), [key]: value }
  }

  function setPacingValue(value: number | null): void {
    const amount = value ?? 0
    setConfig('calendar_pacing_value', amount)
    form.time_per_turn = amount * unitMinutes(pacingUnit(form))
  }

  function setPacingUnit(unit: string): void {
    const amount = pacingValue(form)
    setConfig('calendar_pacing_unit', unit)
    form.time_per_turn = amount * unitMinutes(unit)
  }

  function setMaxValue(value: number | null): void {
    setConfig('calendar_max_value', value)
    form.max_time_per_turn = value === null ? null : value * unitMinutes(maxUnit(form))
  }

  function setMaxUnit(unit: string): void {
    const amount = maxValue(form)
    setConfig('calendar_max_unit', unit)
    if (amount !== null) form.max_time_per_turn = amount * unitMinutes(unit)
  }

  return { form, errors, setConfig, setPacingValue, setPacingUnit, setMaxValue, setMaxUnit }
}
