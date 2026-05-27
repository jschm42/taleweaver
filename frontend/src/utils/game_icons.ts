/**
 * Shared utility for RPG Awesome icon mapping and themed colors.
 */

export const getItemIcon = (type?: string) => {
  switch (type?.toUpperCase()) {
    case 'CONSUMABLE': return 'ra-potion'
    case 'WEAPON': return 'ra-bowie-knife'
    case 'TOOL': return 'ra-wrench'
    case 'KEY': return 'ra-key'
    case 'KEYS': return 'ra-key'
    case 'COMBINABLE': return 'ra-wrench'
    case 'WEARABLE': return 'ra-helmet'
    case 'NPC': return 'ra-player'
    case 'PLAYER': return 'ra-player'
    case 'SCENE': return 'ra-mountains'
    default: return 'ra-emerald'
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

export const getImageUrl = (path?: string | null, options?: { thumbnail?: boolean }) => {
  if (!path) return ''
  const normalizedPath = normalizeGameImagePath(path)
  if (!normalizedPath || isPlaceholderImagePath(normalizedPath)) return ''
  
  let finalPath = normalizedPath
  if (options?.thumbnail) {
    const extIdx = normalizedPath.lastIndexOf('.')
    if (extIdx !== -1) {
      finalPath = normalizedPath.substring(0, extIdx) + '_thumb' + normalizedPath.substring(extIdx)
    }
  }

  const cacheVersion = localStorage.getItem('tw_visual_cache_version') || '0'
  const separator = finalPath.includes('?') ? '&' : '?'
  return `${finalPath}${separator}v=${cacheVersion}`
}

const normalizeGameImagePath = (path?: string | null): string => {
  if (!path) return ''
  const trimmed = path.trim()
  if (!trimmed) return ''

  // Preserve fully-qualified and special browser URLs.
  if (/^(https?:|data:|blob:)/i.test(trimmed)) {
    return trimmed
  }
  if (trimmed.startsWith('/data/')) {
    return trimmed
  }

  // Legacy backend payloads may provide relative data-root paths.
  if (trimmed.startsWith('/')) {
    return `/data${trimmed}`
  }
  return `/data/${trimmed.replace(/^\/+/, '')}`
}

export const isPlaceholderImagePath = (path?: string | null): boolean => {
  if (!path) return true
  const normalized = path.trim().toLowerCase()
  if (!normalized) return true
  return /(^|\/)placeholder\.svg(\?|$)/.test(normalized)
}

export const hasRenderableImagePath = (path?: string | null): boolean => {
  return Boolean(path && path.trim() && !isPlaceholderImagePath(path))
}

