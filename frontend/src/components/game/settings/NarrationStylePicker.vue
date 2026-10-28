<script setup lang="ts">
import { computed } from 'vue'
import { NARRATION_STYLE_OPTIONS, type NarrationStyle } from './narrationStyles'

const style = defineModel<NarrationStyle>({ required: true })

const selected = computed(() => NARRATION_STYLE_OPTIONS.find((option) => option.id === style.value))
</script>

<template>
  <section class="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
    <div class="space-y-1">
      <label for="narration-style" class="block text-xs font-black uppercase tracking-widest text-slate-100">
        Narration Style
      </label>
      <p class="text-xs leading-relaxed text-slate-400">
        How much the narrator writes per turn, from quick snippets to novel-like chapters.
      </p>
    </div>

    <select
      id="narration-style"
      v-model="style"
      class="mt-3 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2.5 text-sm text-slate-100 focus:border-amber-400/70 focus:outline-none cursor-pointer"
    >
      <option v-for="option in NARRATION_STYLE_OPTIONS" :key="option.id" :value="option.id">
        {{ option.label }} · {{ option.length }}
      </option>
    </select>
    <p v-if="selected" class="mt-2 text-[11px] leading-snug text-slate-400">{{ selected.description }}</p>

    <p class="mt-3 border-t border-white/5 pt-3 text-[11px] leading-relaxed text-slate-500">
      <span class="font-bold uppercase tracking-wider text-slate-400">How it works · </span>The style changes the
      narrator's length and pacing rules from your next action on. Longer styles take a little longer to generate
      and use more tokens; new scenes and big moments are always allowed a bit more room.
    </p>
  </section>
</template>
