<script setup lang="ts">
/**
 * Picks the gateway scenes of one link to a built region: the scenes the new region connects
 * to first (spec 5.2a). Without picks the World-Builder gets the region's border scenes and
 * fast travel points.
 */
import { computed } from 'vue'
import { useEditor } from '@/composables/editor/editorContext'
import { useRegionBuilderContext } from '@/composables/regionBuilder/regionBuilderContext'
import { MAX_GATEWAY_SCENES, toggleGateway } from '@/composables/regionBuilder/regionBuilderForm'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiDisclosure from '@/components/ui/UiDisclosure.vue'

const props = defineProps<{ regionId: string; regionLabel: string }>()

const editor = useEditor()
const { form } = useRegionBuilderContext()

interface SceneRow {
  id: string
  label: string
}

const scenes = computed<SceneRow[]>(() =>
  ((editor.editorScenes || []) as { id: string; label?: string; name?: string; section_id?: string | null }[])
    .filter((s) => s.section_id === props.regionId)
    .map((s) => ({ id: s.id, label: s.label || s.name || s.id })),
)
const picked = computed(() => form.value?.gateways[props.regionId] || [])
const full = computed(() => picked.value.length >= MAX_GATEWAY_SCENES)
const summary = computed(() =>
  picked.value.length ? `Gateway scenes in ${props.regionLabel}: ${picked.value.length} picked` : `Gateway scenes in ${props.regionLabel}: automatic`,
)

function toggle(sceneId: string, on: boolean): void {
  if (form.value) toggleGateway(form.value, props.regionId, sceneId, on)
}
</script>

<template>
  <UiDisclosure :label="summary" hint="Pick where the new region's exits start; up to 8.">
    <p v-if="!scenes.length" class="wb-hint py-2">This region has no scenes yet.</p>
    <div v-else class="grid grid-cols-1 gap-2 py-2 sm:grid-cols-2">
      <UiCheckbox
        v-for="scene in scenes"
        :key="scene.id"
        :model-value="picked.includes(scene.id)"
        :label="scene.label"
        :disabled="full && !picked.includes(scene.id)"
        @update:model-value="toggle(scene.id, $event)"
      />
    </div>
  </UiDisclosure>
</template>
