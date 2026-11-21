<script setup lang="ts">
/** Image style and narrative tone of a new adventure. */
import { Feather, Palette } from 'lucide-vue-next'
import { useCreateAdventureContext } from '@/composables/createAdventure/createAdventureContext'
import CatalogPicker from '@/components/create-adventure/CatalogPicker.vue'
import UiCard from '@/components/ui/UiCard.vue'

const { form, imageStyles, tones, isLoadingCatalogs } = useCreateAdventureContext()

const STYLE_HELP =
  'The look of every generated image. One style keeps scenes, characters and items consistent.'
const TONE_HELP = 'Mood, pacing and wording of the story. Pick the tone that matches the experience you want.'
</script>

<template>
  <UiCard title="Look & tone" description="Admins manage both catalogs in Admin → Image styles and Tones.">
    <div class="grid grid-cols-1 gap-6 md:grid-cols-2">
      <CatalogPicker
        v-model="form.selected_style_id"
        title="Image style"
        :help="STYLE_HELP"
        :items="imageStyles"
        :icon="Palette"
        :loading="isLoadingCatalogs"
      />
      <CatalogPicker
        v-model="form.selected_tone_id"
        title="Tone"
        :help="TONE_HELP"
        :items="tones"
        :icon="Feather"
        :loading="isLoadingCatalogs"
      />
    </div>
  </UiCard>
</template>
