<script setup lang="ts">
/**
 * One category of a size section: optional on/off switch, "AI decides" and a min/max range.
 * min and max null mean the AI decides; a min above max pulls max along and vice versa.
 * `form` holds `min_<limit>`, `max_<limit>` and the switch; shared by the Generate adventure
 * page and the Region Builder.
 */
import { computed } from 'vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

type EnabledKey = 'quest_generation_enabled' | 'container_generation_enabled' | 'text_log_generation_enabled' | 'award_generation_enabled'

const props = defineProps<{
  /** The reactive form object the row reads and writes. */
  form: object
  label: string
  description: string
  limit: string
  bounds: [number, number]
  defaults: [number, number]
  enabledKey?: EnabledKey
}>()

const fields = computed(() => props.form as Record<string, unknown>)
const minKey = computed(() => `min_${props.limit}`)
const maxKey = computed(() => `max_${props.limit}`)
const minValue = computed(() => fields.value[minKey.value] as number | null)
const maxValue = computed(() => fields.value[maxKey.value] as number | null)
const enabled = computed(() => !props.enabledKey || Boolean(fields.value[props.enabledKey]))
const isAuto = computed(() => minValue.value === null && maxValue.value === null)

function write(key: string, value: unknown): void {
  fields.value[key] = value
}

function setAuto(auto: boolean): void {
  write(minKey.value, auto ? null : props.defaults[0])
  write(maxKey.value, auto ? null : props.defaults[1])
}

function clamp(value: unknown): number {
  const [low, high] = props.bounds
  const number = typeof value === 'number' && Number.isFinite(value) ? value : low
  return Math.min(high, Math.max(low, Math.round(number)))
}

function setMin(value: unknown): void {
  const next = clamp(value)
  write(minKey.value, next)
  if (maxValue.value !== null && next > maxValue.value) write(maxKey.value, next)
}

function setMax(value: unknown): void {
  const next = clamp(value)
  write(maxKey.value, next)
  if (minValue.value !== null && next < minValue.value) write(minKey.value, next)
}

function setEnabled(value: boolean): void {
  if (props.enabledKey) write(props.enabledKey, value)
}
</script>

<template>
  <div class="grid grid-cols-1 items-center gap-3 py-3 sm:grid-cols-[minmax(0,1fr)_auto_13rem]">
    <div class="flex min-w-0 items-start gap-3">
      <UiToggle
        v-if="enabledKey"
        :model-value="!!enabled"
        :label="`Generate ${label.toLowerCase()}`"
        hide-label
        @update:model-value="setEnabled"
      />
      <div class="min-w-0">
        <p class="wb-label !text-wb-strong">{{ label }}</p>
        <p class="wb-hint">{{ description }}</p>
      </div>
    </div>
    <UiCheckbox
      :model-value="isAuto"
      label="AI decides"
      :disabled="!enabled"
      @update:model-value="setAuto"
    />
    <div class="flex items-center gap-2 sm:justify-end" :class="{ invisible: isAuto || !enabled }">
      <UiInput
        type="number"
        size="sm"
        class="w-20"
        :model-value="minValue ?? defaults[0]"
        :min="bounds[0]"
        :max="bounds[1]"
        :aria-label="`Minimum ${label.toLowerCase()}`"
        :disabled="isAuto || !enabled"
        @update:model-value="setMin"
      />
      <span class="wb-hint" aria-hidden="true">to</span>
      <UiInput
        type="number"
        size="sm"
        class="w-20"
        :model-value="maxValue ?? defaults[1]"
        :min="bounds[0]"
        :max="bounds[1]"
        :aria-label="`Maximum ${label.toLowerCase()}`"
        :disabled="isAuto || !enabled"
        @update:model-value="setMax"
      />
    </div>
  </div>
</template>
