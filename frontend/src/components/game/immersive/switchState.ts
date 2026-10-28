import { parseMetadata } from '../prompts/promptUtils'

function switchConfig(sw: any): Record<string, any> {
  const config = parseMetadata(sw?.metadata_json).switch
  return config && typeof config === 'object' ? config : {}
}

/** ID of a scene switch's current state, e.g. "ON" / "HALF-OPEN" (used for logic, not display). */
export function switchStateId(sw: any): string {
  return String(sw?.switch_state || switchConfig(sw).initial_state || '').toUpperCase()
}

/** In-game text of a state: its label, or the state ID when no label is set. */
export function stateLabel(sw: any, state: string): string {
  const id = String(state || '').toUpperCase()
  const labels = switchConfig(sw).state_labels
  const label = labels && typeof labels === 'object' ? String(labels[id] || '').trim() : ''
  return label || id
}

/** Display text of a scene switch's current state ("—" when unknown). */
export function switchState(sw: any): string {
  const id = switchStateId(sw)
  return id ? stateLabel(sw, id) : '—'
}
