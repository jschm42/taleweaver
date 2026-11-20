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
import { ChevronDown, ChevronRight, Plus, Trash2 } from 'lucide-vue-next'
import UiButton from '@/components/ui/UiButton.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import type { SelectOption } from '@/components/ui/UiSelect.vue'

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
type TargetKind = 'entity' | 'scene' | 'time' | 'topic' | null

const TRIGGERS: { value: string; label: string; target: TargetKind }[] = [
  { value: 'on_interact', label: 'On interact (item / character)', target: 'entity' },
  { value: 'on_enter_scene', label: 'On enter scene', target: 'scene' },
  { value: 'on_turn_start', label: 'On turn start', target: null },
  { value: 'on_turn_end', label: 'On turn end', target: null },
  { value: 'on_logic_pass_done', label: 'On logic pass done (every message)', target: null },
  { value: 'on_narration_done', label: 'On narration done (every message)', target: null },
  { value: 'on_time_reached', label: 'On time reached (elapsed in-game time)', target: 'time' },
  { value: 'on_respawn', label: 'On respawn (protagonist revived)', target: null },
  { value: 'on_conversation_heard', label: 'On conversation heard (NPC topic overheard)', target: 'topic' },
]
const TRIGGER_OPTIONS: SelectOption[] = TRIGGERS.map((t) => ({ value: t.value, label: t.label }))

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

function targetSelectOptions(trigger: string): SelectOption[] {
  return [{ value: '', label: 'Any' }, ...targetOptions(trigger).map((o) => ({ value: o.id, label: `${o.name} (${o.id})` }))]
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
    <p class="wb-hint">
      Event scripts that only run while this chapter is active. They use the same triggers as global scripts (except
      On init), e.g. a bomb that opens a choice dialog only during this chapter.
    </p>

    <UiEmptyState
      v-if="scripts.length === 0"
      title="No chapter scripts yet"
      description="Example: On interact with the bomb runs open_bomb_dialog()."
    />

    <article v-for="(script, index) in scripts" :key="index" class="rounded-xl border border-wb-line bg-wb-raised">
      <div class="flex items-center gap-2 px-3 py-2">
        <button
          type="button"
          class="flex min-w-0 flex-1 items-center gap-2 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
          :aria-expanded="expandedIndex === index"
          @click="toggle(index)"
        >
          <component :is="expandedIndex === index ? ChevronDown : ChevronRight" class="h-4 w-4 shrink-0 text-wb-muted" />
          <span class="wb-mono shrink-0 text-wb-strong">{{ script.id || '(no ID)' }}</span>
          <span class="wb-body truncate text-wb-muted">
            {{ script.trigger }}<template v-if="targetKind(script.trigger)"> · {{ targetName(script) }}</template>
            <template v-if="script.name"> · {{ script.name }}</template>
          </span>
        </button>
        <UiIconButton :icon="Trash2" label="Remove chapter script" size="sm" variant="danger" @click="removeScript(index)" />
      </div>

      <div v-if="expandedIndex === index" class="space-y-4 border-t border-wb-line p-4">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <UiField label="Script ID" required>
            <EditorIdInput
              :model-value="script.id"
              :prefix="EDITOR_ID_PREFIXES.SCRIPT"
              :source-name="script.name || ''"
              :taken-ids="scripts.filter((_, i) => i !== index).map((s) => String(s.id || ''))"
              :max-length="MAX_EDITOR_ID_LENGTH"
              :required="true"
              placeholder="SCR_TAMPER_BOMB"
              aria-label="Script ID"
              @update:model-value="(val) => updateId(index, val)"
            />
          </UiField>
          <UiField label="Name" hint="Optional.">
            <UiInput
              :model-value="script.name || ''"
              placeholder="e.g. Bomb tamper dialog"
              @update:model-value="(v) => updateScript(index, { name: String(v ?? '') })"
            />
          </UiField>
          <UiField label="Trigger">
            <UiSelect
              :model-value="script.trigger"
              :options="TRIGGER_OPTIONS"
              @update:model-value="(v) => updateTrigger(index, String(v ?? ''))"
            />
          </UiField>
          <UiField
            v-if="targetKind(script.trigger) === 'time'"
            label="Elapsed in-game time"
            hint="Since the adventure started; fires once while this chapter is active."
          >
            <UiInput
              :model-value="script.target_id || ''"
              mono
              placeholder="e.g. 90, 2h 30m, 1d"
              @update:model-value="(v) => updateScript(index, { target_id: String(v ?? '') })"
            />
          </UiField>
          <UiField
            v-else-if="targetKind(script.trigger) === 'topic'"
            label="Conversation topic id"
            hint="The id of an NPC conversation topic; empty = any topic."
          >
            <UiInput
              :model-value="script.target_id || ''"
              mono
              placeholder="e.g. cellar_door"
              @update:model-value="(v) => updateScript(index, { target_id: String(v ?? '') })"
            />
          </UiField>
          <UiField
            v-else-if="targetKind(script.trigger)"
            :label="targetKind(script.trigger) === 'scene' ? 'Target scene' : 'Target item or character'"
          >
            <UiSelect
              :model-value="script.target_id || ''"
              :options="targetSelectOptions(script.trigger)"
              @update:model-value="(v) => updateScript(index, { target_id: String(v ?? '') })"
            />
          </UiField>
        </div>

        <ScriptEditor
          :model-value="script.code || ''"
          label="Script"
          help-text="Runs on the selected trigger, but only while this chapter is the active one."
          :context="script.trigger"
          placeholder="e.g. open_bomb_dialog()"
          min-height="100px"
          @update:model-value="updateScript(index, { code: $event })"
        />
      </div>
    </article>

    <UiButton size="sm" :icon="Plus" @click="addScript">Add chapter script</UiButton>
  </div>
</template>
