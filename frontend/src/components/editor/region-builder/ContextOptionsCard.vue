<script setup lang="ts">
/**
 * Card 3 of the Region Builder: which parts of the existing world go into the prompt. All on by
 * default; every option costs tokens. The gateway scenes are always sent (spec 5.2).
 */
import { computed } from 'vue'
import { useRegionBuilderContext } from '@/composables/regionBuilder/regionBuilderContext'
import { CONTEXT_OPTIONS, formatTokens, setAllContext } from '@/composables/regionBuilder/regionBuilderForm'
import ContextOptionRow from '@/components/editor/region-builder/ContextOptionRow.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const { form, blocks, previewError } = useRegionBuilderContext()

const gateway = computed(() => blocks.value.gateway || null)

function setAll(on: boolean): void {
  if (form.value) setAllContext(form.value, on)
}
</script>

<template>
  <UiCard v-if="form" title="World context" description="What the World-Builder knows about the rest of your world.">
    <template #actions>
      <UiButton size="sm" variant="ghost" @click="setAll(true)">All on</UiButton>
      <UiButton size="sm" variant="ghost" @click="setAll(false)">All off</UiButton>
    </template>
    <div class="space-y-3">
      <UiNotice tone="info">
        Every option adds context to the prompt. More context keeps the region consistent with the rest of the world,
        but costs more tokens and makes generation slower.
      </UiNotice>
      <UiNotice v-if="previewError" tone="warn">{{ previewError }}</UiNotice>
      <div class="divide-y divide-wb-line">
        <ContextOptionRow v-for="option in CONTEXT_OPTIONS" :key="option.key" :option="option" />
        <div class="flex flex-wrap items-center justify-between gap-3 py-3">
          <div class="min-w-0">
            <p class="wb-label text-wb-strong">Gateway scenes (always included)</p>
            <p class="wb-hint">Border scenes of the linked regions; the new region's exits start there.</p>
          </div>
          <UiBadge tone="info">{{ gateway ? formatTokens(gateway.tokens) : '…' }}</UiBadge>
        </div>
      </div>
    </div>
  </UiCard>
</template>
