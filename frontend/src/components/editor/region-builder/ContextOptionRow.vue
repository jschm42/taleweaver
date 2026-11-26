<script setup lang="ts">
/**
 * One option of the World context card: on/off, the detail level (advanced) and what it adds to
 * the prompt. An option that is off still shows its cost, measured at its default detail.
 */
import { computed } from 'vue'
import { useRegionBuilderContext } from '@/composables/regionBuilder/regionBuilderContext'
import {
  formatTokens,
  isContextOn,
  setContextOn,
  type ContextOptionInfo,
} from '@/composables/regionBuilder/regionBuilderForm'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const props = defineProps<{ option: ContextOptionInfo }>()

const { form, blocks } = useRegionBuilderContext()

const DETAIL_OPTIONS = [
  { value: 'compact', label: 'Compact' },
  { value: 'full', label: 'Full' },
]

const block = computed(() => blocks.value[props.option.key] || null)
const on = computed(() => (form.value ? isContextOn(form.value, props.option.key) : false))
const empty = computed(() => block.value?.empty === true)
const cost = computed(() => {
  if (!block.value) return '…'
  return empty.value ? 'nothing yet' : formatTokens(block.value.tokens)
})
const showWalkthroughs = computed(
  () => props.option.key === 'sequences' && form.value?.mode === 'advanced' && form.value.context.sequences === 'full',
)

function toggle(value: boolean): void {
  if (form.value) setContextOn(form.value, props.option.key, value)
}

function setDetail(value: unknown): void {
  if (!form.value || (value !== 'compact' && value !== 'full')) return
  form.value.context[props.option.key] = value
}
</script>

<template>
  <div v-if="form" class="grid grid-cols-1 items-center gap-3 py-3 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
    <div class="flex min-w-0 items-start gap-3">
      <UiToggle :model-value="on && !empty" :label="option.label" hide-label :disabled="empty" @update:model-value="toggle" />
      <div class="min-w-0">
        <p class="wb-label text-wb-strong">{{ option.label }}</p>
        <p class="wb-hint">{{ option.description }}</p>
        <UiToggle
          v-if="showWalkthroughs"
          v-model="form.context.walkthroughs"
          class="mt-2"
          label="Include walkthroughs"
          description="The solution steps of each chapter, up to 600 characters each."
        />
      </div>
    </div>
    <UiSelect
      v-if="form.mode === 'advanced' && option.hasDetail && !empty"
      size="sm"
      class="w-32"
      :model-value="on ? form.context[option.key] : 'compact'"
      :options="DETAIL_OPTIONS"
      :disabled="!on"
      :aria-label="`Detail of ${option.label.toLowerCase()}`"
      @update:model-value="setDetail"
    />
    <span v-else class="hidden sm:block" aria-hidden="true" />
    <UiBadge :tone="on && !empty ? 'info' : 'neutral'" class="justify-self-start sm:justify-self-end">{{ cost }}</UiBadge>
  </div>
</template>
