<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const ef = useEntityFormContext()
</script>

<template>
  <UiSection v-if="ef.type === 'npc'" title="Movement" class="border-t border-wb-line pt-6">
    <UiToggle
      v-model="ef.localForm.moveable"
      label="Can move between scenes"
      description="The Game Master decides when the character moves."
    />

    <div v-if="ef.localForm.moveable" class="space-y-2">
      <div class="flex items-center justify-between gap-3">
        <p class="wb-label">Allowed scenes</p>
        <UiBadge>
          {{ (ef.localForm.allowed_scenes_input || []).length === 0 ? 'All scenes' : `${(ef.localForm.allowed_scenes_input || []).length} selected` }}
        </UiBadge>
      </div>
      <p class="wb-hint">With none selected, the character may go anywhere.</p>
      <div
        v-if="ef.sceneReferenceOptions.length"
        class="grid max-h-48 grid-cols-1 gap-2 overflow-y-auto rounded-md border border-wb-line p-2 sm:grid-cols-2"
      >
        <UiCheckbox
          v-for="s in ef.sceneReferenceOptions"
          :key="s.id"
          :model-value="ef.isSceneAllowed(s.id)"
          :label="s.name || s.id"
          :description="s.id"
          @update:model-value="ef.toggleAllowedScene(s.id)"
        />
      </div>
      <p v-else class="wb-hint">This adventure has no scenes yet.</p>
    </div>
  </UiSection>
</template>
