<script setup lang="ts">
/**
 * Moves scenes into one region: checked scenes leave their current region. Every scene belongs
 * to a region, so a scene leaves this region only by moving it into another one. Runs
 * immediately, not through the save bar.
 */
import { computed, ref, watch } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import type { WorldSection } from '@/services/sectionService'

interface SceneOption {
  id: string
  label: string
  sectionId: string | null
}

const open = defineModel<boolean>('open', { default: false })

const props = defineProps<{
  section: WorldSection | null
  scenes: SceneOption[]
  sectionLabels: Record<string, string>
  saving: boolean
}>()

const emit = defineEmits<{
  (e: 'apply', added: string[]): void
}>()

const chosen = ref<Set<string>>(new Set())
const search = ref('')

watch(open, (isOpen) => {
  if (!isOpen || !props.section) return
  chosen.value = new Set()
  search.value = ''
})

const visible = computed(() => {
  const term = search.value.trim().toLowerCase()
  return props.scenes.filter(
    (s) => s.sectionId !== props.section?.id && (!term || s.label.toLowerCase().includes(term) || s.id.toLowerCase().includes(term)),
  )
})

function isChosen(id: string): boolean {
  return chosen.value.has(id)
}

function toggle(id: string, value: boolean): void {
  const next = new Set(chosen.value)
  if (value) next.add(id)
  else next.delete(id)
  chosen.value = next
}

function where(scene: SceneOption): string {
  if (!scene.sectionId) return scene.id
  return `${scene.id} · now in ${props.sectionLabels[scene.sectionId] || scene.sectionId}`
}

function apply(): void {
  if (!props.section || !chosen.value.size) return
  emit('apply', [...chosen.value])
}
</script>

<template>
  <UiModal
    v-model:open="open"
    :title="`Move scenes into ${section?.label || 'region'}`"
    description="Checked scenes move here from their current region. To take a scene out of this region, move it into another one."
    size="lg"
    :persistent="saving"
  >
    <div class="space-y-3">
      <UiInput v-model="search" type="search" placeholder="Filter scenes..." aria-label="Filter scenes" />
      <UiEmptyState v-if="!visible.length" title="No other scenes" description="Every scene already lies in this region, or none matches the filter." />
      <div v-else class="max-h-96 overflow-y-auto space-y-1 pr-1">
        <UiCheckbox
          v-for="scene in visible"
          :key="scene.id"
          :model-value="isChosen(scene.id)"
          :label="scene.label"
          :description="where(scene)"
          @update:model-value="toggle(scene.id, $event)"
        />
      </div>
    </div>
    <template #footer>
      <UiButton :disabled="saving" @click="open = false">Cancel</UiButton>
      <UiButton variant="primary" :loading="saving" :disabled="!chosen.size" @click="apply">Move {{ chosen.size || '' }} scene(s)</UiButton>
    </template>
  </UiModal>
</template>
