<script setup lang="ts">
/** Sticky bottom bar of the page: validate-and-fix switch and the Generate button. */
import { computed } from 'vue'
import { Sparkles } from 'lucide-vue-next'
import { useCreateAdventureContext } from '@/composables/createAdventure/createAdventureContext'
import UiButton from '@/components/ui/UiButton.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const { form, isGenerating, isLoadingCatalogs, hasLlmConfig, create } = useCreateAdventureContext()

const label = computed(() => {
  if (isGenerating.value) return 'Starting…'
  return hasLlmConfig.value ? 'Generate adventure' : 'Language model required'
})
</script>

<template>
  <div
    class="sticky bottom-0 z-20 mt-6 flex flex-col gap-3 rounded-xl border border-wb-line-strong bg-wb-overlay px-4 py-3 shadow-wb-float sm:flex-row sm:items-center sm:justify-between"
    role="region"
    aria-label="Generate"
  >
    <UiToggle
      v-model="form.auto_validate_and_fix"
      label="Validate & fix afterwards"
      description="Checks the finished world and applies the first AI fix per finding. Takes a few minutes more."
    />
    <div class="flex flex-col items-stretch gap-1 sm:items-end">
      <UiButton
        variant="ai"
        :icon="Sparkles"
        :loading="isGenerating"
        :disabled="isGenerating || isLoadingCatalogs || !hasLlmConfig"
        @click="create"
      >
        {{ label }}
      </UiButton>
      <p class="wb-hint">The world is built in the background; this takes a few minutes.</p>
    </div>
  </div>
</template>
