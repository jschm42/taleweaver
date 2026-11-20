import type { GameSession } from '@/types'
import { lastPlayedMs } from '@/utils/relativeTime'

/** Template id of a session (older sessions only carry `adventure_id`). */
export function sessionTemplateId(session: GameSession | null): string | null {
  return session ? session.template_id || session.adventure_id || null : null
}

/** Sessions the player can continue, most recently played first. */
export function playableSessions(sessions: GameSession[]): GameSession[] {
  return sessions
    .filter((s) => s.is_ready && (!s.status || s.status === 'active'))
    .sort((a, b) => lastPlayedMs(b) - lastPlayedMs(a))
}

/**
 * The most recently played session of each adventure, newest first, at most `limit` of them,
 * so several playthroughs of one adventure take a single card.
 */
export function pickRecentSessions(sessions: GameSession[], limit: number): GameSession[] {
  const seen = new Set<string>()
  const picked: GameSession[] = []
  for (const session of playableSessions(sessions)) {
    const key = sessionTemplateId(session) || session.game_id
    if (seen.has(key)) continue
    seen.add(key)
    picked.push(session)
    if (picked.length === limit) break
  }
  return picked
}
