<script setup lang="ts">
/**
 * "Discard region" for a region the Region Builder built: removes what it added and makes it a
 * planned region again, so it can be rebuilt. Confirms first (destructive).
 */
import { computed, ref } from 'vue'
import { Trash2 } from 'lucide-vue-next'
import { useConfirm } from '@/composables/useDialogs'
import { useToast } from '@/composables/useToast'
import { sectionService, type WorldSection } from '@/services/sectionService'
import UiButton from '@/components/ui/UiButton.vue'

const props = defineProps<{
  adventureId: string
  section: WorldSection
  /** Unsaved Regions page changes: discarding reloads the regions from the server. */
  dirty: boolean
}>()

const emit = defineEmits<{ (e: 'discarded'): void }>()

const confirm = useConfirm()
const toast = useToast()
const busy = ref(false)

const counts = computed(() => {
  const record = props.section.generated
  if (!record) return ''
  const parts = [
    [record.scene_ids.length, 'scene(s)'],
    [record.entity_ids.length, 'character(s) and item(s)'],
    [record.quest_ids.length + record.award_keys.length, 'quest(s) and award(s)'],
    [record.sequence_ids.length, 'chapter(s)'],
  ].filter(([count]) => Number(count) > 0)
  return parts.map(([count, label]) => `${count} ${label}`).join(', ')
})

async function discard(): Promise<void> {
  const ok = await confirm({
    title: `Discard ${props.section.label}?`,
    message:
      `This removes what the Region Builder added (${counts.value || 'its content'}), including later edits ` +
      'inside its scenes, and makes it a planned region again. Running sessions that already took it in keep their copy.',
    confirmLabel: 'Discard region',
    danger: true,
  })
  if (!ok) return
  busy.value = true
  try {
    await sectionService.discardSection(props.adventureId, props.section.id)
    toast.success(`${props.section.label} is a planned region again.`)
    emit('discarded')
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Failed to discard the region.')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="flex flex-wrap items-center gap-3 border-t border-wb-line pt-4">
    <UiButton variant="danger" :icon="Trash2" :loading="busy" :disabled="dirty" @click="discard">Discard region…</UiButton>
    <span class="wb-hint">{{ dirty ? 'Save your changes first.' : 'Built by the Region Builder; it can be taken out and rebuilt.' }}</span>
  </div>
</template>
