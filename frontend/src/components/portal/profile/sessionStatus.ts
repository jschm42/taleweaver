export type SessionFilter = 'all' | 'active' | 'completed' | 'game_over' | 'archived'

export interface SessionStatusMeta {
  label: string
  icon: string
  /** Badge (text + background) classes. */
  badge: string
  /** Card accent (border/ring) classes. */
  accent: string
}

const STATUS_META: Record<string, SessionStatusMeta> = {
  active: {
    label: 'In Progress',
    icon: 'ra ra-player-teleport',
    badge: 'bg-sky-500/15 text-sky-300 border-sky-400/30',
    accent: 'border-white/10 hover:border-sky-400/40',
  },
  completed: {
    label: 'Victory',
    icon: 'ra ra-trophy',
    badge: 'bg-amber-400/15 text-amber-200 border-amber-300/40',
    accent: 'border-amber-300/40 shadow-[0_0_24px_rgba(251,191,36,0.12)] hover:border-amber-300/70',
  },
  game_over: {
    label: 'Defeated',
    icon: 'ra ra-skull',
    badge: 'bg-red-500/15 text-red-300 border-red-400/40',
    accent: 'border-red-500/30 hover:border-red-400/60',
  },
  archived: {
    label: 'Archived',
    icon: 'ra ra-book',
    badge: 'bg-slate-500/15 text-slate-300 border-slate-400/30',
    accent: 'border-white/5 hover:border-white/20',
  },
}

export function sessionStatusMeta(status: string): SessionStatusMeta {
  return STATUS_META[status] ?? STATUS_META.active
}

export const SESSION_FILTERS: Array<{ key: SessionFilter, label: string }> = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'In Progress' },
  { key: 'completed', label: 'Victories' },
  { key: 'game_over', label: 'Defeats' },
  { key: 'archived', label: 'Archived' },
]

export function formatShortDate(value?: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}
