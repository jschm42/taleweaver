import { ref } from 'vue'
import type { Ref } from 'vue'
import { entityService } from '@/services/entityService'
import type { EntityBundleKind } from '@/services/entityService'
import { notificationService } from '@/services/notificationService'
import { makeSafeFilename } from '@/utils/editor_utils'

const BUNDLE_EXTENSION = 'twe'
const KIND_LABELS: Record<EntityBundleKind, string> = {
  protagonist: 'Protagonist',
  npc: 'NPC',
  item: 'Item',
}
const PROTAGONIST_IMPORT_CONFIRM =
  'Importing replaces the current protagonist profile, stats, and portrait. Inventory and equipment are kept. Continue?'

export interface UseEntityTransferResult {
  isTransferring: Ref<boolean>
  exportEntity: (kind: EntityBundleKind, entityId: string | null, label: string) => Promise<void>
  importEntity: (kind: EntityBundleKind) => void
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

/**
 * Export/import of a single protagonist, NPC, or item as a .twe bundle (ZIP incl. image).
 */
export function useEntityTransfer(
  adventureId: () => string,
  onImported: () => Promise<void>,
): UseEntityTransferResult {
  const isTransferring = ref(false)

  async function exportEntity(kind: EntityBundleKind, entityId: string | null, label: string): Promise<void> {
    isTransferring.value = true
    try {
      const blob = await entityService.exportEntityBundle(adventureId(), kind, entityId || undefined)
      downloadBlob(blob, makeSafeFilename(`${kind}_${label || entityId || kind}`, BUNDLE_EXTENSION))
      notificationService.add(`${KIND_LABELS[kind]} exported.`, 'success')
    } catch (error: unknown) {
      notificationService.add(errorMessage(error, `Failed to export ${KIND_LABELS[kind]}.`), 'error')
    } finally {
      isTransferring.value = false
    }
  }

  async function runImport(kind: EntityBundleKind, file: File): Promise<void> {
    isTransferring.value = true
    try {
      const result = await entityService.importEntityBundle(adventureId(), file, kind)
      await onImported()
      const idSuffix = kind === 'protagonist' ? '' : ` as ${result.entity_id}`
      notificationService.add(`${KIND_LABELS[kind]} "${result.name}" imported${idSuffix}.`, 'success')
      result.warnings.forEach((warning) => notificationService.add(warning, 'info'))
    } catch (error: unknown) {
      notificationService.add(errorMessage(error, `Failed to import ${KIND_LABELS[kind]}.`), 'error')
    } finally {
      isTransferring.value = false
    }
  }

  function importEntity(kind: EntityBundleKind): void {
    if (kind === 'protagonist' && !confirm(PROTAGONIST_IMPORT_CONFIRM)) {
      return
    }
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = `.${BUNDLE_EXTENSION}`
    input.onchange = (): void => {
      const file = input.files?.[0]
      if (!file) {
        return
      }
      void runImport(kind, file)
    }
    input.click()
  }

  return { isTransferring, exportEntity, importEntity }
}
