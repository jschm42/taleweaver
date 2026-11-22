<script setup lang="ts">
/**
 * Sticky bottom bar of the Region Builder: the prompt's estimated size (a warning above
 * LARGE_PROMPT_TOKENS), the prompt preview (advanced) and the Build button.
 */
import { computed } from 'vue'
import { Eye, Sparkles } from 'lucide-vue-next'
import { useRegionBuilderContext } from '@/composables/regionBuilder/regionBuilderContext'
import { LARGE_PROMPT_TOKENS, formatTokens } from '@/composables/regionBuilder/regionBuilderForm'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'

const emit = defineEmits<{ (e: 'show-prompt'): void }>()

const { form, preview, starting, canBuild, blockReason, build } = useRegionBuilderContext()

const total = computed(() => preview.value?.total_tokens ?? null)
const large = computed(() => (total.value ?? 0) > LARGE_PROMPT_TOKENS)
</script>

<template>
  <div
    class="sticky bottom-0 z-20 mt-6 flex flex-col gap-3 rounded-xl border border-wb-line-strong bg-wb-overlay px-4 py-3 shadow-wb-float sm:flex-row sm:items-center sm:justify-between"
    role="region"
    aria-label="Build region"
  >
    <div class="min-w-0 space-y-1">
      <div class="flex flex-wrap items-center gap-2">
        <span class="wb-label">Prompt size</span>
        <UiBadge :tone="large ? 'warn' : 'info'">{{ total === null ? '…' : formatTokens(total) }}</UiBadge>
        <UiButton v-if="form?.mode === 'advanced'" size="sm" variant="ghost" :icon="Eye" @click="emit('show-prompt')">
          Preview prompt
        </UiButton>
      </div>
      <p class="wb-hint">
        {{ large ? 'Large prompt: consider compact detail for scenes, characters and items.' : 'An estimate; system prompt included.' }}
      </p>
    </div>
    <div class="flex flex-col items-stretch gap-1 sm:items-end">
      <UiButton variant="ai" :icon="Sparkles" :loading="starting" :disabled="!canBuild" @click="build">Build region</UiButton>
      <p class="wb-hint">{{ blockReason || 'The region is built in the background; this takes a few minutes.' }}</p>
    </div>
  </div>
</template>
