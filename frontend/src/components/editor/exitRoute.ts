/** "From → To" parts for exit tiles; bidirectional exits use "↔". */

type SceneRef = { id?: string; label?: string; name?: string }
type ExitRef = { from_scene_id?: string; to_scene_id?: string; exit_type?: string }

export type ExitRoute = { from: string; to: string; text: string; bidirectional: boolean }

function sceneName(sceneId: string, scenes: SceneRef[]): string {
  const scene = scenes.find((entry) => String(entry?.id || '') === sceneId)
  return String(scene?.label || scene?.name || sceneId || '?')
}

export function exitRoute(worldExit: ExitRef, scenes: SceneRef[]): ExitRoute {
  const from = sceneName(String(worldExit?.from_scene_id || ''), scenes)
  const to = sceneName(String(worldExit?.to_scene_id || ''), scenes)
  const bidirectional = String(worldExit?.exit_type || '').toLowerCase() === 'bidirectional'
  return { from, to, bidirectional, text: `${from} ${bidirectional ? '↔' : '→'} ${to}` }
}
