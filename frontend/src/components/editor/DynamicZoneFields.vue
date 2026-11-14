<script setup lang="ts">
import { computed, ref } from 'vue'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'

export interface DynamicZoneNpcCapsOverride {
  humanoid?: number | null
  being?: number | null
  animal?: number | null
  monster?: number | null
}

export interface DynamicZoneSpawnChancesOverride {
  npc?: number | null
  enemy?: number | null
  humanoid?: number | null
  being?: number | null
  animal?: number | null
  monster?: number | null
  item?: number | null
  container?: number | null
  switch?: number | null
}

import EditorIdInput from '@/components/editor/EditorIdInput.vue'
import {
  EDITOR_ID_PREFIXES,
  buildDynamicPlaceholderSceneId,
} from '@/utils/editor_utils'

export interface DynamicZoneForm {
  zone_id: string
  theme: string
  instructions?: string | null
  instructions_scope?: 'once' | 'first_scene' | 'max_depth' | 'all_scenes' | null
  cluster_consistency?: boolean
  depth: number
  max_depth: number
  danger_level: 'peaceful' | 'low' | 'medium' | 'high' | 'deadly' | 'random'
  max_npcs?: number
  npc_type_caps?: DynamicZoneNpcCapsOverride | null
  spawn_chances?: DynamicZoneSpawnChancesOverride | null
  audio_mode?: 'inherit' | 'empty' | 'generate' | null
  cul_de_sac_on_max_depth: boolean
  on_after_generated_script?: string | null
}

const NPC_CAP_FIELDS: Array<{ key: keyof DynamicZoneNpcCapsOverride; label: string }> = [
  { key: 'humanoid', label: 'Max Humanoids' },
  { key: 'being', label: 'Max Beings' },
  { key: 'animal', label: 'Max Animals' },
  { key: 'monster', label: 'Max Monsters' },
]

const SPAWN_CHANCE_FIELDS: Array<{
  key: keyof DynamicZoneSpawnChancesOverride
  label: string
  defaultVal: number
}> = [
  { key: 'npc', label: 'NPCs (Overall)', defaultVal: 55 },
  { key: 'enemy', label: 'Hostile Enemies', defaultVal: 35 },
  { key: 'humanoid', label: 'Humanoids', defaultVal: 50 },
  { key: 'being', label: 'Beings', defaultVal: 20 },
  { key: 'animal', label: 'Animals', defaultVal: 30 },
  { key: 'monster', label: 'Monsters', defaultVal: 25 },
  { key: 'item', label: 'Items & Loot', defaultVal: 75 },
  { key: 'container', label: 'Containers', defaultVal: 30 },
  { key: 'switch', label: 'Switches', defaultVal: 20 },
]

const props = withDefaults(
  defineProps<{
    modelValue: DynamicZoneForm | null | undefined
    mode?: 'exit' | 'scene'
  }>(),
  {
    mode: 'exit',
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: DynamicZoneForm | null): void
}>()

const enabled = computed(() => Boolean(props.modelValue))
const isSceneMode = computed(() => props.mode === 'scene')
const activeDynamicTab = ref<'setup' | 'spawns' | 'after_generated'>('setup')

const zone = computed<DynamicZoneForm>(() => ({
  zone_id: props.modelValue?.zone_id || 'ZONE_WILD',
  theme: props.modelValue?.theme || '',
  instructions: props.modelValue?.instructions ?? '',
  instructions_scope: props.modelValue?.instructions_scope ?? 'once',
  cluster_consistency:
    props.modelValue?.cluster_consistency !== undefined
      ? Boolean(props.modelValue.cluster_consistency)
      : true,
  depth: props.modelValue?.depth ?? 1,
  max_depth: props.modelValue?.max_depth ?? 3,
  danger_level: props.modelValue?.danger_level || 'medium',
  max_npcs: props.modelValue?.max_npcs ?? 2,
  npc_type_caps: props.modelValue?.npc_type_caps ?? null,
  spawn_chances: props.modelValue?.spawn_chances ?? null,
  audio_mode: props.modelValue?.audio_mode ?? null,
  cul_de_sac_on_max_depth:
    props.modelValue?.cul_de_sac_on_max_depth !== undefined
      ? Boolean(props.modelValue.cul_de_sac_on_max_depth)
      : true,
  on_after_generated_script: props.modelValue?.on_after_generated_script ?? '',
}))

const hasAnyOverride = computed(() => {
  const caps = zone.value.npc_type_caps || {}
  const chances = zone.value.spawn_chances || {}
  return (
    Object.values(caps).some((v) => v !== null && v !== undefined) ||
    Object.values(chances).some((v) => v !== null && v !== undefined)
  )
})

const placeholderTargetId = computed(() =>
  buildDynamicPlaceholderSceneId(
    zone.value.zone_id || 'ZONE_WILD',
    zone.value.depth || 1,
    1,
  ),
)

function toggleEnabled() {
  if (enabled.value) {
    emit('update:modelValue', null)
  } else {
    emit('update:modelValue', {
      zone_id: 'ZONE_WILD',
      theme: '',
      instructions: '',
      instructions_scope: 'once',
      cluster_consistency: true,
      depth: 1,
      max_depth: 3,
      danger_level: 'medium',
      max_npcs: 2,
      npc_type_caps: null,
      spawn_chances: null,
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

function updateCapOverride(key: keyof DynamicZoneNpcCapsOverride, raw: string) {
  const next: DynamicZoneNpcCapsOverride = { ...(zone.value.npc_type_caps || {}) }
  if (raw === '') {
    next[key] = null
  } else {
    const parsed = Math.max(0, Math.min(5, Math.round(Number(raw) || 0)))
    next[key] = parsed
  }
  const hasVal = Object.values(next).some((v) => v !== null && v !== undefined)
  updateField('npc_type_caps', hasVal ? next : null)
}

function updateChanceOverride(key: keyof DynamicZoneSpawnChancesOverride, raw: number | null) {
  const next: DynamicZoneSpawnChancesOverride = { ...(zone.value.spawn_chances || {}) }
  if (raw === null) {
    next[key] = null
  } else {
    next[key] = Math.max(0, Math.min(100, Math.round(raw)))
  }
  const hasVal = Object.values(next).some((v) => v !== null && v !== undefined)
  updateField('spawn_chances', hasVal ? next : null)
}

function applyAbandonedPreset() {
  emit('update:modelValue', {
    ...zone.value,
    danger_level: 'peaceful',
    max_npcs: 0,
    npc_type_caps: { humanoid: 0, being: 0, animal: 0, monster: 0 },
    spawn_chances: {
      ...(zone.value.spawn_chances || {}),
      npc: 0,
      enemy: 0,
      humanoid: 0,
      being: 0,
      animal: 0,
      monster: 0,
    },
  })
}

function clearOverrides() {
  emit('update:modelValue', {
    ...zone.value,
    npc_type_caps: null,
    spawn_chances: null,
  })
}
</script>

<template>
  <div class="border border-emerald-500/20 rounded-2xl p-4 bg-emerald-950/10 space-y-4">
    <div class="flex items-center justify-between gap-3">
      <div class="space-y-0.5">
        <p class="text-xs font-black uppercase tracking-wider text-emerald-400">
          {{
            isSceneMode
              ? 'Dynamic Scene (Generate on First Entry)'
              : 'Dynamic Zone Exit (Procedural Scene Generation)'
          }}
        </p>
        <p class="text-[11px] text-slate-400">
          {{
            isSceneMode
              ? 'Preserve authored exits and static entities, generating scene details, visuals, and random encounters on first player entry.'
              : 'Generate a persistent session scene on-the-fly when a player enters this passage.'
          }}
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
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div v-if="!isSceneMode" class="text-[11px] text-emerald-300/80 font-mono">
          Target placeholder: {{ placeholderTargetId }}
        </div>
        <div v-else class="text-[11px] text-emerald-300/80">
          Share a Zone ID across multiple Dynamic Scenes or Exits to share cluster consistency.
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-slate-800 hover:bg-emerald-900/50 text-emerald-300 border border-emerald-500/30 transition-colors"
            @click="applyAbandonedPreset"
          >
            Abandoned / Silent Place
          </button>
          <button
            v-if="hasAnyOverride"
            type="button"
            class="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-black/40 hover:bg-white/10 text-slate-300 border border-white/10 transition-colors"
            @click="clearOverrides"
          >
            Reset Overrides
          </button>
        </div>
      </div>

      <div class="flex gap-1 border-b border-white/10">
        <button
          type="button"
          :class="[
            'px-3 py-1.5 text-[11px] font-bold rounded-t-lg border-b-2 transition-colors',
            activeDynamicTab === 'setup'
              ? 'border-emerald-400 text-white bg-black/30'
              : 'border-transparent text-slate-400 hover:text-slate-200',
          ]"
          @click="activeDynamicTab = 'setup'"
        >
          Zone Setup
        </button>
        <button
          type="button"
          :class="[
            'px-3 py-1.5 text-[11px] font-bold rounded-t-lg border-b-2 transition-colors flex items-center gap-1.5',
            activeDynamicTab === 'spawns'
              ? 'border-emerald-400 text-white bg-black/30'
              : 'border-transparent text-slate-400 hover:text-slate-200',
          ]"
          @click="activeDynamicTab = 'spawns'"
        >
          <span>Spawn Caps &amp; Chances</span>
          <span v-if="hasAnyOverride" class="w-1.5 h-1.5 rounded-full bg-emerald-400" />
        </button>
        <button
          type="button"
          :class="[
            'px-3 py-1.5 text-[11px] font-bold rounded-t-lg border-b-2 transition-colors flex items-center gap-1.5',
            activeDynamicTab === 'after_generated'
              ? 'border-emerald-400 text-white bg-black/30'
              : 'border-transparent text-slate-400 hover:text-slate-200',
          ]"
          @click="activeDynamicTab = 'after_generated'"
        >
          <span>After Generated</span>
          <span v-if="(zone.on_after_generated_script || '').trim()" class="w-1.5 h-1.5 rounded-full bg-cyan-400" />
        </button>
      </div>

      <template v-if="activeDynamicTab === 'setup'">
        <div :class="isSceneMode ? 'grid md:grid-cols-3 gap-3' : 'grid md:grid-cols-2 lg:grid-cols-4 gap-3'">
          <div class="text-xs text-slate-300 space-y-1">
            <span class="block">Zone ID</span>
            <EditorIdInput
              :model-value="zone.zone_id"
              :prefix="EDITOR_ID_PREFIXES.ZONE"
              :source-name="zone.theme"
              :compact="true"
              placeholder="ZONE_IRON_MINES"
              aria-label="Dynamic Zone ID"
              @update:model-value="(val) => updateField('zone_id', val)"
            />
          </div>

          <label v-if="!isSceneMode" class="text-xs text-slate-300 space-y-1">
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

        <label v-if="!isSceneMode" class="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
          <input
            type="checkbox"
            :checked="zone.cul_de_sac_on_max_depth"
            class="accent-emerald-500"
            @change="updateField('cul_de_sac_on_max_depth', ($event.target as HTMLInputElement).checked)"
          />
          <span>Cul-de-sac on max depth (stop branching with a climax/dead-end at max depth)</span>
        </label>

        <label class="flex items-start gap-2 text-xs text-slate-300 cursor-pointer select-none">
          <input
            type="checkbox"
            :checked="zone.cluster_consistency !== false"
            class="mt-0.5 accent-emerald-500"
            @change="updateField('cluster_consistency', ($event.target as HTMLInputElement).checked)"
          />
          <span>
            <span class="font-medium text-slate-200">Cluster consistency</span>
            <span class="block text-[11px] text-slate-400">
              Include global adventure theme, root zone theme, and existing cluster scenes (NPCs &amp; items) in generation prompts (uses more tokens; disable for independent generation).
            </span>
          </span>
        </label>

        <div class="space-y-2">
          <div class="flex items-center justify-between gap-2">
            <label class="text-xs font-medium text-slate-300">
              Generation Instructions (Loose Prompt or Blueprint)
            </label>
            <span class="text-[10px] font-mono text-slate-500">Optional</span>
          </div>
          <label v-if="!isSceneMode" class="text-xs text-slate-300 space-y-1 block">
            <span>Instructions Scope</span>
            <select
              :value="zone.instructions_scope || 'once'"
              class="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:border-emerald-500 outline-none"
              @change="updateField('instructions_scope', ($event.target as HTMLSelectElement).value as DynamicZoneForm['instructions_scope'])"
            >
              <option value="once">Once per cluster (avoid repeating unique items/NPCs — default)</option>
              <option value="first_scene">First scene only (depth 1)</option>
              <option value="max_depth">Climax scene only (max depth)</option>
              <option value="all_scenes">All scenes in cluster</option>
            </select>
          </label>
          <textarea
            :value="zone.instructions || ''"
            rows="4"
            placeholder="E.g. Generate a loot chest in the stable with a 1d+2 sword&#10;or Blueprint syntax:&#10;[Container: IRON_CHEST] Loot Chest&#10;&#10;[Weapon: IRON_SWORD] Iron Sword&#10;location: IRON_CHEST&#10;damage_dice: 1d+2"
            class="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-xs font-mono text-white placeholder:text-slate-600 focus:border-emerald-500 outline-none resize-y"
            @input="updateField('instructions', ($event.target as HTMLTextAreaElement).value)"
          />
          <p class="text-[11px] text-slate-400">
            Accepts freeform instructions or World-Builder Blueprint blocks ([Scene:], [NPC:], [Container:], [Weapon:], [Item:], ...). In Blueprint blocks, optional <code>depth: 1</code> or <code>depth: max</code> targets specific depths, and spawned entities are automatically deduplicated across the cluster.
          </p>
        </div>
      </template>

      <div v-else-if="activeDynamicTab === 'spawns'" class="space-y-4">
        <div class="space-y-2">
          <p class="text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Max NPCs per Type (blank = Use Global)
          </p>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
            <label v-for="cap in NPC_CAP_FIELDS" :key="cap.key" class="text-xs text-slate-300 space-y-1">
              <span class="text-[11px]">{{ cap.label }}</span>
              <input
                type="number"
                min="0"
                max="5"
                placeholder="Global"
                :value="zone.npc_type_caps?.[cap.key] ?? ''"
                class="w-full bg-black/40 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder:text-slate-500 focus:border-emerald-500 outline-none"
                @input="updateCapOverride(cap.key, ($event.target as HTMLInputElement).value)"
              />
            </label>
          </div>
        </div>

        <div class="space-y-2">
          <p class="text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Spawn Probability Overrides (0–100%)
          </p>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-2.5">
            <div
              v-for="field in SPAWN_CHANCE_FIELDS"
              :key="field.key"
              class="bg-black/30 border border-white/5 rounded-lg p-2.5 space-y-1"
            >
              <div class="flex items-center justify-between gap-2 text-[11px]">
                <span class="font-semibold text-slate-200">{{ field.label }}</span>
                <div class="flex items-center gap-1.5">
                  <span class="font-mono text-emerald-400">
                    {{
                      zone.spawn_chances?.[field.key] !== null &&
                      zone.spawn_chances?.[field.key] !== undefined
                        ? `${zone.spawn_chances[field.key]}%`
                        : 'Global'
                    }}
                  </span>
                  <button
                    v-if="
                      zone.spawn_chances?.[field.key] !== null &&
                      zone.spawn_chances?.[field.key] !== undefined
                    "
                    type="button"
                    class="text-[10px] text-slate-400 hover:text-white underline"
                    @click="updateChanceOverride(field.key, null)"
                  >
                    Inherit
                  </button>
                </div>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                :value="zone.spawn_chances?.[field.key] ?? field.defaultVal"
                class="w-full accent-emerald-500 cursor-pointer"
                @input="updateChanceOverride(field.key, Number(($event.target as HTMLInputElement).value))"
              />
            </div>
          </div>
        </div>
      </div>

      <div v-else class="space-y-3">
        <ScriptEditor
          :model-value="zone.on_after_generated_script || ''"
          label="On After Generated Script"
          help-text="Executed right after a dynamic scene is generated and persisted. Read `generated_scene` (or `tw.generated_scene`) and clone/move items or NPCs into `generated_scene['id']`."
          context="after_generated"
          min-height="120px"
          @update:model-value="updateField('on_after_generated_script', $event || null)"
        />
        <div class="bg-black/30 border border-white/5 rounded-xl p-3 text-[11px] text-slate-400 space-y-1">
          <p class="font-bold text-slate-300">Available in <code>generated_scene</code> (and <code>tw.generated_scene</code>):</p>
          <p class="font-mono text-[10px] text-emerald-300/90">
            id, origin_scene_id, zone_id, theme, depth, max_depth, danger_level, name, description, npcs, objects, forward_exits
          </p>
          <p class="font-mono text-[10px] text-slate-300">
            Example: <code>if generated_scene["depth"] == generated_scene["max_depth"]: tw.items.clone("RELIC_KEY", scene_id=generated_scene["id"])</code>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
