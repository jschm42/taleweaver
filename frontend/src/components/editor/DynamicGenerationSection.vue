<script setup lang="ts">
import { computed } from 'vue'

export interface DynamicGenerationConfig {
  scene_image_mode: 'off' | 'inherit' | 'simple' | 'hq'
  npc_image_mode: 'off' | 'simple' | 'hq'
  item_image_mode: 'off' | 'simple' | 'hq'
  audio_mode: 'inherit' | 'empty' | 'generate'
  max_npcs: number
  interlude_quote_enabled: boolean
}

const DEFAULT_CONFIG: DynamicGenerationConfig = {
  scene_image_mode: 'simple',
  npc_image_mode: 'simple',
  item_image_mode: 'simple',
  audio_mode: 'inherit',
  max_npcs: 2,
  interlude_quote_enabled: true,
}

const props = defineProps<{
  modelValue?: Partial<DynamicGenerationConfig> | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: DynamicGenerationConfig): void
}>()

const config = computed<DynamicGenerationConfig>(() => ({
  scene_image_mode: props.modelValue?.scene_image_mode || DEFAULT_CONFIG.scene_image_mode,
  npc_image_mode: props.modelValue?.npc_image_mode || DEFAULT_CONFIG.npc_image_mode,
  item_image_mode: props.modelValue?.item_image_mode || DEFAULT_CONFIG.item_image_mode,
  audio_mode: props.modelValue?.audio_mode || DEFAULT_CONFIG.audio_mode,
  max_npcs: clampMaxNpcs(props.modelValue?.max_npcs ?? DEFAULT_CONFIG.max_npcs),
  interlude_quote_enabled:
    props.modelValue?.interlude_quote_enabled !== undefined
      ? Boolean(props.modelValue.interlude_quote_enabled)
      : DEFAULT_CONFIG.interlude_quote_enabled,
}))

function clampMaxNpcs(raw: unknown): number {
  const num = Number(raw)
  if (!Number.isFinite(num)) return DEFAULT_CONFIG.max_npcs
  return Math.max(0, Math.min(5, Math.round(num)))
}

function updateField<K extends keyof DynamicGenerationConfig>(
  key: K,
  value: DynamicGenerationConfig[K],
) {
  emit('update:modelValue', {
    ...config.value,
    [key]: value,
  })
}
</script>

<template>
  <div class="p-8 bg-slate-900/50 border border-white/5 rounded-3xl space-y-6 animate-page-in">
    <div class="space-y-1">
      <h4 class="text-xs font-black text-white uppercase tracking-widest flex items-center gap-2">
        <i class="ra ra-compass text-emerald-400"></i> Dynamic Generator
      </h4>
      <p class="text-xs text-slate-400 leading-relaxed">
        Configure how on-the-fly procedural scenes, portraits, item artwork, audio, and loading quotes behave when players enter Dynamic Zone Exits.
      </p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <label class="block space-y-1.5">
        <span class="text-xs font-bold text-slate-200">Scene Image Generation</span>
        <select
          :value="config.scene_image_mode"
          class="w-full bg-black/40 border border-white/10 rounded-2xl px-4 py-3 text-sm text-white focus:border-emerald-500 outline-none transition-all"
          @change="updateField('scene_image_mode', ($event.target as HTMLSelectElement).value as DynamicGenerationConfig['scene_image_mode'])"
        >
          <option value="simple">Simple Model (fast scene artwork)</option>
          <option value="hq">High Quality Model (detailed scene artwork)</option>
          <option value="inherit">Inherit from Originating Scene</option>
          <option value="off">Off (no scene image)</option>
        </select>
      </label>

      <label class="block space-y-1.5">
        <span class="text-xs font-bold text-slate-200">NPC Portrait Generation</span>
        <select
          :value="config.npc_image_mode"
          class="w-full bg-black/40 border border-white/10 rounded-2xl px-4 py-3 text-sm text-white focus:border-emerald-500 outline-none transition-all"
          @change="updateField('npc_image_mode', ($event.target as HTMLSelectElement).value as DynamicGenerationConfig['npc_image_mode'])"
        >
          <option value="simple">Simple Model (fast NPC portraits)</option>
          <option value="hq">High Quality Model (detailed portraits)</option>
          <option value="off">Off (no portraits)</option>
        </select>
      </label>

      <label class="block space-y-1.5">
        <span class="text-xs font-bold text-slate-200">Item Image Generation</span>
        <select
          :value="config.item_image_mode"
          class="w-full bg-black/40 border border-white/10 rounded-2xl px-4 py-3 text-sm text-white focus:border-emerald-500 outline-none transition-all"
          @change="updateField('item_image_mode', ($event.target as HTMLSelectElement).value as DynamicGenerationConfig['item_image_mode'])"
        >
          <option value="simple">Simple Model (fast item artwork)</option>
          <option value="hq">High Quality Model (detailed item artwork)</option>
          <option value="off">Off (no item images)</option>
        </select>
      </label>

      <label class="block space-y-1.5">
        <span class="text-xs font-bold text-slate-200">Dynamic Scene Audio</span>
        <select
          :value="config.audio_mode"
          class="w-full bg-black/40 border border-white/10 rounded-2xl px-4 py-3 text-sm text-white focus:border-emerald-500 outline-none transition-all"
          @change="updateField('audio_mode', ($event.target as HTMLSelectElement).value as DynamicGenerationConfig['audio_mode'])"
        >
          <option value="inherit">Inherit from Originating Scene</option>
          <option value="empty">Empty (silence)</option>
          <option value="generate">Generate New Music Track</option>
        </select>
      </label>

      <label class="block space-y-1.5">
        <span class="text-xs font-bold text-slate-200">Max NPCs per Scene (0–5)</span>
        <input
          type="number"
          min="0"
          max="5"
          :value="config.max_npcs"
          class="w-full bg-black/40 border border-white/10 rounded-2xl px-4 py-3 text-sm text-white focus:border-emerald-500 outline-none transition-all"
          @input="updateField('max_npcs', clampMaxNpcs(($event.target as HTMLInputElement).value))"
        />
      </label>

      <div class="md:col-span-2 flex items-start gap-4 p-4 bg-black/30 border border-white/5 rounded-2xl">
        <div class="space-y-1 min-w-0 flex-1">
          <p class="text-sm font-bold text-white">Interlude NPC Quote</p>
          <p class="text-xs text-slate-500 leading-relaxed">
            Display (and optionally read aloud) a short atmospheric NPC quote while a dynamic scene is generated.
          </p>
        </div>
        <button
          type="button"
          :class="[
            'w-14 h-8 shrink-0 mt-0.5 rounded-full transition-all relative flex items-center px-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500',
            config.interlude_quote_enabled ? 'bg-emerald-600' : 'bg-slate-800',
          ]"
          :aria-pressed="config.interlude_quote_enabled"
          @click="updateField('interlude_quote_enabled', !config.interlude_quote_enabled)"
        >
          <div
            :class="[
              'w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300',
              config.interlude_quote_enabled ? 'translate-x-6' : 'translate-x-0',
            ]"
          />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-page-in {
  animation: pageIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes pageIn {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
