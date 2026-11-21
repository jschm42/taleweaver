<script setup lang="ts">
/**
 * The world map images: a grid of 16:9 tiles. Choose a tile (or a "+" cell right of or below
 * the map to extend it), then draw it with the image model (editable prompt, optionally with the
 * adventure's image style and tone), upload an own image, download or remove it. Growing or
 * shrinking the grid keeps the regions over the same spot of the map.
 */
import { computed, ref, watch } from 'vue'
import { Download, Plus, Sparkles, Trash2, Upload } from 'lucide-vue-next'
import { useToast } from '@/composables/useToast'
import { sectionService } from '@/services/sectionService'
import type { MapLayout } from '@/types'
import { getImageUrl } from '@/utils/game_icons'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const MAX_GRID = 6

const open = defineModel<boolean>('open', { default: false })

const props = defineProps<{ adventureId: string; layout: MapLayout | null }>()

const emit = defineEmits<{ (e: 'changed'): void }>()

const toast = useToast()
const cell = ref<{ col: number; row: number }>({ col: 0, row: 0 })
const prompt = ref('')
const style = ref('')
const tone = ref('')
const useStyle = ref(true)
const useTone = ref(true)
const loading = ref(false)
const busy = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const cols = computed(() => props.layout?.cols || 1)
const rows = computed(() => props.layout?.rows || 1)
// Existing cells plus one extra column and row to grow into.
const gridCols = computed(() => Math.min(MAX_GRID, cols.value + 1))
const gridRows = computed(() => Math.min(MAX_GRID, rows.value + 1))
const tileAt = (col: number, row: number) => props.layout?.tiles.find((t) => t.col === col && t.row === row)
const current = computed(() => tileAt(cell.value.col, cell.value.row))
const isNewCell = computed(() => cell.value.col >= cols.value || cell.value.row >= rows.value)

async function loadPrompt(): Promise<void> {
  loading.value = true
  try {
    const info = await sectionService.getMapPrompt(props.adventureId, cell.value.col, cell.value.row)
    prompt.value = info.prompt
    style.value = info.style
    tone.value = info.tone
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Failed to load the map prompt.')
  } finally {
    loading.value = false
  }
}

watch(open, (isOpen) => {
  if (!isOpen) return
  cell.value = { col: 0, row: 0 }
  void loadPrompt()
})

function choose(col: number, row: number): void {
  cell.value = { col, row }
  void loadPrompt()
}

async function run(action: () => Promise<unknown>, failure: string): Promise<void> {
  busy.value = true
  try {
    await action()
    emit('changed')
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : failure)
  } finally {
    busy.value = false
  }
}

function draw(): Promise<void> {
  const { col, row } = cell.value
  return run(
    () => sectionService.generateMapTile(props.adventureId, { col, row, prompt: prompt.value, use_style: useStyle.value, use_tone: useTone.value }),
    'Failed to draw the map tile.',
  )
}

function upload(file: File | undefined): void {
  if (file) void run(() => sectionService.uploadMapTile(props.adventureId, cell.value.col, cell.value.row, file), 'Failed to upload the map tile.')
  if (fileInput.value) fileInput.value.value = ''
}

function remove(): Promise<void> {
  return run(() => sectionService.removeMapTile(props.adventureId, cell.value.col, cell.value.row), 'Failed to remove the map tile.')
}

function download(): void {
  const url = current.value?.url
  if (!url) return
  const link = document.createElement('a')
  link.href = getImageUrl(url) || url
  link.download = `world-map-${cell.value.col + 1}-${cell.value.row + 1}${url.slice(url.lastIndexOf('.'))}`
  link.click()
}

function short(text: string): string {
  return text.length > 140 ? `${text.slice(0, 140)}...` : text || 'none set'
}
</script>

<template>
  <UiModal v-model:open="open" title="World map images" description="Build a large map from up to 6 x 6 images: extend it to the right or downwards." size="xl" :persistent="busy">
    <div class="space-y-5">
      <div class="grid gap-1" :style="{ gridTemplateColumns: `repeat(${gridCols}, minmax(0, 1fr))` }">
        <template v-for="row in gridRows" :key="`r${row}`">
          <button
            v-for="col in gridCols"
            :key="`c${col}-${row}`"
            type="button"
            :aria-label="tileAt(col - 1, row - 1) ? `Tile ${col}, ${row}` : `Add a tile at ${col}, ${row}`"
            :class="[
              'relative aspect-[16/9] rounded-md border overflow-hidden flex items-center justify-center',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent',
              cell.col === col - 1 && cell.row === row - 1 ? 'border-wb-accent ring-2 ring-wb-accent' : 'border-wb-line',
              col > cols || row > rows ? 'border-dashed bg-wb-sunken' : 'bg-wb-raised',
            ]"
            @click="choose(col - 1, row - 1)"
          >
            <img v-if="tileAt(col - 1, row - 1)" :src="getImageUrl(tileAt(col - 1, row - 1)?.url) || ''" alt="" class="absolute inset-0 w-full h-full object-cover" />
            <Plus v-else class="w-5 h-5 text-wb-muted" aria-hidden="true" />
          </button>
        </template>
      </div>

      <div class="space-y-3 border-t border-wb-line pt-4">
        <p class="wb-subheading">
          Tile {{ cell.col + 1 }}, {{ cell.row + 1 }}{{ isNewCell ? ' (extends the map)' : current ? '' : ' (empty)' }}
        </p>
        <UiSpinner v-if="loading" label="Loading the prompt" />
        <template v-else>
          <UiField label="Prompt" hint="Names this tile's part of the map and its regions; edit it freely. Ask for no lettering.">
            <UiTextarea v-model="prompt" :rows="5" />
          </UiField>
          <UiCheckbox v-model="useStyle" label="Add the adventure's image style" :description="short(style)" />
          <UiCheckbox v-model="useTone" label="Add the adventure's tone" :description="short(tone)" />
        </template>
        <p class="wb-hint">Every tile is drawn on its own, so the edges between tiles may not match exactly.</p>
      </div>
    </div>
    <template #footer>
      <input ref="fileInput" type="file" class="hidden" accept="image/png,image/jpeg,image/webp" @change="upload(($event.target as HTMLInputElement).files?.[0])" />
      <UiButton v-if="current" variant="danger" :icon="Trash2" :disabled="busy" @click="remove">Remove</UiButton>
      <UiButton v-if="current" :icon="Download" @click="download">Download</UiButton>
      <UiButton :icon="Upload" :disabled="busy" @click="fileInput?.click()">Upload image</UiButton>
      <UiButton variant="ai" :icon="Sparkles" :loading="busy" :disabled="loading" @click="draw">{{ current ? 'Redraw' : 'Draw tile' }}</UiButton>
    </template>
  </UiModal>
</template>
