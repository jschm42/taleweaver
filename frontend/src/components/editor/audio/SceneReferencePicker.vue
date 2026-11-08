<script setup lang="ts">
/**
 * SceneReferencePicker — dropdown of the adventure's scenes with their image thumbnails.
 * The empty value stands for "whole adventure" (prompt from the premise instead of a scene).
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ChevronDown, Globe2 } from 'lucide-vue-next'
import { getImageUrl } from '@/utils/game_icons'

export interface ReferenceScene {
  id: string
  label?: string
  name?: string
  image_url?: string | null
}

const model = defineModel<string>({ required: true })
const props = defineProps<{ scenes: ReferenceScene[] }>()

const open = ref(false)
const root = ref<HTMLElement | null>(null)
const failedThumbs = ref(new Set<string>())

const selected = computed((): ReferenceScene | undefined => props.scenes.find((s) => s.id === model.value))

function label(scene: ReferenceScene): string {
  return scene.label || scene.name || scene.id
}

/** Thumbnail first; if it is missing, the full image. */
function imageFor(scene: ReferenceScene): string {
  if (!scene.image_url) return ''
  return getImageUrl(scene.image_url, { thumbnail: !failedThumbs.value.has(scene.id) })
}

function onImageError(scene: ReferenceScene): void {
  if (failedThumbs.value.has(scene.id)) return
  failedThumbs.value = new Set([...failedThumbs.value, scene.id])
}

function choose(id: string): void {
  model.value = id
  open.value = false
}

function onDocumentClick(event: MouseEvent): void {
  if (root.value && !root.value.contains(event.target as Node)) open.value = false
}

onMounted(() => document.addEventListener('mousedown', onDocumentClick))
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocumentClick))
</script>

<template>
  <div ref="root" class="relative">
    <button
      type="button"
      class="w-full flex items-center gap-2.5 bg-slate-950/80 border border-white/10 rounded-xl px-2.5 py-1.5 text-xs text-slate-200 hover:border-orange-500/40 focus:outline-none focus:border-orange-500/50"
      :aria-expanded="open"
      aria-haspopup="listbox"
      title="The AI prompt is written from this scene and the adventure's tone"
      @click="open = !open"
      @keydown.escape="open = false"
    >
      <template v-if="selected">
        <span class="w-10 h-7 shrink-0 rounded-md overflow-hidden bg-slate-800">
          <img v-if="imageFor(selected)" :src="imageFor(selected)" alt="" class="w-full h-full object-cover" @error="onImageError(selected)" />
        </span>
        <span class="truncate">{{ label(selected) }}</span>
      </template>
      <template v-else>
        <span class="w-10 h-7 shrink-0 rounded-md bg-slate-800 flex items-center justify-center"><Globe2 class="w-3.5 h-3.5 text-slate-400" /></span>
        <span class="truncate text-slate-300">Whole adventure (premise)</span>
      </template>
      <ChevronDown class="w-3.5 h-3.5 ml-auto shrink-0 text-slate-500" />
    </button>

    <ul
      v-if="open"
      role="listbox"
      class="absolute z-50 mt-1 w-full max-h-72 overflow-y-auto bg-slate-900 border border-white/15 rounded-xl shadow-2xl py-1"
    >
      <li>
        <button type="button" role="option" :aria-selected="!model"
          class="w-full flex items-center gap-2.5 px-2.5 py-1.5 text-left text-xs hover:bg-orange-500/15"
          :class="!model ? 'text-orange-300' : 'text-slate-200'" @click="choose('')">
          <span class="w-10 h-7 shrink-0 rounded-md bg-slate-800 flex items-center justify-center"><Globe2 class="w-3.5 h-3.5 text-slate-400" /></span>
          Whole adventure (premise)
        </button>
      </li>
      <li v-for="scene in scenes" :key="scene.id">
        <button type="button" role="option" :aria-selected="model === scene.id"
          class="w-full flex items-center gap-2.5 px-2.5 py-1.5 text-left text-xs hover:bg-orange-500/15"
          :class="model === scene.id ? 'text-orange-300' : 'text-slate-200'" @click="choose(scene.id)">
          <span class="w-10 h-7 shrink-0 rounded-md overflow-hidden bg-slate-800">
            <img v-if="imageFor(scene)" :src="imageFor(scene)" alt="" loading="lazy" class="w-full h-full object-cover" @error="onImageError(scene)" />
          </span>
          <span class="truncate">{{ label(scene) }}</span>
          <span class="ml-auto pl-2 font-mono text-[10px] text-slate-600 shrink-0">{{ scene.id }}</span>
        </button>
      </li>
    </ul>
  </div>
</template>
