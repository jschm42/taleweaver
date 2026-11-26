<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Feather, ImagePlus, Palette, Sparkles, Trash2, Upload } from 'lucide-vue-next'
import type { CatalogTile } from '@/types'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const props = withDefaults(defineProps<{
  isOpen: boolean
  isEditingExisting: boolean
  item: CatalogTile
  index: number | null
  type: 'styles' | 'tones'
  isGenerating?: boolean
  isSubmitting?: boolean
}>(), {
  isGenerating: false,
  isSubmitting: false,
})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', item: CatalogTile): void
  (e: 'generate', payload: { type: 'styles' | 'tones', item: CatalogTile, index: number | null, prompt?: string | null }): void
  (e: 'upload', payload: { event: Event, type: 'styles' | 'tones', item: CatalogTile, index: number | null }): void
}>()

const editingItem = ref<CatalogTile>({ ...props.item })
const showCustomPrompt = ref(false)
const customPromptInput = ref('')
const touched = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

watch(() => props.item, (newItem) => {
  editingItem.value = JSON.parse(JSON.stringify(newItem))
  showCustomPrompt.value = false
  customPromptInput.value = ''
  touched.value = false
}, { deep: true })

const copy = computed(() =>
  props.type === 'styles'
    ? { noun: 'image style', description: 'How the images of an adventure are rendered.', icon: Palette }
    : { noun: 'narrative tone', description: 'Mood and voice of the generated world and story.', icon: Feather },
)

const nameError = computed(() => (touched.value && !editingItem.value.name.trim() ? 'A name is required.' : null))

const handleSave = () => {
  touched.value = true
  if (!editingItem.value.name.trim()) return
  // Auto-generate ID from name if blank
  if (!editingItem.value.id.trim()) {
    editingItem.value.id = editingItem.value.name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
  }
  emit('save', editingItem.value)
}

const handleQuickGenerate = () => {
  emit('generate', { type: props.type, item: editingItem.value, index: props.index, prompt: null })
}

const handleCustomGenerate = () => {
  if (!customPromptInput.value.trim()) return
  emit('generate', { type: props.type, item: editingItem.value, index: props.index, prompt: customPromptInput.value.trim() })
}

const handleUpload = (event: Event) => {
  emit('upload', { event, type: props.type, item: editingItem.value, index: props.index })
}

function handleOpenChange(open: boolean): void {
  if (!open) emit('close')
}
</script>

<template>
  <UiModal
    :open="isOpen"
    :title="`${isEditingExisting ? 'Edit' : 'Add'} ${copy.noun}`"
    :description="copy.description"
    size="lg"
    :persistent="isSubmitting"
    @update:open="handleOpenChange"
  >
    <div class="space-y-5">
      <section class="flex flex-col gap-4 sm:flex-row sm:items-start">
        <div class="relative aspect-[2/3] w-28 shrink-0 overflow-hidden rounded-xl border border-wb-line bg-wb-raised">
          <img v-if="editingItem.image_url" :src="editingItem.image_url" :alt="editingItem.name" class="h-full w-full object-cover" />
          <div v-else class="flex h-full w-full flex-col items-center justify-center gap-1 text-wb-faint">
            <component :is="copy.icon" class="h-6 w-6" aria-hidden="true" />
            <span class="wb-hint !text-current">No image</span>
          </div>
          <div v-if="isGenerating" class="absolute inset-0 flex items-center justify-center bg-black/70">
            <UiSpinner label="Generating image" class="!text-wb-ai-text" />
          </div>
          <UiIconButton
            v-if="editingItem.image_url && !isGenerating"
            :icon="Trash2"
            label="Remove image"
            size="sm"
            variant="secondary"
            class="absolute right-1 top-1"
            @click="editingItem.image_url = ''"
          />
        </div>

        <div class="min-w-0 flex-1 space-y-2">
          <p class="wb-label">Cover image</p>
          <p class="wb-hint">Shown on the tile authors pick from.</p>
          <div class="flex flex-wrap gap-2">
            <UiButton
              variant="ai"
              size="sm"
              :icon="Sparkles"
              :loading="isGenerating"
              :disabled="!editingItem.name"
              title="Generate an image from the name and description"
              @click="handleQuickGenerate"
            >
              Generate image
            </UiButton>
            <UiButton size="sm" :icon="ImagePlus" :disabled="isGenerating" :aria-expanded="showCustomPrompt" @click="showCustomPrompt = !showCustomPrompt">
              From prompt
            </UiButton>
            <UiButton size="sm" :icon="Upload" @click="fileInput?.click()">Upload</UiButton>
            <input ref="fileInput" type="file" class="hidden" accept="image/*" @change="handleUpload" />
          </div>
          <div v-if="showCustomPrompt" class="flex flex-col gap-2 pt-1 sm:flex-row">
            <UiInput
              v-model="customPromptInput"
              aria-label="Image prompt"
              placeholder="e.g. Dark gothic oil painting with mist and amber candlelight"
              @keydown.enter.prevent="handleCustomGenerate"
            />
            <UiButton variant="ai" size="sm" class="sm:h-9" :disabled="!customPromptInput.trim() || isGenerating" @click="handleCustomGenerate">
              Generate
            </UiButton>
          </div>
        </div>
      </section>

      <UiField label="Name" required :error="nameError" :count="(editingItem.name || '').length" :max-length="30">
        <UiInput v-model="editingItem.name" maxlength="30" placeholder="e.g. Grim Dark Fantasy" data-autofocus />
      </UiField>

      <UiField
        label="Short description"
        hint="Shown to authors in the adventure creator."
        :count="(editingItem.description || '').length"
        :max-length="200"
      >
        <UiTextarea v-model="editingItem.description" :rows="2" maxlength="200" />
      </UiField>

      <UiField
        :label="type === 'styles' ? 'Style prompt' : 'Tone instruction'"
        info="Added to the AI prompt whenever this entry is used, e.g. lighting, line work or mood."
        :count="(editingItem.instruction || '').length"
        :max-length="500"
      >
        <UiTextarea
          v-model="editingItem.instruction"
          :rows="3"
          maxlength="500"
          mono
          placeholder="e.g. cinematic lighting, chiaroscuro, heavy ink lines, gritty realism"
        />
      </UiField>
    </div>

    <template #footer>
      <UiButton :disabled="isSubmitting" @click="emit('close')">Cancel</UiButton>
      <UiButton variant="primary" :loading="isSubmitting" @click="handleSave">Save</UiButton>
    </template>
  </UiModal>
</template>
