<script setup lang="ts">
/**
 * Building a planned region: opens the Region Builder, shows the running state and the reason
 * of a failed attempt. The generation runs in the background on the server; the Regions page
 * polls until the region is built or planned again.
 */
import { Sparkles } from 'lucide-vue-next'
import type { WorldSection } from '@/services/sectionService'
import UiButton from '@/components/ui/UiButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'

defineProps<{
  section: WorldSection
  /** Unsaved region changes: the server must know the region before it can build it. */
  dirty: boolean
}>()

const emit = defineEmits<{ (e: 'build'): void }>()
</script>

<template>
  <div class="space-y-3">
    <div v-if="section.status === 'generating'" class="flex items-center gap-2 wb-body text-wb-muted">
      <UiSpinner size="sm" label="Generating" />
      The World-Builder is building this region. This takes a few minutes.
    </div>
    <template v-else>
      <UiNotice v-if="section.generation_error" tone="danger" title="The last generation failed">
        {{ section.generation_error }}
      </UiNotice>
      <div class="flex flex-wrap items-center gap-3">
        <UiButton variant="ai" :icon="Sparkles" :disabled="dirty" @click="emit('build')">
          {{ section.generation_error ? 'Retry…' : 'Build region…' }}
        </UiButton>
        <span class="wb-hint">
          {{ dirty ? 'Save your changes first.' : 'Choose the size and which parts of your world the World-Builder reads.' }}
        </span>
      </div>
    </template>
  </div>
</template>
