<script setup lang="ts">
import { computed } from 'vue'

export interface DynamicNpcTypeCaps {
  humanoid: number
  being: number
  animal: number
  monster: number
}

export interface DynamicSpawnChances {
  npc: number
  enemy: number
  humanoid: number
  being: number
  animal: number
  monster: number
  item: number
  container: number
  switch: number
}

export interface DynamicGenerationConfig {
  scene_image_mode: 'off' | 'inherit' | 'simple' | 'hq'
  npc_image_mode: 'off' | 'simple' | 'hq'
  item_image_mode: 'off' | 'simple' | 'hq'
  audio_mode: 'inherit' | 'empty' | 'generate'
  max_npcs: number
  npc_type_caps: DynamicNpcTypeCaps
  spawn_chances: DynamicSpawnChances
  interlude_quote_enabled: boolean
}

const DEFAULT_NPC_TYPE_CAPS: DynamicNpcTypeCaps = {
  humanoid: 2,
  being: 2,
  animal: 2,
  monster: 2,
}

const DEFAULT_SPAWN_CHANCES: DynamicSpawnChances = {
  npc: 55,
  enemy: 35,
  humanoid: 50,
  being: 20,
  animal: 30,
  monster: 25,
  item: 75,
  container: 30,
  switch: 20,
}

const DEFAULT_CONFIG: DynamicGenerationConfig = {
  scene_image_mode: 'simple',
  npc_image_mode: 'simple',
  item_image_mode: 'simple',
  audio_mode: 'inherit',
  max_npcs: 2,
  npc_type_caps: { ...DEFAULT_NPC_TYPE_CAPS },
  spawn_chances: { ...DEFAULT_SPAWN_CHANCES },
  interlude_quote_enabled: true,
}

const NPC_CAP_FIELDS: Array<{ key: keyof DynamicNpcTypeCaps; label: string }> = [
  { key: 'humanoid', label: 'Max Humanoids' },
  { key: 'being', label: 'Max Beings' },
  { key: 'animal', label: 'Max Animals' },
  { key: 'monster', label: 'Max Monsters' },
]

const SPAWN_CHANCE_FIELDS: Array<{ key: keyof DynamicSpawnChances; label: string; hint: string }> = [
  { key: 'npc', label: 'NPCs (Overall)', hint: '0% = always empty / silent' },
  { key: 'enemy', label: 'Hostile Enemies', hint: 'Chance an NPC is hostile' },
  { key: 'humanoid', label: 'Humanoids', hint: 'Relative weight / share' },
  { key: 'being', label: 'Beings', hint: 'Relative weight / share' },
  { key: 'animal', label: 'Animals', hint: 'Relative weight / share' },
  { key: 'monster', label: 'Monsters', hint: 'Relative weight / share' },
  { key: 'item', label: 'Items & Loot', hint: 'Chance items spawn in scene' },
  { key: 'container', label: 'Containers', hint: 'Chests, crates, lockers' },
  { key: 'switch', label: 'Switches', hint: 'Levers, buttons, mechanisms' },
]

const props = defineProps<{
  modelValue?: Partial<DynamicGenerationConfig> | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: DynamicGenerationConfig): void
}>()

function clampInt(raw: unknown, fallback: number, min: number, max: number): number {
  const num = Number(raw)
  if (!Number.isFinite(num)) return fallback
  return Math.max(min, Math.min(max, Math.round(num)))
}

const config = computed<DynamicGenerationConfig>(() => ({
  scene_image_mode: props.modelValue?.scene_image_mode || DEFAULT_CONFIG.scene_image_mode,
  npc_image_mode: props.modelValue?.npc_image_mode || DEFAULT_CONFIG.npc_image_mode,
  item_image_mode: props.modelValue?.item_image_mode || DEFAULT_CONFIG.item_image_mode,
  audio_mode: props.modelValue?.audio_mode || DEFAULT_CONFIG.audio_mode,
  max_npcs: clampInt(props.modelValue?.max_npcs ?? DEFAULT_CONFIG.max_npcs, DEFAULT_CONFIG.max_npcs, 0, 5),
  npc_type_caps: {
    humanoid: clampInt(props.modelValue?.npc_type_caps?.humanoid, DEFAULT_NPC_TYPE_CAPS.humanoid, 0, 5),
    being: clampInt(props.modelValue?.npc_type_caps?.being, DEFAULT_NPC_TYPE_CAPS.being, 0, 5),
    animal: clampInt(props.modelValue?.npc_type_caps?.animal, DEFAULT_NPC_TYPE_CAPS.animal, 0, 5),
    monster: clampInt(props.modelValue?.npc_type_caps?.monster, DEFAULT_NPC_TYPE_CAPS.monster, 0, 5),
  },
  spawn_chances: {
    npc: clampInt(props.modelValue?.spawn_chances?.npc, DEFAULT_SPAWN_CHANCES.npc, 0, 100),
    enemy: clampInt(props.modelValue?.spawn_chances?.enemy, DEFAULT_SPAWN_CHANCES.enemy, 0, 100),
    humanoid: clampInt(props.modelValue?.spawn_chances?.humanoid, DEFAULT_SPAWN_CHANCES.humanoid, 0, 100),
    being: clampInt(props.modelValue?.spawn_chances?.being, DEFAULT_SPAWN_CHANCES.being, 0, 100),
    animal: clampInt(props.modelValue?.spawn_chances?.animal, DEFAULT_SPAWN_CHANCES.animal, 0, 100),
    monster: clampInt(props.modelValue?.spawn_chances?.monster, DEFAULT_SPAWN_CHANCES.monster, 0, 100),
    item: clampInt(props.modelValue?.spawn_chances?.item, DEFAULT_SPAWN_CHANCES.item, 0, 100),
    container: clampInt(props.modelValue?.spawn_chances?.container, DEFAULT_SPAWN_CHANCES.container, 0, 100),
    switch: clampInt(props.modelValue?.spawn_chances?.switch, DEFAULT_SPAWN_CHANCES.switch, 0, 100),
  },
  interlude_quote_enabled:
    props.modelValue?.interlude_quote_enabled !== undefined
      ? Boolean(props.modelValue.interlude_quote_enabled)
      : DEFAULT_CONFIG.interlude_quote_enabled,
}))

function clampMaxNpcs(raw: unknown): number {
  return clampInt(raw, DEFAULT_CONFIG.max_npcs, 0, 5)
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

function updateNpcCap(key: keyof DynamicNpcTypeCaps, raw: unknown) {
  updateField('npc_type_caps', {
    ...config.value.npc_type_caps,
    [key]: clampInt(raw, DEFAULT_NPC_TYPE_CAPS[key], 0, 5),
  })
}

function updateSpawnChance(key: keyof DynamicSpawnChances, raw: unknown) {
  updateField('spawn_chances', {
    ...config.value.spawn_chances,
    [key]: clampInt(raw, DEFAULT_SPAWN_CHANCES[key], 0, 100),
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

      <div class="md:col-span-2 p-5 bg-black/25 border border-white/5 rounded-2xl space-y-3">
        <div>
          <p class="text-xs font-black uppercase tracking-wider text-slate-200">
            Max NPCs per Type (0–5)
          </p>
          <p class="text-[11px] text-slate-500">
            Fine-tune how many humanoids, beings, animals, or monsters may appear in one scene. Set to 0 to forbid that type.
          </p>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <label
            v-for="cap in NPC_CAP_FIELDS"
            :key="cap.key"
            class="block space-y-1"
          >
            <span class="text-[11px] font-bold text-slate-300">{{ cap.label }}</span>
            <input
              type="number"
              min="0"
              max="5"
              :value="config.npc_type_caps[cap.key]"
              class="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:border-emerald-500 outline-none"
              @input="updateNpcCap(cap.key, ($event.target as HTMLInputElement).value)"
            />
          </label>
        </div>
      </div>

      <div class="md:col-span-2 p-5 bg-black/25 border border-white/5 rounded-2xl space-y-4">
        <div>
          <p class="text-xs font-black uppercase tracking-wider text-slate-200">
            Default Spawn Probabilities (0–100%)
          </p>
          <p class="text-[11px] text-slate-500">
            Control how likely NPCs, enemies, creatures, items, containers, and switches are generated. Individual Dynamic Exits can override any value.
          </p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <label
            v-for="field in SPAWN_CHANCE_FIELDS"
            :key="field.key"
            class="block space-y-1.5 bg-black/30 border border-white/5 rounded-xl p-3"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="text-xs font-bold text-slate-200">{{ field.label }}</span>
              <span class="text-xs font-mono font-bold text-emerald-400">
                {{ config.spawn_chances[field.key] }}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              :value="config.spawn_chances[field.key]"
              class="w-full accent-emerald-500 cursor-pointer"
              @input="updateSpawnChance(field.key, ($event.target as HTMLInputElement).value)"
            />
            <p class="text-[10px] text-slate-500">{{ field.hint }}</p>
          </label>
        </div>
      </div>

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
