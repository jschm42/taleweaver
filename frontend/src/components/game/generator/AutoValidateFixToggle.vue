<script setup lang="ts">
const enabled = defineModel<boolean>({ default: true })
</script>

<template>
  <label
    class="flex w-full max-w-xl cursor-pointer items-start gap-3 rounded-xl border p-3 transition-all"
    :class="enabled ? 'border-aether-primary/30 bg-aether-primary/5' : 'border-white/10 bg-black/20 hover:border-white/20'"
  >
    <input v-model="enabled" type="checkbox" class="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-aether-primary" />
    <span class="flex flex-col gap-0.5 text-left">
      <span class="text-xs font-bold text-slate-200">Validate &amp; auto-fix after generation</span>
      <span class="text-[11px] leading-snug text-slate-400">
        Runs a full validation once the world is built and applies the first AI fix proposal to each finding.
        Adds a few minutes and extra LLM calls. Remaining findings show up in the editor's Validation tab.
      </span>
    </span>
  </label>
</template>
