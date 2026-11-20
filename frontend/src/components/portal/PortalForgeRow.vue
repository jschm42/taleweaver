<script setup lang="ts">
import ForgeTile from './ForgeTile.vue'
import quillIcon from '@/assets/svg/quill-feather-pen-with-ink-bottle.svg'
import mapIcon from '@/assets/svg/fantasy-rpg-map.svg'

defineProps<{
  isSeeding: boolean
}>()

defineEmits<{
  (e: 'create'): void
  (e: 'generate-world'): void
  (e: 'open-library'): void
}>()
</script>

<template>
  <section class="space-y-3" aria-label="Create or find adventures">
    <h2 class="shelf-heading text-xs sm:text-sm uppercase">The Forge</h2>
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-3">
      <ForgeTile
        class="tale-enter"
        style="--i: 0"
        title="Start new"
        subtitle="Write your legend from a blank page."
        accent-rgb="251 191 36"
        :image-src="quillIcon"
        @activate="$emit('create')"
      />
      <ForgeTile
        class="tale-enter"
        style="--i: 1"
        title="Generate adventure"
        subtitle="Let the AI weave a sandbox world for you."
        accent-rgb="192 132 252"
        :image-src="mapIcon"
        @activate="$emit('generate-world')"
      />
      <ForgeTile
        class="tale-enter"
        style="--i: 2"
        :title="isSeeding ? 'Importing tales...' : 'Discover'"
        subtitle="Install published adventures from the catalog."
        accent-rgb="96 165 250"
        icon="ra-book"
        :disabled="isSeeding"
        @activate="$emit('open-library')"
      />
    </div>
  </section>
</template>
