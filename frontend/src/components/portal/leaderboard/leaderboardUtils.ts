import type { LeaderboardEntry } from '@/types'

export type LeaderboardSortKey = 'rank' | 'awards' | 'completed' | 'failed'

export type RankTier = 'gold' | 'silver' | 'bronze' | 'plain'

export const SORT_OPTIONS: ReadonlyArray<{ key: LeaderboardSortKey; label: string }> = [
  { key: 'rank', label: 'Rank / XP' },
  { key: 'awards', label: 'Awards' },
  { key: 'completed', label: 'Completed' },
  { key: 'failed', label: 'Failed' },
]

/** Lower value sorts first; ties fall back to the server-side rank. */
const SORT_VALUE: Record<LeaderboardSortKey, (entry: LeaderboardEntry) => number> = {
  rank: (entry) => entry.rank,
  awards: (entry) => -entry.total_awards,
  completed: (entry) => -entry.completed_quests,
  failed: (entry) => -entry.failed_quests,
}

export function sortPlayers(players: LeaderboardEntry[], key: LeaderboardSortKey): LeaderboardEntry[] {
  const value = SORT_VALUE[key]
  return [...players].sort((a, b) => value(a) - value(b) || a.rank - b.rank)
}

export function filterPlayers(players: LeaderboardEntry[], query: string): LeaderboardEntry[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return players
  return players.filter((player) => player.username.toLowerCase().includes(needle))
}

export function rankTier(rank: number): RankTier {
  if (rank === 1) return 'gold'
  if (rank === 2) return 'silver'
  if (rank === 3) return 'bronze'
  return 'plain'
}

export function normalizeAvatarUrl(url?: string | null): string {
  return (url || '').replace(/\\/g, '/')
}

/** Same generated avatar the header and profile page show for users without a profile image. */
export function fallbackAvatarUrl(username?: string | null): string {
  return `https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(username || 'default')}`
}

export function playerAvatarUrl(url: string | null | undefined, username: string): string {
  return normalizeAvatarUrl(url) || fallbackAvatarUrl(username)
}

export function formatNumber(value: number): string {
  return value.toLocaleString('en-US')
}
