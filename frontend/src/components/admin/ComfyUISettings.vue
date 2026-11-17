<script setup lang="ts">
import UiBadge from '@/components/ui/UiBadge.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

type Workflow = 'sd15' | 'sdxl'
const url = defineModel<string>('url', { default: 'http://127.0.0.1:8188' })
const timeout = defineModel<number>('timeout', { default: 600 })
const simpleWorkflow = defineModel<Workflow>('simpleWorkflow', { default: 'sdxl' })
const advancedWorkflow = defineModel<Workflow>('advancedWorkflow', { default: 'sdxl' })
defineProps<{ simple: boolean; advanced: boolean }>()

const WORKFLOWS = [
  { value: 'sd15', label: 'SD 1.5 – text to image' },
  { value: 'sdxl', label: 'SDXL – text to image' },
]
</script>

<template>
  <UiCard title="ComfyUI" description="Your own ComfyUI server; pick installed checkpoints in the model fields above.">
    <template #actions>
      <UiBadge tone="warn">Experimental</UiBadge>
    </template>
    <div class="space-y-4">
      <div class="grid gap-4 sm:grid-cols-2">
        <UiField label="ComfyUI server URL">
          <UiInput v-model="url" type="url" placeholder="http://127.0.0.1:8188" />
        </UiField>
        <UiField label="Generation timeout" hint="Seconds, 1–3600.">
          <UiInput v-model="timeout" type="number" min="1" max="3600" />
        </UiField>
        <UiField v-if="simple" label="Workflow for the standard model">
          <UiSelect v-model="simpleWorkflow" :options="WORKFLOWS" />
        </UiField>
        <UiField v-if="advanced" label="Workflow for the high-fidelity model">
          <UiSelect v-model="advancedWorkflow" :options="WORKFLOWS" />
        </UiField>
      </div>
      <p class="wb-hint">
        Built-in workflows use core nodes; each checkpoint must match the chosen model family. The backend connects to the
        URL, not your browser; private or LAN addresses need ALLOW_PRIVATE_NETWORK_MODELS=true. SD 1.5 usually uses a
        512 px edge, SDXL 1024 px (set under Local diffusion parameters). A timeout stops waiting and removes a queued job;
        it does not interrupt a running one.
      </p>
    </div>
  </UiCard>
</template>
