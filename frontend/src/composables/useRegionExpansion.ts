/**
 * Offers regions the author built after a session started (docs/specs/world_sections.md, 9.7).
 * Asked once per region: a declined region is remembered in this browser and not offered again.
 */
import { api } from '@/composables/useApi'
import { useConfirm } from '@/composables/useDialogs'

const DECLINED_PREFIX = 'tw-region-expansion-declined:'

function readDeclined(gameId: string): string[] {
  try {
    const raw = localStorage.getItem(DECLINED_PREFIX + gameId)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.map(String) : []
  } catch {
    return []
  }
}

function writeDeclined(gameId: string, ids: string[]): void {
  try {
    localStorage.setItem(DECLINED_PREFIX + gameId, JSON.stringify(ids))
  } catch {
    // Storage unavailable (private window): the offer simply comes back next time.
  }
}

export function useRegionExpansion(gameId: () => string, reload: () => Promise<void>): { offer: () => Promise<void> } {
  const confirm = useConfirm()

  async function offer(): Promise<void> {
    const id = gameId()
    if (!id) return
    let pending
    try {
      pending = (await api.getSessionExpansion(id)).pending
    } catch {
      return
    }
    const declined = readDeclined(id)
    const fresh = pending.filter((region) => !declined.includes(region.id))
    if (!fresh.length) return
    const names = fresh.map((region) => region.label).join(', ')
    const ok = await confirm({
      title: fresh.length === 1 ? `New region: ${names}` : `New regions: ${names}`,
      message: 'The author added this to the adventure after you started. Add it to your journey? Your progress stays as it is.',
      confirmLabel: 'Add to my journey',
      cancelLabel: 'Not now',
    })
    if (!ok) {
      writeDeclined(id, [...declined, ...fresh.map((region) => region.id)])
      return
    }
    await api.applySessionExpansion(id)
    await reload()
  }

  return { offer }
}
