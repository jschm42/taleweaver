/**
 * Links a UiField with the control inside it: the control takes the field's id, its
 * description ids and its invalid state, so labels, hints and errors are announced.
 */
import { computed, inject, type ComputedRef, type InjectionKey } from 'vue'

export interface FieldContext {
  id: string
  describedBy: ComputedRef<string | undefined>
  invalid: ComputedRef<boolean>
  required: ComputedRef<boolean>
}

export const FIELD_CONTEXT: InjectionKey<FieldContext> = Symbol('ui-field')

export interface ControlBinding {
  id: ComputedRef<string | undefined>
  describedBy: ComputedRef<string | undefined>
  invalid: ComputedRef<boolean>
  required: ComputedRef<boolean>
}

/** Field wiring for a control; explicit props win over the surrounding UiField. */
export function useFieldControl(props: { id?: string; invalid?: boolean; required?: boolean }): ControlBinding {
  const field = inject(FIELD_CONTEXT, null)
  return {
    id: computed(() => props.id ?? field?.id),
    describedBy: computed(() => field?.describedBy.value),
    invalid: computed(() => Boolean(props.invalid) || Boolean(field?.invalid.value)),
    required: computed(() => Boolean(props.required) || Boolean(field?.required.value)),
  }
}

export const CONTROL_CLASS =
  'w-full rounded-md bg-wb-raised border text-wb-strong wb-body placeholder:text-wb-faint ' +
  'transition-colors focus:outline-none focus:ring-2 ' +
  'disabled:opacity-50 disabled:cursor-not-allowed'

/**
 * Full input look for shared components that only accept a class string
 * (e.g. `input-class` of ElevenLabsVoiceField). Prefer UiInput / UiSelect everywhere else.
 */
export const CONTROL_INPUT_CLASS =
  'w-full rounded-md bg-wb-raised border border-wb-line-strong text-wb-strong wb-body placeholder:text-wb-faint ' +
  'h-9 px-3 transition-colors focus:outline-none focus:ring-2 focus:border-wb-accent focus:ring-wb-accent/40'

/** Multi-line counterpart of CONTROL_INPUT_CLASS (e.g. `class-name` of ReferenceTextarea). */
export const CONTROL_TEXTAREA_CLASS =
  'w-full rounded-md bg-wb-raised border border-wb-line-strong text-wb-strong wb-body placeholder:text-wb-faint ' +
  'px-3 py-2 resize-y transition-colors focus:outline-none focus:ring-2 focus:border-wb-accent focus:ring-wb-accent/40'

/** Border and focus ring: accent normally, danger for an invalid value. */
export function controlBorder(invalid: boolean): string {
  return invalid
    ? 'border-wb-danger focus:border-wb-danger focus:ring-wb-danger/40'
    : 'border-wb-line-strong focus:border-wb-accent focus:ring-wb-accent/40'
}
