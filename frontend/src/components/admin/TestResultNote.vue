<script setup lang="ts">
import { CircleCheck, CircleX } from 'lucide-vue-next'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'
import { routeMissed, type CapabilityCheck, type RouteInfo, type SpeedRating } from '@/services/testService'

/** Result of a provider test run (`testService.testResults[...]`), with the capability checks if any. */
defineProps<{
  result?: { status: 'loading' | 'success' | 'error' | string; message?: string; checks?: CapabilityCheck[]; speed?: SpeedRating; routing?: RouteInfo } | null
}>()
</script>

<template>
  <div v-if="result" aria-live="polite">
    <p v-if="result.status === 'loading'" class="flex items-center gap-2 wb-body text-wb-muted">
      <UiSpinner size="sm" /> {{ result.message || 'Testing…' }}
    </p>
    <UiNotice v-else :tone="result.status === 'success' ? 'success' : 'danger'">
      {{ result.message }}
      <ul v-if="result.checks?.length" class="mt-2 space-y-1">
        <li v-for="check in result.checks" :key="check.id" class="flex items-start gap-2">
          <CircleCheck v-if="check.passed" class="mt-0.5 h-4 w-4 shrink-0 text-wb-accent-text" aria-label="Passed" />
          <CircleX v-else class="mt-0.5 h-4 w-4 shrink-0 text-wb-danger-text" aria-label="Failed" />
          <span>
            {{ check.label }}
            <span v-if="check.detail" class="wb-hint"> · {{ check.detail }}</span>
          </span>
        </li>
      </ul>
      <p v-if="result.speed" class="mt-2 wb-hint">{{ result.speed.note }}</p>
      <p v-if="result.routing?.note && !routeMissed(result.routing)" class="mt-1 wb-hint">{{ result.routing.note }}</p>
    </UiNotice>
    <UiNotice
      v-if="result.status !== 'loading' && routeMissed(result.routing)"
      tone="warn"
      title="OpenRouter provider not used"
      class="mt-2"
    >
      {{ result.routing?.note }}
    </UiNotice>
  </div>
</template>
