<script setup lang="ts">
/**
 * Region Builder: build one planned region with the World-Builder. Simple mode shows the region,
 * its idea, the world context and a size preset; advanced mode adds every count, strictness,
 * detail levels and the prompt preview. Route: /adventures/:id/editor/regions/:sectionId/build.
 * Spec: docs/specs/region_builder.md.
 */
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, Globe2 } from 'lucide-vue-next'
import { provideRegionBuilder } from '@/composables/regionBuilder/regionBuilderContext'
import { useRegionBuilder } from '@/composables/regionBuilder/useRegionBuilder'
import type { RegionMode } from '@/composables/regionBuilder/regionBuilderForm'
import ContextOptionsCard from '@/components/editor/region-builder/ContextOptionsCard.vue'
import InheritedSettingsCard from '@/components/editor/region-builder/InheritedSettingsCard.vue'
import PromptPreviewModal from '@/components/editor/region-builder/PromptPreviewModal.vue'
import RegionBuildBar from '@/components/editor/region-builder/RegionBuildBar.vue'
import RegionIdeaCard from '@/components/editor/region-builder/RegionIdeaCard.vue'
import RegionInfoCard from '@/components/editor/region-builder/RegionInfoCard.vue'
import RegionSizeCard from '@/components/editor/region-builder/RegionSizeCard.vue'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'

const route = useRoute()
const sectionId = computed(() => String(route.params.sectionId || ''))
const state = useRegionBuilder(sectionId)
provideRegionBuilder(state)
const { form, section, setMode, backToRegions } = state

const MODES: { value: RegionMode; label: string }[] = [
  { value: 'simple', label: 'Simple' },
  { value: 'advanced', label: 'Advanced' },
]

const promptOpen = ref(false)
const mode = computed({
  get: (): RegionMode => form.value?.mode || 'simple',
  set: (value: RegionMode) => setMode(value),
})
</script>

<template>
  <div class="space-y-6">
    <PageHeader
      :title="section ? `Build ${section.label}` : 'Build region'"
      description="The World-Builder adds this region to your world: scenes, characters, items and exits to its neighbours."
    >
      <template #actions>
        <UiSegmented v-if="form" v-model="mode" :options="MODES" label="Settings shown" />
        <UiButton variant="ghost" :icon="ArrowLeft" @click="backToRegions">Regions</UiButton>
      </template>
    </PageHeader>

    <UiEmptyState
      v-if="!section"
      :icon="Globe2"
      title="Region not found"
      description="It may have been deleted or renamed. Open the Regions page to pick a planned region."
    />

    <template v-else-if="form">
      <UiNotice v-if="section.status === 'built'" tone="info" title="Already built">
        This region has scenes already. The Region Builder only builds planned regions.
      </UiNotice>
      <UiNotice v-else-if="section.status === 'generating'" tone="info" title="Building">
        The World-Builder is building this region. The Regions page shows when it is done.
      </UiNotice>
      <UiNotice v-else-if="section.generation_error" tone="danger" title="The last build failed">
        {{ section.generation_error }}
      </UiNotice>

      <RegionInfoCard />
      <RegionIdeaCard />
      <ContextOptionsCard />
      <RegionSizeCard />
      <InheritedSettingsCard />
      <RegionBuildBar @show-prompt="promptOpen = true" />
      <PromptPreviewModal v-model:open="promptOpen" />
    </template>
  </div>
</template>
