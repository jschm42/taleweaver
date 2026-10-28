/** Display label of a scene switch's current state, e.g. "ON" / "OFF". */
export function switchState(sw: any): string {
  return String(sw.switch_state || sw.metadata_json?.switch?.initial_state || '—').toUpperCase()
}
