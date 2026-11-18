import type { GameSession } from '@/types'
import { lastPlayedMs } from '@/utils/relativeTime'

/** The playable session the player opened most recently; the hero banner continues it. */
export function pickResumableSession(sessions: GameSession[]): GameSession | null {
  const playable = sessions.filter((s) => s.is_ready && (!s.status || s.status === 'active'))
  if (playable.length === 0) return null
  return playable.reduce((latest, s) => (lastPlayedMs(s) > lastPlayedMs(latest) ? s : latest))
}

/** Template id of a session (older sessions only carry `adventure_id`). */
export function sessionTemplateId(session: GameSession | null): string | null {
  return session ? session.template_id || session.adventure_id || null : null
}
