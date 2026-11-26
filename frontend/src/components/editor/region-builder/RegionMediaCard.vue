<script setup lang="ts">
/**
 * Card of the Region Builder: images (in the adventure's image style) and voices for the new
 * region. Simple mode has one image switch; advanced mode one per kind (spec 4.2, 7.3).
 */
import { computed } from 'vue'
import { useRegionBuilderContext } from '@/composables/regionBuilder/regionBuilderContext'
import { imagesOn, setImages } from '@/composables/regionBuilder/regionBuilderForm'
import UiCard from '@/components/ui/UiCard.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const { form } = useRegionBuilderContext()

const images = computed({
  get: (): boolean => (form.value ? imagesOn(form.value) : false),
  set: (value: boolean) => {
    if (form.value) setImages(form.value, value)
  },
})
</script>

<template>
  <UiCard
    v-if="form"
    title="Images & voices"
    description="Pictures use the adventure's image style. Turn them off to add them by hand later; the region builds faster."
  >
    <div class="space-y-4">
      <UiToggle
        v-if="form.mode === 'simple'"
        v-model="images"
        label="Generate images"
        description="Scenes, characters and items of the new region."
      />
      <template v-else>
        <UiToggle v-model="form.options.generate_scene_images" label="Scene images" description="One picture per new scene." />
        <UiToggle v-model="form.options.generate_npc_images" label="Character portraits" description="A portrait per new character." />
        <UiToggle v-model="form.options.generate_item_images" label="Item images" description="A picture per new item." />
      </template>
      <UiToggle
        v-model="form.options.automatic_npc_voice_assignment"
        label="Assign voices"
        description="The World-Builder gives every new character a fitting voice from the voice list."
      />
    </div>
  </UiCard>
</template>
