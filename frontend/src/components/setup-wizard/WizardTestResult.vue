<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheck, CircleX, Loader2 } from 'lucide-vue-next'
import { routeMissed, testService } from '@/services/testService'
import { wizardStyles } from './wizardPresets'

const props = defineProps<{ testKey: string }>()

const result = computed(() => testService.testResults.value[props.testKey])
</script>

<template>
  <div v-if="result" class="space-y-2">
    <p v-if="result.status === 'loading'" class="flex items-center gap-2 text-xs text-slate-400">
      <Loader2 class="w-4 h-4 animate-spin" /> {{ result.message }}
    </p>
    <p v-else :class="result.status === 'success' ? wizardStyles.success : wizardStyles.error">
      {{ result.message }}
    </p>
    <ul v-if="result.status !== 'loading' && result.checks?.length" class="space-y-1">
      <li v-for="check in result.checks" :key="check.id" class="flex items-start gap-2" :class="wizardStyles.hint">
        <CircleCheck v-if="check.passed" class="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" aria-label="Passed" />
        <CircleX v-else class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-label="Failed" />
        <span>{{ check.label }}<template v-if="check.detail"> · {{ check.detail }}</template></span>
      </li>
    </ul>
    <p v-if="result.status !== 'loading' && result.speed" :class="wizardStyles.hint">{{ result.speed.note }}</p>
    <p
      v-if="result.status !== 'loading' && result.routing?.note"
      :class="routeMissed(result.routing) ? 'text-xs font-bold text-amber-400' : wizardStyles.hint"
    >
      {{ result.routing.note }}
    </p>
    <img
      v-if="result.image_url"
      :src="result.image_url"
      alt="Test image"
      class="w-40 h-40 object-cover rounded-xl border border-white/10"
    />
  </div>
</template>
