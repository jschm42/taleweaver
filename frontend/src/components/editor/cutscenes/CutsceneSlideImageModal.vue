<script setup lang="ts">
/**
 * The image of one cut-scene slide: draw it with the image model (editable prompt, LQ or HQ
 * model, in the cut-scene's own image style or the adventure's, optionally with the tone),
 * upload an own image or remove it. While an image is drawn every control is locked and
 * **Cancel** stops waiting for it. The result goes into the page's draft (`update`).
 */
import { onBeforeUnmount, ref, watch } from 'vue'
import { Sparkles, Trash2, Upload, X } from 'lucide-vue-next'
import { useToast } from '@/composables/useToast'
import { cutsceneService, type SlideImageQuality } from '@/services/cutsceneService'
import type { CutsceneDefinitionSlide } from '@/types'
import { getImageUrl } from '@/utils/game_icons'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const QUALITY_OPTIONS: { value: SlideImageQuality, label: string }[] = [
  { value: 'simple', label: 'LQ · Simple model' },
  { value: 'advanced', label: 'HQ · High-fidelity model' },
]

const open = defineModel<boolean>('open', { default: false })

const props = defineProps<{
  adventureId: string
  slide: CutsceneDefinitionSlide | null
  cutsceneTitle: string
  /** The cut-scene's image style override ('' = the adventure's style). */
  imageStyle: string
}>()

const emit = defineEmits<{
  (e: 'update', value: { image_url: string | null, image_prompt: string }): void
}>()

const toast = useToast()
const prompt = ref('')
const style = ref('')
const tone = ref('')
const useStyle = ref(true)
const useTone = ref(false)
const quality = ref<SlideImageQuality>('advanced')
const loading = ref(false)
const drawing = ref(false)
const uploading = ref(false)
const imageUrl = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
let drawRequest: AbortController | null = null

async function load(): Promise<void> {
  const slide = props.slide
  if (!slide) return
  imageUrl.value = slide.image_url || null
  loading.value = true
  try {
    const info = await cutsceneService.slidePrompt(props.adventureId, props.cutsceneTitle, slide.text, props.imageStyle)
    prompt.value = slide.image_prompt || info.prompt
    style.value = info.style
    tone.value = info.tone
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Failed to load the image prompt.')
  } finally {
    loading.value = false
  }
}

function cancel(): void {
  drawRequest?.abort()
}

watch(open, (isOpen) => {
  if (isOpen) void load()
  else cancel()
})

onBeforeUnmount(cancel)

async function draw(): Promise<void> {
  const request = new AbortController()
  drawRequest = request
  drawing.value = true
  try {
    const result = await cutsceneService.generateImage(
      props.adventureId,
      {
        prompt: prompt.value,
        image_style: props.imageStyle,
        use_style: useStyle.value,
        use_tone: useTone.value,
        quality: quality.value,
      },
      request.signal,
    )
    imageUrl.value = result.url
    emit('update', { image_url: result.url, image_prompt: prompt.value })
  } catch (error: unknown) {
    if (request.signal.aborted) toast.info('Image generation cancelled.')
    else toast.error(error instanceof Error ? error.message : 'Failed to generate the image.')
  } finally {
    if (drawRequest === request) drawRequest = null
    drawing.value = false
  }
}

async function upload(file: File | undefined): Promise<void> {
  if (fileInput.value) fileInput.value.value = ''
  if (!file) return
  uploading.value = true
  try {
    const result = await cutsceneService.uploadImage(props.adventureId, file)
    imageUrl.value = result.url
    emit('update', { image_url: result.url, image_prompt: prompt.value })
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Failed to upload the image.')
  } finally {
    uploading.value = false
  }
}

function remove(): void {
  imageUrl.value = null
  emit('update', { image_url: null, image_prompt: prompt.value })
}

function short(text: string): string {
  return text.length > 140 ? `${text.slice(0, 140)}...` : text || 'none set'
}
</script>

<template>
  <UiModal
    v-model:open="open"
    title="Slide image"
    description="Draw the image from a prompt or upload your own. Wide 16:9 images fill the screen best."
    size="lg"
    :persistent="drawing || uploading"
  >
    <div class="space-y-4">
      <div class="relative aspect-[16/9] overflow-hidden rounded-md border border-wb-line bg-wb-sunken">
        <img v-if="imageUrl" :src="getImageUrl(imageUrl) || imageUrl" alt="" :class="['absolute inset-0 h-full w-full object-cover', drawing && 'opacity-40']" />
        <p v-else-if="!drawing" class="absolute inset-0 flex items-center justify-center wb-hint">No image yet: the slide shows on the theme's background.</p>
        <div v-if="drawing" class="absolute inset-0 flex items-center justify-center">
          <UiSpinner label="Drawing the image" />
        </div>
      </div>
      <UiSpinner v-if="loading" label="Loading the prompt" />
      <fieldset v-else :disabled="drawing || uploading" class="space-y-4">
        <UiField label="Prompt" hint="Describes the picture; written from the slide text, edit it freely.">
          <UiTextarea v-model="prompt" :rows="4" :disabled="drawing || uploading" />
        </UiField>
        <UiField label="Image model" hint="LQ is fast and cheap for drafts; HQ takes longer and looks better.">
          <UiSegmented v-model="quality" :options="QUALITY_OPTIONS" label="Image model" :disabled="drawing || uploading" />
        </UiField>
        <UiCheckbox
          v-model="useStyle"
          :label="props.imageStyle ? 'Add the cut-scene\'s image style' : 'Add the adventure\'s image style'"
          :description="short(style)"
          :disabled="drawing || uploading"
        />
        <UiCheckbox v-model="useTone" label="Add the adventure's tone" :description="short(tone)" :disabled="drawing || uploading" />
      </fieldset>
    </div>
    <template #footer>
      <input ref="fileInput" type="file" class="hidden" accept="image/png,image/jpeg,image/webp" @change="upload(($event.target as HTMLInputElement).files?.[0])" />
      <UiButton v-if="drawing" :icon="X" @click="cancel">Cancel</UiButton>
      <template v-else>
        <UiButton v-if="imageUrl" variant="danger" :icon="Trash2" :disabled="uploading" @click="remove">Remove</UiButton>
        <UiButton :icon="Upload" :loading="uploading" :disabled="loading" @click="fileInput?.click()">Upload image</UiButton>
      </template>
      <UiButton variant="ai" :icon="Sparkles" :loading="drawing" :disabled="loading || uploading || !prompt.trim()" @click="draw">
        {{ imageUrl ? 'Redraw' : 'Draw image' }}
      </UiButton>
    </template>
  </UiModal>
</template>
