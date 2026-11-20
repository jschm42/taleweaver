<script setup lang="ts">
import { computed, provide, useId } from 'vue'
import { FIELD_CONTEXT } from '@/components/ui/fieldContext'
import UiInfoPopover from '@/components/ui/UiInfoPopover.vue'

const props = withDefaults(
  defineProps<{
    label: string
    /** One sentence below the control. Longer help belongs in `info`. */
    hint?: string
    error?: string | null
    /** Help text shown in a popover next to the label. */
    info?: string
    required?: boolean
    /** Current length, shown as "count / maxLength" when maxLength is set. */
    count?: number
    maxLength?: number
    id?: string
  }>(),
  { hint: '', error: null, info: '', required: false, count: undefined, maxLength: undefined, id: undefined },
)

const fieldId = props.id ?? `field-${useId()}`
const hintId = `${fieldId}-hint`
const errorId = `${fieldId}-error`

const invalid = computed(() => Boolean(props.error))
const overLimit = computed(
  () => props.maxLength !== undefined && props.count !== undefined && props.count > props.maxLength,
)
const describedBy = computed(() => {
  const ids = [props.hint ? hintId : '', props.error ? errorId : ''].filter(Boolean)
  return ids.length ? ids.join(' ') : undefined
})

provide(FIELD_CONTEXT, {
  id: fieldId,
  describedBy,
  invalid,
  required: computed(() => props.required),
})
</script>

<template>
  <div class="space-y-1.5">
    <div class="flex items-center justify-between gap-2">
      <div class="flex items-center gap-1.5 min-w-0">
        <label :for="fieldId" class="wb-label truncate">
          {{ label }}<span v-if="required" class="text-wb-danger-text" aria-hidden="true"> *</span>
        </label>
        <UiInfoPopover v-if="info" :title="label" :text="info" />
      </div>
      <span
        v-if="maxLength !== undefined && count !== undefined"
        :class="['wb-hint tabular-nums', overLimit ? '!text-wb-danger-text' : '']"
      >
        {{ count }} / {{ maxLength }}
      </span>
    </div>
    <slot :id="fieldId" :described-by="describedBy" :invalid="invalid" />
    <p v-if="error" :id="errorId" class="wb-hint !text-wb-danger-text" role="alert">{{ error }}</p>
    <p v-else-if="hint" :id="hintId" class="wb-hint">{{ hint }}</p>
  </div>
</template>
