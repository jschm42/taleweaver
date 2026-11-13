<script setup lang="ts">
import { computed } from 'vue'

export interface DynamicZoneForm {
  zone_id: string
  theme: string
  depth: number
  max_depth: number
  danger_level: 'peaceful' | 'low' | 'medium' | 'high' | 'deadly' | 'random'
  max_npcs?: number
  audio_mode?: 'inherit' | 'empty' | 'generate' | null
  cul_de_sac_on_max_depth: boolean
}

const props = defineProps<{
  modelValue: DynamicZoneForm | null | undefined
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: DynamicZoneForm | null): void
}>()

const enabled = computed(() => Boolean(props.modelValue))

const zone = computed<DynamicZoneForm>(() => ({
  zone_id: props.modelValue?.zone_id || 'wild_zone',
  theme: props.modelValue?.theme || '',
  depth: props.modelValue?.depth ?? 1,
  max_depth: props.modelValue?.max_depth ?? 3,
  danger_level: props.modelValue?.danger_level || 'medium',
  max_npcs: props.modelValue?.max_npcs ?? 2,
  audio_mode: props.modelValue?.audio_mode ?? null,
  cul_de_sac_on_max_depth:
    props.modelValue?.cul_de_sac_on_max_depth !== undefined
      ? Boolean(props.modelValue.cul_de_sac_on_max_depth)
      : true,
}))

const placeholderTargetId = computed(() => {
  const clean = String(zone.value.zone_id || 'wild_zone')
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '') || 'ZONE'
  return `DYN_${clean}_D${zone.value.depth || 1}_1`
})

function toggleEnabled() {
  if (enabled.value) {
    emit('update:modelValue', null)
  } else {
    emit('update:modelValue', {
      zone_id: 'wild_zone',
      theme: '',
      depth: 1,
      max_depth: 3,
      danger_level: 'medium',
      max_npcs: 2,
      audio_mode: null,
      cul_de_sac_on_max_depth: true,
    })
  }
}

function updateField<K extends keyof DynamicZoneForm>(key: K, value: DynamicZoneForm[K]) {
  emit('update:modelValue', {
    ...zone.value,
    [key]: value,
  })
}
</script>

<template>
  <div class="border border-emerald-500/20 rounded-2xl p-4 bg-emerald-950/10 space-y-4">
    <div class="flex items-center justify-between gap-3">
      <div class="space-y-0.5">
        <p class="text-xs font-black uppercase tracking-wider text-emerald-400">
          Dynamic Zone Exit (Procedural Scene Generation)
        </p>
        <p class="text-[11px] text-slate-400">
          Generate a persistent session scene on-the-fly when a player enters this passage.
        </p>
      </div>
      <button
        type="button"
        :class="[
          'w-12 h-7 shrink-0 rounded-full transition-all relative flex items-center px-1',
          enabled ? 'bg-emerald-600' : 'bg-slate-800',
        ]"
        :aria-pressed="enabled"
        @click="toggleEnabled"
      >
        <div
          :class="[
            'w-5 h-5 bg-white rounded-full shadow transition-transform duration-200',
            enabled ? 'translate-x-5' : 'translate-x-0',
          ]"
        />
      </button>
    </div>

    <div v-if="enabled" class="space-y-3 pt-2 border-t border-white/10">
      <div class="text-[11px] text-emerald-300/80 font-mono">
        Target placeholder: {{ placeholderTargetId }}
      </div>

      <div class="grid md:grid-cols-2 lg:grid-cols-4 gap-3">
        <label class="text-xs text-slate-300 space-y-1">
          <span>Zone ID</span>
          <input
            :value="zone.zone_id"
            maxlength="40"
            placeholder="iron_mines"
            class="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:border-emerald-500 outline-none"
            @input="updateField('zone_id', ($event.target as HTMLInputElement).value)"
          />
        </label>

        <label class="text-xs text-slate-300 space-y-1">
          <span>Max Depth (1–6)</span>
          <input
            type="number"
            min="1"
            max="6"
            :value="zone.max_depth"
            class="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:border-emerald-500 outline-none"
            @input="updateField('max_depth', Math.min(6, Math.max(1, Number(($event.target as HTMLInputElement).value) || 1)))"
          />
        </label>

        <label class="text-xs text-slate-300 space-y-1">
          <span>Max NPCs (0–5)</span>
          <input
            type="number"
            min="0"
            max="5"
            :value="zone.max_npcs ?? 2"
            class="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:border-emerald-500 outline-none"
            @input="updateField('max_npcs', Math.min(5, Math.max(0, Number(($event.target as HTMLInputElement).value) || 0)))"
          />
        </label>

        <label class="text-xs text-slate-300 space-y-1">
          <span>Danger Level</span>
          <select
            :value="zone.danger_level"
            class="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:border-emerald-500 outline-none"
            @change="updateField('danger_level', ($event.target as HTMLSelectElement).value as DynamicZoneForm['danger_level'])"
          >
            <option value="peaceful">Peaceful (no hostiles)</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="deadly">Deadly</option>
            <option value="random">Random</option>
          </select>
        </label>
      </div>

      <label class="text-xs text-slate-300 space-y-1 block">
        <span>Music Override</span>
        <select
          :value="zone.audio_mode || ''"
          class="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:border-emerald-500 outline-none"
          @change="updateField('audio_mode', (($event.target as HTMLSelectElement).value || null) as DynamicZoneForm['audio_mode'])"
        >
          <option value="">Use Global Setting</option>
          <option value="inherit">Inherit from Originating Scene</option>
          <option value="generate">Generate New Music Track</option>
          <option value="empty">Off (silence)</option>
        </select>
      </label>

      <label class="text-xs text-slate-300 space-y-1 block">
        <span>Zone Theme <span class="text-red-400">*</span></span>
        <textarea
          :value="zone.theme"
          rows="2"
          maxlength="500"
          placeholder="e.g. Abandoned dwarven iron mine, flooded tracks, spider webs, decaying timber"
          class="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:border-emerald-500 outline-none resize-y"
          @input="updateField('theme', ($event.target as HTMLTextAreaElement).value)"
        />
      </label>

      <label class="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
        <input
          type="checkbox"
          :checked="zone.cul_de_sac_on_max_depth"
          class="accent-emerald-500"
          @change="updateField('cul_de_sac_on_max_depth', ($event.target as HTMLInputElement).checked)"
        />
        <span>Cul-de-sac on max depth (stop branching with a climax/dead-end at max depth)</span>
      </label>
    </div>
  </div>
</template>
