import { ref } from 'vue'

/** Inventory items the sheet treats as readable notes/books. */
export function isReadableItem(item: any): boolean {
  if (!item) return false
  const itemType = String(item.item_type || item.metadata_json?.item_type || '').toUpperCase()
  if (itemType === 'READABLE') return true
  const metadata = (item.metadata_json && typeof item.metadata_json === 'object') ? item.metadata_json : {}
  return Boolean(item.text_log_content || metadata.text_log_content)
}

export function isEquippable(item: any): boolean {
  return !!item?.slot || (Array.isArray(item?.wearable_slots) && item.wearable_slots.length > 0)
}

/** Items a click does something with (read, open, consume, equip). */
export function isInteractable(item: any): boolean {
  if (!item) return false
  if (isReadableItem(item)) return true
  const itemType = String(item.item_type || '').toUpperCase()
  if (itemType === 'CONTAINER' || itemType === 'CONSUMABLE') return true
  return isEquippable(item)
}

/** Remembers image paths that failed to load so the fallback icon is shown instead. */
export function useBrokenImages() {
  const broken = ref<Record<string, boolean>>({})

  const showImage = (path?: string | null): boolean => !!path && !broken.value[path]

  const handleImageError = (path?: string | null) => {
    if (!path) return
    broken.value[path] = true
  }

  return { showImage, handleImageError }
}
