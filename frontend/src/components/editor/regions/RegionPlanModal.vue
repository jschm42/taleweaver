<script setup lang="ts">
/**
 * "Plan regions": the World-Builder proposes planned regions from the adventure's plot. The
 * proposal is shown for review; "Use plan" puts it into the Regions page draft (saved with the
 * save bar), nothing is stored before.
 */
import { computed, ref, watch } from 'vue'
import { Sparkles } from 'lucide-vue-next'
import { useToast } from '@/composables/useToast'
import { sectionService, type RegionPlan } from '@/services/sectionService'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const open = defineModel<boolean>('open', { default: false })

const props = defineProps<{ adventureId: string; existingIds: string[] }>()

const emit = defineEmits<{ (e: 'apply', plan: RegionPlan): void }>()

const toast = useToast()
const count = ref<string | number | null>(3)
const direction = ref('')
const planning = ref(false)
const plan = ref<RegionPlan | null>(null)

watch(open, (isOpen) => {
  if (isOpen) plan.value = null
})

const newRegions = computed(() => (plan.value?.sections || []).filter((s) => !props.existingIds.includes(s.id)))

async function makePlan(): Promise<void> {
  planning.value = true
  try {
    const amount = Math.min(8, Math.max(1, Number(count.value) || 3))
    plan.value = await sectionService.planSections(props.adventureId, amount, direction.value)
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Failed to plan the regions.')
  } finally {
    planning.value = false
  }
}

function usePlan(): void {
  if (!plan.value) return
  emit('apply', plan.value)
  open.value = false
}
</script>

<template>
  <UiModal v-model:open="open" title="Plan regions" description="The World-Builder plans new regions from the adventure's plot." size="lg" :persistent="planning">
    <div class="space-y-4">
      <div class="grid gap-4 md:grid-cols-[8rem_1fr]">
        <UiField label="New regions">
          <UiInput v-model="count" type="number" />
        </UiField>
        <UiField label="Directions" hint="Optional, e.g. 'a desert, a sunken city, the final fortress in the north'.">
          <UiTextarea v-model="direction" :rows="2" />
        </UiField>
      </div>
      <div v-if="plan" class="space-y-2 border-t border-wb-line pt-4">
        <p class="wb-label">Proposed regions</p>
        <p v-for="region in newRegions" :key="region.id" class="wb-body">
          <span class="text-wb-strong">{{ region.label }}</span> · {{ region.description }}
        </p>
      </div>
    </div>
    <template #footer>
      <UiButton :disabled="planning" @click="open = false">Cancel</UiButton>
      <UiButton v-if="!plan" variant="ai" :icon="Sparkles" :loading="planning" @click="makePlan">Plan</UiButton>
      <template v-else>
        <UiButton variant="ai" :icon="Sparkles" :loading="planning" @click="makePlan">Plan again</UiButton>
        <UiButton variant="primary" @click="usePlan">Use plan</UiButton>
      </template>
    </template>
  </UiModal>
</template>
