/**
 * Admin actions on the whole style or tone catalog: restore the built-in defaults, import a
 * catalog file and export the catalog. Restore and import merge by id (same id replaced, new
 * ids added, own entries kept) and save right away, like every other change on these pages.
 */
import { api } from '@/composables/useApi'
import { confirmDialog } from '@/composables/useDialogs'
import { useToast } from '@/composables/useToast'
import { catalogService } from '@/services/catalogService'
import type { CatalogTile } from '@/types'
import {
  buildCatalogFile,
  catalogFileName,
  catalogPlural,
  downloadJson,
  mergeCatalog,
  parseCatalogFile,
} from '@/components/admin/catalogTransfer'

type TileCatalog = 'styles' | 'tones'

function catalogRef(type: TileCatalog): { value: CatalogTile[] } {
  return type === 'styles' ? catalogService.imageStylesCatalog : catalogService.toneCatalog
}

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

export function useCatalogTransfer(): {
  restoreDefaults: (type: TileCatalog) => Promise<void>
  importFile: (type: TileCatalog, file: File) => Promise<void>
  exportCatalog: (type: TileCatalog) => void
} {
  const toast = useToast()

  async function applyMerge(type: TileCatalog, incoming: CatalogTile[], done: string): Promise<void> {
    const result = mergeCatalog(catalogRef(type).value, incoming)
    catalogRef(type).value = result.items
    await catalogService.saveCurrentCatalog(type)
    if (catalogService.statusMessage.value?.type === 'error') {
      toast.error(catalogService.statusMessage.value.text)
      return
    }
    toast.success(`${done}: ${result.replaced} updated, ${result.added} added.`)
  }

  async function restoreDefaults(type: TileCatalog): Promise<void> {
    const confirmed = await confirmDialog({
      title: `Restore the default ${catalogPlural(type)}?`,
      message: 'Built-in entries get their original text and image back; missing ones are added. Your own entries stay.',
      confirmLabel: 'Restore defaults',
    })
    if (!confirmed) return
    try {
      const { items } = await api.getCatalogDefaults(type)
      await applyMerge(type, items, 'Defaults restored')
    } catch (err) {
      toast.error(`Restoring the defaults failed: ${errorText(err)}`)
    }
  }

  async function importFile(type: TileCatalog, file: File): Promise<void> {
    let items: CatalogTile[]
    try {
      items = parseCatalogFile(await file.text(), type) as CatalogTile[]
    } catch (err) {
      toast.error(`Import failed: ${errorText(err)}`)
      return
    }
    const confirmed = await confirmDialog({
      title: `Import ${items.length} ${catalogPlural(type)}?`,
      message: 'Entries with an existing id are replaced, new ones are added. Entries missing from the file stay.',
      confirmLabel: 'Import',
    })
    if (!confirmed) return
    await applyMerge(type, items, 'Imported')
  }

  function exportCatalog(type: TileCatalog): void {
    downloadJson(catalogFileName(type), buildCatalogFile(type, catalogRef(type).value))
    toast.success(`Exported ${catalogRef(type).value.length} ${catalogPlural(type)}.`)
  }

  return { restoreDefaults, importFile, exportCatalog }
}
