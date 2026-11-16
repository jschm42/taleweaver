<script setup lang="ts">
// Editor toggle for WorldScene.is_respawn_point: in respawn mode a protagonist who falls to 0 HP
// wakes up at the last revival point reached (else at the start scene).
import { ref, watch } from 'vue'
import { entityService } from '@/services/entityService'
import { notificationService } from '@/services/notificationService'

const props = defineProps<{
  adventureId: string
  sceneId: string
  value?: boolean | null
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
}>()

const checked = ref(!!props.value)
const isSaving = ref(false)

watch(() => props.value, (value) => {
  checked.value = !!value
})

async function toggle(): Promise<void> {
  const next = !checked.value
  isSaving.value = true
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: 'scene',
      target_id: props.sceneId,
      is_respawn_point: next,
    })
    checked.value = next
    emit('refresh')
  } catch (error: unknown) {
    notificationService.add(error instanceof Error ? error.message : 'Failed to update the revival point.', 'error')
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <label class="flex items-start gap-2 p-3 rounded-xl bg-black/40 border border-white/5 text-xs text-slate-300 cursor-pointer">
    <input :checked="checked" :disabled="isSaving" type="checkbox" class="mt-0.5 accent-indigo-500" @change="toggle" />
    <span>
      Revival point
      <span class="block text-[11px] text-slate-500">
        When the adventure respawns at 0 HP (Plot → Loss Conditions), the protagonist wakes up at the last revival point reached.
      </span>
    </span>
  </label>
</template>
