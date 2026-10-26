<script setup lang="ts">
import { NARRATION_STYLE_OPTIONS, type NarrationStyle } from './narrationStyles'

const style = defineModel<NarrationStyle>({ required: true })
</script>

<template>
  <section class="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
    <div class="space-y-1">
      <h4 class="text-xs font-black uppercase tracking-widest text-slate-100">Narration Style</h4>
      <p class="text-xs leading-relaxed text-slate-400">
        How much the narrator writes per turn, from quick snippets to novel-like chapters.
      </p>
    </div>

    <div role="radiogroup" aria-label="Narration style" class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
      <button
        v-for="option in NARRATION_STYLE_OPTIONS"
        :key="option.id"
        type="button"
        role="radio"
        :aria-checked="style === option.id"
        class="flex flex-col gap-2 rounded-xl border p-3 text-left transition-all cursor-pointer"
        :class="style === option.id ? 'border-amber-400/70 bg-amber-500/10' : 'border-white/10 bg-white/[0.03] hover:border-white/20'"
        @click="style = option.id"
      >
        <span class="flex h-12 flex-col gap-[3px] overflow-hidden rounded-md border border-white/10 bg-slate-950/60 p-1.5" aria-hidden="true">
          <span
            v-for="line in option.previewLines"
            :key="line"
            class="block h-[3px] shrink-0 rounded-full bg-slate-500/70"
            :style="{ width: line === option.previewLines ? '60%' : '100%' }"
          ></span>
        </span>
        <span class="text-xs font-black uppercase tracking-widest text-slate-100">{{ option.label }}</span>
        <span class="text-[10px] font-bold uppercase tracking-wider text-amber-300/90">{{ option.length }}</span>
        <span class="text-[11px] leading-snug text-slate-400">{{ option.description }}</span>
      </button>
    </div>

    <p class="mt-3 border-t border-white/5 pt-3 text-[11px] leading-relaxed text-slate-500">
      <span class="font-bold uppercase tracking-wider text-slate-400">How it works · </span>The style changes the
      narrator's length and pacing rules from your next action on. Longer styles take a little longer to generate
      and use more tokens; new scenes and big moments are always allowed a bit more room.
    </p>
  </section>
</template>
