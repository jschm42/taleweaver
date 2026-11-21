<script setup lang="ts">
/** Which images and voices are generated together with the world. */
import { useCreateAdventureContext } from '@/composables/createAdventure/createAdventureContext'
import UiCard from '@/components/ui/UiCard.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const { form, hasT2iConfig, isConfigLoaded } = useCreateAdventureContext()

const OPTIONS = [
  { key: 'automatic_cover_generation', label: 'Cover image', description: 'The title picture of the adventure.' },
  { key: 'generate_scene_images', label: 'Scene images', description: 'One picture per place.' },
  { key: 'generate_npc_images', label: 'Character portraits', description: 'Portraits of the characters.' },
  { key: 'generate_item_images', label: 'Item images', description: 'Pictures of items and containers.' },
  { key: 'automatic_npc_voice_assignment', label: 'Character voices', description: 'Picks a text-to-speech voice per character.' },
] as const
</script>

<template>
  <UiCard title="Images & voices" description="Turn off what you want to add by hand later; the world builds faster.">
    <div class="space-y-4">
      <UiNotice v-if="isConfigLoaded && !hasT2iConfig" tone="warn">
        No image model is set up, so no images are generated. Voices still are.
      </UiNotice>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <UiCheckbox
          v-for="option in OPTIONS"
          :key="option.key"
          v-model="form[option.key]"
          :label="option.label"
          :description="option.description"
        />
      </div>
    </div>
  </UiCard>
</template>
