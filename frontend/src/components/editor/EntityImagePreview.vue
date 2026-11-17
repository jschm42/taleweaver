<script setup lang="ts">
import { ref, watch } from 'vue'
import { Maximize2 } from 'lucide-vue-next'
import EditorImageLightbox from '@/components/editor/EditorImageLightbox.vue'

const props = defineProps<{
  imageUrl: string | null
  label?: string
}>()

const enlargedUrl = ref<string | null>(null)

watch(() => props.imageUrl, () => {
  enlargedUrl.value = null
})

function openLightbox() {
  if (!props.imageUrl) return
  enlargedUrl.value = props.imageUrl
}
</script>

<template>
  <button
    v-if="imageUrl"
    type="button"
    class="group relative h-14 w-14 shrink-0 overflow-hidden rounded-xl border border-wb-line bg-wb-raised transition-colors hover:border-wb-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
    :aria-label="`View ${label || 'image'} in full size`"
    @click="openLightbox"
  >
    <img :src="imageUrl" :alt="label || 'Entity image'" class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105" />
    <span class="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity">
      <Maximize2 class="h-4 w-4 text-wb-strong" />
    </span>
  </button>

  <EditorImageLightbox :image-url="enlargedUrl" @close="enlargedUrl = null" />
</template>
