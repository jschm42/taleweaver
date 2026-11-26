<script setup lang="ts">
// Editor toggle for WorldScene.is_fast_travel_point and its unlock mode: once unlocked, players
// can fast travel to the scene from anywhere (docs/specs/world_sections.md, 6.3).
import { ref, watch } from 'vue'
import { entityService, type EntityEditData } from '@/services/entityService'
import { useToast } from '@/composables/useToast'
import UiField from '@/components/ui/UiField.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

type UnlockMode = 'visit' | 'script'

const props = defineProps<{
  adventureId: string
  sceneId: string
  value?: boolean | null
  unlock?: string | null
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
}>()

const MODES: { value: UnlockMode; label: string }[] = [
  { value: 'visit', label: 'On first visit' },
  { value: 'script', label: 'By a script' },
]

const toast = useToast()
const enabled = ref(Boolean(props.value))
const mode = ref<UnlockMode>(props.unlock === 'script' ? 'script' : 'visit')

watch(() => [props.value, props.unlock], () => {
  enabled.value = Boolean(props.value)
  mode.value = props.unlock === 'script' ? 'script' : 'visit'
})

async function save(fields: Partial<EntityEditData>): Promise<void> {
  try {
    await entityService.saveEntityText(props.adventureId, { target_type: 'scene', target_id: props.sceneId, ...fields })
    emit('refresh')
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Failed to update the fast travel point.')
  }
}

function setEnabled(next: boolean): void {
  enabled.value = next
  void save({ is_fast_travel_point: next })
}

function setMode(next: UnlockMode): void {
  mode.value = next
  void save({ fast_travel_unlock: next })
}
</script>

<template>
  <div class="space-y-3">
    <UiToggle
      :model-value="enabled"
      label="Fast travel point"
      description="Once unlocked, the player can travel here from anywhere along the known route."
      @update:model-value="setEnabled"
    />
    <UiField
      v-if="enabled"
      label="Unlocked"
      info="By a script: call tw.game.unlock_fast_travel('SCENE_ID'), for example when the player activates a waystone."
    >
      <UiSegmented :model-value="mode" :options="MODES" label="How the point is unlocked" @update:model-value="setMode" />
    </UiField>
  </div>
</template>
