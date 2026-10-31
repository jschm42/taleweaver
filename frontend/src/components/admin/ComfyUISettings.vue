<script setup lang="ts">
type Workflow = 'sd15' | 'sdxl'
const url = defineModel<string>('url', { default: 'http://127.0.0.1:8188' })
const timeout = defineModel<number>('timeout', { default: 600 })
const simpleWorkflow = defineModel<Workflow>('simpleWorkflow', { default: 'sdxl' })
const advancedWorkflow = defineModel<Workflow>('advancedWorkflow', { default: 'sdxl' })
defineProps<{ simple: boolean; advanced: boolean }>()
</script>

<template>
  <section class="space-y-4 rounded-3xl border border-amber-500/30 bg-slate-900 p-6">
    <h3 class="font-bold text-white">ComfyUI <span class="ml-2 text-xs text-amber-400">Experimental</span></h3>
    <p class="text-xs leading-relaxed text-slate-400">
      Use your own ComfyUI server. Choose installed checkpoints in the model pickers below.
      Built-in workflows use core nodes; each checkpoint must match the selected model family.
    </p>
    <div class="grid gap-4 sm:grid-cols-2">
      <label class="text-xs text-slate-300">ComfyUI server URL
        <input v-model="url" type="url" placeholder="http://127.0.0.1:8188"
          class="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-white" />
      </label>
      <label class="text-xs text-slate-300">Generation timeout (seconds)
        <input v-model.number="timeout" type="number" min="1" max="3600"
          class="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-white" />
      </label>
      <label v-if="simple" class="text-xs text-slate-300">Standard model workflow
        <select v-model="simpleWorkflow" class="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-white">
          <option value="sd15">SD 1.5 — text to image</option>
          <option value="sdxl">SDXL — text to image</option>
        </select>
      </label>
      <label v-if="advanced" class="text-xs text-slate-300">High-fidelity model workflow
        <select v-model="advancedWorkflow" class="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-white">
          <option value="sd15">SD 1.5 — text to image</option>
          <option value="sdxl">SDXL — text to image</option>
        </select>
      </label>
    </div>
    <p class="text-xs text-slate-400">
      The URL is reached from the TaleWeaver backend, not your browser. Private/LAN endpoints
      require ALLOW_PRIVATE_NETWORK_MODELS=true. SD 1.5 usually uses a 512 px edge;
      SDXL uses 1024 px. Set resolution and sampling under Local Diffusion Parameters.
      Timing out stops waiting and removes this job if still queued; it does not interrupt a running job.
    </p>
  </section>
</template>
