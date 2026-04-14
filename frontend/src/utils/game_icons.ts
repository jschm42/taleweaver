/**
 * Shared utility for RPG Awesome icon mapping and themed colors.
 */

export const getItemIcon = (type?: string) => {
  switch (type?.toUpperCase()) {
    case 'CONSUMABLE': return 'ra-knife-fork'
    case 'WEAPON': return 'ra-knife' // ra-bowie-knife doesn't exist in 0.2.0
    case 'TOOL': return 'ra-wrench'
    case 'KEY': return 'ra-key'
    case 'COMBINABLE': return 'ra-gear-hammer' // ra-repair doesn't exist in 0.2.0
    case 'READABLE': return 'ra-book'
    case 'WEARABLE': return 'ra-helmet'
    case 'PICKABLE': return 'ra-hand'
    case 'STATIC': return 'ra-anchor'
    case 'NPC': return 'ra-player'
    case 'PLAYER': return 'ra-player'
    default: return 'ra-tower'
  }
}

export const getTypeColor = (type?: string) => {
  switch (type?.toUpperCase()) {
    case 'WEAPON': return 'text-rose-500'
    case 'CONSUMABLE': return 'text-emerald-500'
    case 'KEY': return 'text-amber-500'
    case 'TOOL': return 'text-sky-500'
    case 'READABLE': return 'text-indigo-400'
    case 'WEARABLE': return 'text-blue-500'
    case 'COMBINABLE': return 'text-fuchsia-500'
    case 'NPC': return 'text-amber-500'
    default: return 'text-slate-400'
  }
}

export const getImageUrl = (path?: string | null) => {
  if (!path) return ''
  if (path.startsWith('http')) return path
  // In dev, the frontend is on 5173 and backend on 8000
  const baseUrl = window.location.origin.replace('5173', '8000')
  return `${baseUrl}${path}`
}
