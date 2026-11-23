<script setup lang="ts">
/**
 * One cut-scene of the library: id, title, image style override, audio track and its slides.
 * Edits go into the page's draft; the page saves the whole list.
 */
import { computed, ref } from 'vue'
import { Play, Plus, Trash2 } from 'lucide-vue-next'
import { MAX_SLIDES, newSlide } from '@/services/cutsceneService'
import type { CutsceneDefinition, CutsceneDefinitionSlide } from '@/types'
import UiButton from '@/components/ui/UiButton.vue'
import UiCombobox from '@/components/ui/UiCombobox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiSelect, { type SelectOption } from '@/components/ui/UiSelect.vue'
import CutsceneSlideRow from './CutsceneSlideRow.vue'
import CutsceneSlideImageModal from './CutsceneSlideImageModal.vue'

const cutscene = defineModel<CutsceneDefinition>({ required: true })

const props = defineProps<{
  adventureId: string
  /** Ids of the other cut-scenes (an id must be unique). */
  otherIds: string[]
  styleNames: string[]
  audioTracks: { id: string, name?: string }[]
  /** Titles of the chapters that start with this cut-scene. */
  usedBy: string[]
}>()

defineEmits<{ (e: 'preview'): void, (e: 'delete'): void }>()

const imageSlideIndex = ref<number | null>(null)
const imageOpen = computed({
  get: () => imageSlideIndex.value !== null,
  set: (value: boolean) => {
    if (!value) imageSlideIndex.value = null
  },
})
const imageSlide = computed<CutsceneDefinitionSlide | null>(() =>
  imageSlideIndex.value === null ? null : cutscene.value.slides[imageSlideIndex.value] ?? null,
)

const idError = computed(() => {
  const id = cutscene.value.id
  if (!/^[A-Z0-9_]{1,40}$/.test(id)) return 'Use A-Z, 0-9 and _ (max 40).'
  return props.otherIds.includes(id) ? 'Another cut-scene uses this id.' : null
})

const audioOptions = computed<SelectOption[]>(() =>
  props.audioTracks.map((track) => ({ value: track.id, label: track.name || track.id })),
)

const audioTrack = computed<string | number | null>({
  get: () => cutscene.value.audio_track_id || '',
  set: (value) => {
    cutscene.value.audio_track_id = value ? String(value) : null
  },
})

function setId(value: string | number | null): void {
  cutscene.value.id = String(value ?? '').toUpperCase().replace(/[^A-Z0-9_]/g, '_')
}

function addSlide(): void {
  if (cutscene.value.slides.length < MAX_SLIDES) cutscene.value.slides.push(newSlide())
}

function moveSlide(index: number, delta: number): void {
  const slides = cutscene.value.slides
  const target = index + delta
  if (target < 0 || target >= slides.length) return
  const [slide] = slides.splice(index, 1)
  slides.splice(target, 0, slide)
}

function removeSlide(index: number): void {
  if (cutscene.value.slides.length > 1) cutscene.value.slides.splice(index, 1)
}

function updateImage(value: { image_url: string | null, image_prompt: string }): void {
  const slide = imageSlide.value
  if (!slide) return
  slide.image_url = value.image_url
  slide.image_prompt = value.image_prompt
}
</script>

<template>
  <div class="space-y-6">
    <div class="grid gap-4 md:grid-cols-2">
      <UiField label="Title" hint="Shown over the first slide; leave empty for none.">
        <UiInput v-model="cutscene.title" placeholder="e.g. The Crimson Debt" />
      </UiField>
      <UiField
        label="ID"
        :error="idError"
        info="Chapters name it as their start cut-scene; scripts play it with tw.cutscene.play(&quot;ID&quot;)."
      >
        <UiInput :model-value="cutscene.id" mono @update:model-value="setId" />
      </UiField>
      <UiField
        label="Image style"
        hint="Overrides the adventure's style for these slides, e.g. comic or watercolor."
      >
        <UiCombobox v-model="cutscene.image_style" :options="props.styleNames" placeholder="The adventure's style" />
      </UiField>
      <UiField label="Audio track" hint="Plays during the cut-scene instead of the scene audio.">
        <UiSelect v-model="audioTrack" :options="audioOptions" placeholder="No track (scene audio keeps playing)" />
      </UiField>
    </div>
    <p v-if="props.usedBy.length" class="wb-hint">Opens {{ props.usedBy.join(', ') }}.</p>

    <UiSection title="Slides" :description="`${cutscene.slides.length} of ${MAX_SLIDES}. Passages of a slide follow each other over its picture; players skip one by holding Space or the mouse button.`">
      <div class="space-y-4">
        <CutsceneSlideRow
          v-for="(slide, index) in cutscene.slides"
          :key="slide.id"
          v-model="cutscene.slides[index]"
          :index="index"
          :total="cutscene.slides.length"
          @image="imageSlideIndex = index"
          @move="moveSlide(index, $event)"
          @remove="removeSlide(index)"
        />
        <UiButton :icon="Plus" size="sm" :disabled="cutscene.slides.length >= MAX_SLIDES" @click="addSlide">Add slide</UiButton>
      </div>
    </UiSection>

    <div class="flex flex-wrap items-center justify-between gap-2 border-t border-wb-line pt-4">
      <UiButton variant="danger" :icon="Trash2" @click="$emit('delete')">Delete cut-scene</UiButton>
      <UiButton :icon="Play" @click="$emit('preview')">Preview</UiButton>
    </div>

    <CutsceneSlideImageModal
      v-model:open="imageOpen"
      :adventure-id="props.adventureId"
      :slide="imageSlide"
      :cutscene-title="cutscene.title"
      :image-style="cutscene.image_style || ''"
      @update="updateImage"
    />
  </div>
</template>
