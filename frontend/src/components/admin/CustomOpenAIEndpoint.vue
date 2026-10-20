<script setup lang="ts">
defineProps<{
  url: string
  timeout: number
  responseFormat?: string
  loading: boolean
  modelCount: number
  hasKey: boolean
}>()
const emit = defineEmits<{
  (e: 'update:url', value: string): void
  (e: 'update:timeout', value: number): void
  (e: 'update:responseFormat', value: string): void
  (e: 'detect'): void
  (e: 'vault'): void
}>()
</script>

<template>
  <div class="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3">
    <h4 class="text-sm font-bold text-white">OpenAI-Compatible API</h4>
    <label class="block text-xs text-slate-300">
      Base URL
      <input
        :value="url"
        type="url"
        placeholder="https://your-provider.example/v1"
        class="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white"
        @input="emit('update:url', ($event.target as HTMLInputElement).value)"
      />
    </label>
    <label class="block text-xs text-slate-300">
      Request timeout (seconds)
      <input
        :value="timeout"
        type="number"
        min="1"
        max="3600"
        class="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white"
        @input="emit('update:timeout', Number(($event.target as HTMLInputElement).value))"
      />
    </label>
    <label class="block text-xs text-slate-300">
      Structured output support
      <select :value="responseFormat || 'prompt'" class="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white" @change="emit('update:responseFormat', ($event.target as HTMLSelectElement).value)">
        <option value="prompt">Prompt only (widest compatibility)</option>
        <option value="json_object">JSON object (server must support it)</option>
        <option value="json_schema">JSON schema (server must support it)</option>
      </select>
    </label>
    <button type="button" class="text-xs text-cyan-300" @click="emit('vault')">
      {{ hasKey ? 'Manage encrypted API key' : 'Add optional API key in Provider Vault' }}
    </button>
    <div class="flex items-center justify-between text-xs text-slate-400">
      <button type="button" :disabled="loading || !url" class="text-cyan-300 disabled:opacity-40" @click="emit('detect')">
        {{ loading ? 'Detecting…' : 'Detect Models' }}
      </button>
      <span>{{ modelCount }} models</span>
    </div>
    <p class="text-xs text-slate-400">
      Use a hosted gateway or self-hosted server with an OpenAI-compatible Chat Completions API.
      Save endpoint settings before Test Model. Select this provider for any pass and choose a detected model or Custom Model ID.
      Detection is optional. Local servers require ALLOW_PRIVATE_NETWORK_MODELS=true.
      In Docker, use host.docker.internal where available to reach a server on the host.
    </p>
  </div>
</template>
