<script setup lang="ts">
import { computed, ref } from 'vue'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import EditorIdInput from '@/components/editor/EditorIdInput.vue'
import {
  EDITOR_ID_PREFIXES,
  MAX_EDITOR_ID_LENGTH,
  generateEditorId,
  sanitizeEditorId,
} from '@/utils/editor_utils'
import { Plus, Trash2, ChevronDown, ChevronUp, Code2 } from 'lucide-vue-next'

export interface SequenceScript {
  id: string
  name?: string
  trigger: string
  target_id?: string
  code: string
  description?: string
}

interface TargetOption {
  id: string
  name: string
}

const props = withDefaults(defineProps<{
  modelValue?: SequenceScript[]
  scenes?: TargetOption[]
  entities?: TargetOption[]
}>(), {
  modelValue: () => [],
  scenes: () => [],
  entities: () => [],
})

const emit = defineEmits<{
  (e: 'update:modelValue', scripts: SequenceScript[]): void
}>()

// Same triggers as top-level scripts, except on_init (no sequence is active yet).
type TargetKind = 'entity' | 'scene' | 'time' | null

const TRIGGERS: { value: string; label: string; target: TargetKind }[] = [
  { value: 'on_interact', label: 'On Interact (object / NPC)', target: 'entity' },
  { value: 'on_enter_scene', label: 'On Enter Scene', target: 'scene' },
  { value: 'on_turn_start', label: 'On Turn Start', target: null },
  { value: 'on_turn_end', label: 'On Turn End', target: null },
  { value: 'on_logic_pass_done', label: 'On Logic Pass Done (every message)', target: null },
  { value: 'on_narration_done', label: 'On Narration Done (every message)', target: null },
  { value: 'on_time_reached', label: 'On Time Reached (elapsed in-game time)', target: 'time' },
]

const scripts = computed<SequenceScript[]>(() => (Array.isArray(props.modelValue) ? props.modelValue : []))
const expandedIndex = ref<number | null>(null)

function targetKind(trigger: string): TargetKind {
  return TRIGGERS.find((t) => t.value === trigger)?.target ?? null
}

function targetOptions(trigger: string): TargetOption[] {
  const kind = targetKind(trigger)
  if (kind === 'entity') return props.entities
  if (kind === 'scene') return props.scenes
  return []
}

function targetName(script: SequenceScript): string {
  if (!script.target_id) return 'any'
  return targetOptions(script.trigger).find((o) => o.id === script.target_id)?.name || script.target_id
}

function updateScript(index: number, patch: Partial<SequenceScript>): void {
  emit('update:modelValue', scripts.value.map((s, i) => (i === index ? { ...s, ...patch } : s)))
}

function updateId(index: number, raw: string): void {
  updateScript(index, { id: sanitizeEditorId(raw, MAX_EDITOR_ID_LENGTH) })
}

function updateTrigger(index: number, trigger: string): void {
  // A target only makes sense for the matching trigger kind.
  const keepTarget = targetKind(trigger) === targetKind(scripts.value[index].trigger)
  updateScript(index, { trigger, target_id: keepTarget ? scripts.value[index].target_id : '' })
}

function addScript(): void {
  const script: SequenceScript = {
    id: generateEditorId({
      prefix: EDITOR_ID_PREFIXES.SCRIPT,
      takenIds: scripts.value.map((s) => String(s.id || '')),
      maxLen: MAX_EDITOR_ID_LENGTH,
    }),
    name: '',
    trigger: 'on_interact',
    target_id: '',
    code: '',
    description: '',
  }
  emit('update:modelValue', [...scripts.value, script])
  expandedIndex.value = scripts.value.length
}

function removeScript(index: number): void {
  emit('update:modelValue', scripts.value.filter((_, i) => i !== index))
  expandedIndex.value = null
}

function toggle(index: number): void {
  expandedIndex.value = expandedIndex.value === index ? null : index
}
</script>

<template>
  <div class="space-y-4">
    <div class="space-y-1">
      <p class="text-xs font-black text-cyan-400 uppercase tracking-widest flex items-center gap-2">
        <Code2 class="w-4 h-4" /> Sequence Scripts
      </p>
      <p class="text-[11px] text-slate-400">
        Event scripts that only run while this sequence is active. They use the same triggers as
        global scripts (except On Init). Use them for chapter-specific behaviour, e.g. a bomb that
        opens a choice dialog only during this chapter.
      </p>
    </div>

    <p v-if="scripts.length === 0" class="text-[11px] text-slate-500 italic">
      No sequence scripts yet. Example: On Interact with the bomb → <code>open_bomb_dialog()</code>.
    </p>

    <div
      v-for="(script, index) in scripts"
      :key="index"
      class="border border-white/5 bg-black/30 rounded-2xl"
    >
      <!-- Header -->
      <div class="flex items-center gap-3 px-4 py-3">
        <button
          type="button"
          class="flex-1 min-w-0 flex items-center gap-2 text-left"
          @click="toggle(index)"
        >
          <component :is="expandedIndex === index ? ChevronUp : ChevronDown" class="w-4 h-4 shrink-0 text-slate-500" />
          <span class="text-[10px] font-mono text-cyan-300 shrink-0">{{ script.id || '(no id)' }}</span>
          <span class="text-xs text-slate-300 truncate">
            {{ script.trigger }}<template v-if="targetKind(script.trigger)"> · {{ targetName(script) }}</template>
            <template v-if="script.name"> · {{ script.name }}</template>
          </span>
        </button>
        <button
          type="button"
          class="shrink-0 p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
          title="Remove sequence script"
          @click="removeScript(index)"
        >
          <Trash2 class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- Body -->
      <div v-if="expandedIndex === index" class="space-y-4 px-4 pb-4 border-t border-white/5 pt-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div class="space-y-1">
            <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">Script ID</label>
            <EditorIdInput
              :model-value="script.id"
              :prefix="EDITOR_ID_PREFIXES.SCRIPT"
              :source-name="script.name || ''"
              :taken-ids="scripts.filter((_, i) => i !== index).map((s) => String(s.id || ''))"
              :max-length="MAX_EDITOR_ID_LENGTH"
              :compact="true"
              :required="true"
              placeholder="SCR_TAMPER_BOMB"
              aria-label="Script ID"
              @update:model-value="(val) => updateId(index, val)"
            />
          </div>
          <div class="space-y-1">
            <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">Name (optional)</label>
            <input
              :value="script.name || ''"
              type="text"
              placeholder="e.g. Bomb tamper dialog"
              class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-cyan-500/50 outline-none"
              @input="updateScript(index, { name: ($event.target as HTMLInputElement).value })"
            />
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div class="space-y-1">
            <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">Trigger</label>
            <select
              :value="script.trigger"
              class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-cyan-500/50 outline-none"
              @change="updateTrigger(index, ($event.target as HTMLSelectElement).value)"
            >
              <option v-for="t in TRIGGERS" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </div>
          <div v-if="targetKind(script.trigger) === 'time'" class="space-y-1">
            <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">
              Elapsed In-Game Time
            </label>
            <input
              :value="script.target_id || ''"
              type="text"
              placeholder="e.g. 90, 2h 30m, 1d"
              title="Minutes since the adventure started. Fires once when the clock reaches it while this sequence is active."
              class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white font-mono focus:border-cyan-500/50 outline-none"
              @input="updateScript(index, { target_id: ($event.target as HTMLInputElement).value })"
            />
          </div>
          <div v-else-if="targetKind(script.trigger)" class="space-y-1">
            <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">
              Target {{ targetKind(script.trigger) === 'scene' ? 'Scene' : 'Object / NPC' }}
            </label>
            <select
              :value="script.target_id || ''"
              class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-cyan-500/50 outline-none"
              @change="updateScript(index, { target_id: ($event.target as HTMLSelectElement).value })"
            >
              <option value="">Any</option>
              <option v-for="o in targetOptions(script.trigger)" :key="o.id" :value="o.id">{{ o.name }} ({{ o.id }})</option>
            </select>
          </div>
        </div>

        <ScriptEditor
          :model-value="script.code || ''"
          label="Script"
          help-text="Runs on the selected trigger, but only while this sequence is the active one."
          :context="script.trigger"
          placeholder="e.g. open_bomb_dialog()"
          min-height="100px"
          @update:model-value="updateScript(index, { code: $event })"
        />
      </div>
    </div>

    <button
      type="button"
      class="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-dashed border-white/15 text-xs font-bold uppercase tracking-wider text-slate-400 hover:text-cyan-300 hover:border-cyan-500/40 transition-colors"
      @click="addScript"
    >
      <Plus class="w-4 h-4" /> Add Sequence Script
    </button>
  </div>
</template>
