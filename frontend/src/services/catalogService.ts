import { ref } from 'vue'
import { api } from '@/composables/useApi'
import type { CatalogTile } from '@/types'

/**
 * CatalogService manages image styles and narrative tones catalogs:
 * - Fetching catalogs from backend
 * - Adding, editing, removing catalog items
 * - Generating images using AI
 * - Uploading custom images
 *
 * Each catalog item has an id, name, description, instruction, and optional image_url.
 * The service handles CRUD operations and integrates with the image generation API.
 */
class CatalogService {
  // ============ STATE ============
  imageStylesCatalog = ref<CatalogTile[]>([])
  toneCatalog = ref<CatalogTile[]>([])
  isSubmitting = ref(false)
  statusMessage = ref<{ type: 'success' | 'error'; text: string } | null>(null)
  isGeneratingItem = ref<Record<string, boolean>>({})

  // ============ HYDRATION ============

  /**
   * Hydrate both admin-managed catalogs from a settings payload.
   * Falls back to empty arrays so admin views render predictably.
   */
  hydrateCatalogs(payload: {
    image_styles_catalog?: CatalogTile[] | null
    tone_catalog?: CatalogTile[] | null
  }) {
    this.imageStylesCatalog.value = payload.image_styles_catalog || []
    this.toneCatalog.value = payload.tone_catalog || []
  }

  // ============ UTILITIES ============

  /**
   * Convert a string to a URL-safe slug.
   * Used to generate IDs from item names.
   * Example: "My Test Item" → "my-test-item"
   */
  private slugify(value: string): string {
    return (
      value
        .toLowerCase()
        .trim()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '') || 'item'
    )
  }

  // ============ CATALOG ITEM MANAGEMENT ============

  /**
   * Save a catalog item (add new or update existing).
   * Validates that the item has a name and normalizes the data.
   * Type determines which catalog to modify: 'styles' or 'tones'.
   */
  saveItem(type: 'styles' | 'tones', item: CatalogTile, index: number | null = null) {
    if (!item.name?.trim()) {
      this.statusMessage.value = { type: 'error', text: 'Name is required.' }
      return
    }

    // Normalize item data
    const normalizedItem: CatalogTile = {
      ...item,
      id: item.id?.trim() || this.slugify(item.name),
      name: item.name.trim(),
      description: (item.description || '').trim(),
      instruction: (item.instruction || '').trim(),
      image_url: (item.image_url || '').trim() || null,
    }

    // Get the appropriate catalog
    const catalog = type === 'styles' ? this.imageStylesCatalog : this.toneCatalog

    // Add or update
    if (index !== null) {
      catalog.value[index] = normalizedItem
    } else {
      catalog.value.push(normalizedItem)
    }
  }

  /**
   * Remove a catalog item by index.
   * Requires user confirmation before deletion.
   */
  removeItem(type: 'styles' | 'tones', index: number) {
    if (!confirm('Are you sure you want to delete this item?')) {
      return
    }

    const catalog = type === 'styles' ? this.imageStylesCatalog : this.toneCatalog
    catalog.value.splice(index, 1)
  }

  // ============ CATALOG PERSISTENCE ============

  /**
   * Save the entire styles catalog to the backend.
   */
  async saveStylesCatalog() {
    this.isSubmitting.value = true
    this.statusMessage.value = null

    try {
      await api.saveImageStylesCatalog(this.imageStylesCatalog.value)
      this.statusMessage.value = { type: 'success', text: 'Image styles updated.' }
    } catch {
      console.error('[CatalogService] Failed to save image styles catalog')
      this.statusMessage.value = { type: 'error', text: 'Failed to save image styles.' }
    } finally {
      this.isSubmitting.value = false
    }
  }

  /**
   * Save the entire tones catalog to the backend.
   */
  async saveToneCatalog() {
    this.isSubmitting.value = true
    this.statusMessage.value = null

    try {
      await api.saveToneCatalog(this.toneCatalog.value)
      this.statusMessage.value = { type: 'success', text: 'Tones updated.' }
    } catch {
      console.error('[CatalogService] Failed to save tone catalog')
      this.statusMessage.value = { type: 'error', text: 'Failed to save tones.' }
    } finally {
      this.isSubmitting.value = false
    }
  }

  /**
   * Save the current catalog (whichever was being edited).
   * Type defaults to the current modal type or can be explicitly specified.
   */
  async saveCurrentCatalog(type: 'styles' | 'tones') {
    if (type === 'styles') {
      await this.saveStylesCatalog()
    } else {
      await this.saveToneCatalog()
    }
  }

  // ============ IMAGE GENERATION & UPLOAD ============

  /**
   * Generate an image for a catalog item using AI.
   * Requires that a simple T2I model is configured.
   * Optional custom prompt can override the auto-generated one.
   */
  async generateImage(
    type: 'styles' | 'tones',
    item: CatalogTile,
    simpleModel: string,
    index: number | null = null,
    customPrompt: string | null = null,
  ) {
    // Validate: need a model configured
    if (!simpleModel) {
      this.statusMessage.value = {
        type: 'error',
        text: 'Please configure and save the "Simple Model" in Visual Preferences before generating catalog images.',
      }
      return
    }

    // Validate: item needs a name or ID
    const targetId = item.id || this.slugify(item.name)
    if (!targetId) {
      this.statusMessage.value = { type: 'error', text: 'Please provide a name before generating an image.' }
      return
    }

    // Set loading state
    const loadingKey = index !== null ? `${type}_${index}` : 'modal_generating'
    this.isGeneratingItem.value[loadingKey] = true

    try {
      const data = await api.generateCatalogImage({
        target_id: targetId,
        catalog_type: type,
        prompt: customPrompt,
        name: item.name,
        description: item.description,
      })

      if (data.status === 'success') {
        item.image_url = data.image_url

        // If editing an existing item, also save to catalog
        if (index !== null) {
          const catalog = type === 'styles' ? this.imageStylesCatalog : this.toneCatalog
          catalog.value[index].image_url = data.image_url
          await this.saveCurrentCatalog(type)
        }

        this.statusMessage.value = { type: 'success', text: 'Image generated successfully!' }
      } else {
        this.statusMessage.value = { type: 'error', text: data.message || 'Generation failed.' }
      }
    } catch (error) {
      console.error('[CatalogService] Image generation error:', error)
      this.statusMessage.value = { type: 'error', text: 'Error during image generation.' }
    } finally {
      this.isGeneratingItem.value[loadingKey] = false
    }
  }

  /**
   * Upload a custom image file for a catalog item.
   */
  async uploadImage(
    event: Event,
    type: 'styles' | 'tones',
    item: CatalogTile,
    index: number | null = null,
  ) {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)
    formData.append('catalog_type', type)
    formData.append('target_id', item.id || this.slugify(item.name))

    try {
      const data = await api.uploadCatalogImage(formData)
      if (data.status === 'success') {
        item.image_url = data.image_url

        // If editing an existing item, also save to catalog
        if (index !== null) {
          const catalog = type === 'styles' ? this.imageStylesCatalog : this.toneCatalog
          catalog.value[index].image_url = data.image_url
          await this.saveCurrentCatalog(type)
        }

        this.statusMessage.value = { type: 'success', text: 'Image uploaded successfully!' }
      } else {
        this.statusMessage.value = { type: 'error', text: data.message || 'Upload failed.' }
      }
    } catch (error) {
      console.error('[CatalogService] Image upload error:', error)
      this.statusMessage.value = { type: 'error', text: 'Error during image upload.' }
    } finally {
      input.value = ''
    }
  }
}

export const catalogService = new CatalogService()
