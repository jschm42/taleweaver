<script setup lang="ts">
defineProps<{
  passTitle?: string
  url: string
  fallbackUrl?: string
  timeout?: number
  responseFormat?: string
  showResponseFormat?: boolean
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
  <div class="p-4 bg-slate-950/80 border border-purple-500/30 rounded-2xl space-y-3 animate-fade-in">
    <!-- Header with title & Detect Models -->
    <div class="flex items-center justify-between">
      <h4 class="text-xs font-bold text-purple-300 flex items-center gap-2">
        <i class="ra ra-reactor text-purple-400"></i>
        <span>OpenAI-Compatible Endpoint{{ passTitle ? ` (${passTitle})` : '' }}</span>
      </h4>
      <div class="flex items-center gap-2">
        <span v-if="modelCount > 0" class="text-[11px] text-purple-400 font-mono hidden sm:inline">
          {{ modelCount }} detected
        </span>
        <button
          type="button"
          :disabled="loading || !(url || fallbackUrl)"
          class="px-2.5 py-1 bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 text-[11px] font-bold rounded-lg border border-purple-500/30 transition-all flex items-center gap-1.5 disabled:opacity-40"
          @click="emit('detect')"
        >
          <i class="ra ra-recycle" :class="{ 'animate-spin': loading }"></i>
          <span>{{ loading ? 'Detecting…' : 'Detect Models' }}</span>
        </button>
      </div>
    </div>

    <!-- Base URL Input -->
    <div>
      <label class="block text-xs text-slate-300">
        Base URL
        <input
          :value="url"
          type="url"
          :placeholder="fallbackUrl || 'https://your-provider.example/v1'"
          class="mt-1 w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white font-mono outline-none focus:ring-2 focus:ring-purple-500/50"
          @input="emit('update:url', ($event.target as HTMLInputElement).value)"
        />
      </label>
      <p v-if="!url && fallbackUrl" class="text-[11px] text-purple-400/80 font-mono mt-1">
        Using global fallback: {{ fallbackUrl }}
      </p>
    </div>

    <!-- Structured Output Support & Timeout Grid -->
    <div :class="['grid gap-3', showResponseFormat ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1']">
      <label v-if="showResponseFormat" class="block text-xs text-slate-300">
        Structured output support
        <select
          :value="responseFormat || 'prompt'"
          class="mt-1 w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white outline-none focus:ring-2 focus:ring-purple-500/50"
          @change="emit('update:responseFormat', ($event.target as HTMLSelectElement).value)"
        >
          <option value="prompt">Prompt only (widest compatibility)</option>
          <option value="json_object">JSON object (server must support it)</option>
          <option value="json_schema">JSON schema (server must support it)</option>
        </select>
      </label>

      <label class="block text-xs text-slate-300">
        Request timeout (seconds)
        <input
          :value="timeout ?? 300"
          type="number"
          min="1"
          max="3600"
          placeholder="300"
          class="mt-1 w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white font-mono outline-none focus:ring-2 focus:ring-purple-500/50"
          @input="emit('update:timeout', Number(($event.target as HTMLInputElement).value) || 300)"
        />
      </label>
    </div>

    <!-- Footer with Vault Key Link & Mobile Model Count -->
    <div class="flex items-center justify-between text-xs pt-1 border-t border-slate-800/60">
      <button
        type="button"
        class="text-[11px] text-purple-300 hover:underline flex items-center gap-1"
        @click="emit('vault')"
      >
        <i class="ra ra-key"></i>
        <span>{{ hasKey ? 'Manage encrypted API key in Vault' : 'Add optional API key in Provider Vault' }}</span>
      </button>
      <span v-if="modelCount > 0" class="text-[11px] text-slate-500 font-mono sm:hidden">
        {{ modelCount }} models
      </span>
    </div>
  </div>
</template>
