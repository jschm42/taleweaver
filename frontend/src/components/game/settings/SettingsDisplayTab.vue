<script setup lang="ts">
import { computed } from 'vue'
import { SKINS, findSkin, type SkinId, type SkinPreference } from '@/skins/skinRegistry'
import { TEXT_DENSITY_OPTIONS, type TextDensity } from '@/skins/useTextDensity'
import { TEXT_SCALES } from '@/skins/useTextScale'

const skin = defineModel<SkinPreference>('skin', { required: true })
const density = defineModel<TextDensity>('density', { required: true })
const textScale = defineModel<number>('textScale', { required: true })

/** Preview line heights / gaps (px) to illustrate each density in the picker. */
const DENSITY_PREVIEW: Record<TextDensity, { bar: number; gap: number }> = {
  compact: { bar: 3, gap: 2 },
  comfortable: { bar: 4, gap: 4 },
  spacious: { bar: 5, gap: 7 },
}

const props = defineProps<{
  /** Skin that "Auto" resolves to for this adventure. */
  autoSkin: SkinId
  /** Why Auto picked it, e.g. "chosen by the adventure author" or "matches the tone Mystery". */
  autoReason: string
}>()

const autoDefinition = computed(() => findSkin(props.autoSkin))
</script>

<template>
  <div class="flex flex-col gap-4">
    <p class="text-xs leading-relaxed text-slate-400">
      Choose how narration, dialogue and the story tabs look. Each skin changes colors, fonts and shapes but
      keeps the layout identical, so nothing moves around.
    </p>

    <div role="radiogroup" aria-label="Dialog skin" class="flex flex-col gap-2">
      <button
        type="button"
        role="radio"
        :aria-checked="skin === 'auto'"
        class="flex items-center gap-3 rounded-2xl border p-3 text-left transition-all cursor-pointer"
        :class="skin === 'auto' ? 'border-amber-400/70 bg-amber-500/10' : 'border-white/10 bg-white/[0.03] hover:border-white/20'"
        @click="skin = 'auto'"
      >
        <span class="flex h-10 w-14 shrink-0 overflow-hidden rounded-lg border border-white/10" aria-hidden="true">
          <span
            v-for="color in autoDefinition.swatch"
            :key="color"
            class="flex-1"
            :style="{ background: color }"
          ></span>
        </span>
        <span class="min-w-0 flex-1">
          <span class="block text-xs font-black uppercase tracking-widest text-slate-100">
            Auto · {{ autoDefinition.label }}
          </span>
          <span class="block text-xs leading-relaxed text-slate-400">Follows the adventure: {{ props.autoReason }}.</span>
        </span>
      </button>

      <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <button
          v-for="definition in SKINS"
          :key="definition.id"
          type="button"
          role="radio"
          :aria-checked="skin === definition.id"
          class="flex items-center gap-3 rounded-2xl border p-3 text-left transition-all cursor-pointer"
          :class="skin === definition.id ? 'border-amber-400/70 bg-amber-500/10' : 'border-white/10 bg-white/[0.03] hover:border-white/20'"
          @click="skin = definition.id"
        >
          <span class="flex h-10 w-10 shrink-0 overflow-hidden rounded-lg border border-white/10" aria-hidden="true">
            <span
              v-for="color in definition.swatch"
              :key="color"
              class="flex-1"
              :style="{ background: color }"
            ></span>
          </span>
          <span class="min-w-0 flex-1">
            <span class="block text-xs font-black uppercase tracking-widest text-slate-100">{{ definition.label }}</span>
            <span class="block text-[11px] leading-snug text-slate-400">{{ definition.description }}</span>
          </span>
        </button>
      </div>
    </div>

    <section class="flex flex-col gap-2 border-t border-white/5 pt-4">
      <h4 class="text-xs font-black uppercase tracking-widest text-slate-100">Text Density</h4>
      <p class="text-xs leading-relaxed text-slate-400">
        Controls text size, line spacing and the padding around narration and dialogue in the story feed.
      </p>
      <div role="radiogroup" aria-label="Text density" class="grid grid-cols-3 gap-2">
        <button
          v-for="option in TEXT_DENSITY_OPTIONS"
          :key="option.id"
          type="button"
          role="radio"
          :aria-checked="density === option.id"
          class="flex flex-col gap-2 rounded-2xl border p-3 text-left transition-all cursor-pointer"
          :class="density === option.id ? 'border-amber-400/70 bg-amber-500/10' : 'border-white/10 bg-white/[0.03] hover:border-white/20'"
          @click="density = option.id"
        >
          <span
            class="flex flex-col rounded-lg border border-white/10 bg-slate-950/60 p-2"
            :style="{ gap: `${DENSITY_PREVIEW[option.id].gap}px` }"
            aria-hidden="true"
          >
            <span
              v-for="width in [100, 85, 92]"
              :key="width"
              class="block rounded-full bg-slate-500/70"
              :style="{ width: `${width}%`, height: `${DENSITY_PREVIEW[option.id].bar}px` }"
            ></span>
          </span>
          <span class="block text-xs font-black uppercase tracking-widest text-slate-100">{{ option.label }}</span>
          <span class="hidden text-[11px] leading-snug text-slate-400 sm:block">{{ option.description }}</span>
        </button>
      </div>
    </section>

    <section class="flex flex-col gap-2 border-t border-white/5 pt-4">
      <h4 class="text-xs font-black uppercase tracking-widest text-slate-100">Font Size</h4>
      <p class="text-xs leading-relaxed text-slate-400">
        Scales the text of narration, dialogue and system notes in the story feed. Works on top of the text density.
      </p>
      <div role="radiogroup" aria-label="Font size" class="grid grid-cols-5 gap-2">
        <button
          v-for="scale in TEXT_SCALES"
          :key="scale"
          type="button"
          role="radio"
          :aria-checked="textScale === scale"
          :title="`${Math.round(scale * 100)} %`"
          class="flex flex-col items-center gap-1 rounded-2xl border p-2 transition-all cursor-pointer"
          :class="textScale === scale ? 'border-amber-400/70 bg-amber-500/10' : 'border-white/10 bg-white/[0.03] hover:border-white/20'"
          @click="textScale = scale"
        >
          <span class="font-serif font-bold leading-none text-slate-100" :style="{ fontSize: `${scale}rem` }" aria-hidden="true">Aa</span>
          <span class="text-[11px] font-bold tabular-nums text-slate-400">{{ Math.round(scale * 100) }}%</span>
        </button>
      </div>
    </section>

    <p class="text-[11px] leading-relaxed text-slate-500">
      <span class="font-bold uppercase tracking-wider text-slate-400">About skins · </span>Auto uses the skin the
      adventure author picked; otherwise it matches the adventure's tone (for example Sci-Fi → Terminal,
      Mystery → Noir). Picking a skin here overrides that for every adventure on this device.
    </p>
  </div>
</template>
