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
import TriggerScriptField from '@/components/editor/entity/TriggerScriptField.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

export interface SoftRule {
  id: string
  condition: string
  script?: string
  text?: string
  guard_expression?: string
  max_triggers?: number | null
}

const props = withDefaults(defineProps<{ modelValue?: SoftRule[] }>(), {
  modelValue: () => [],
})

const emit = defineEmits<{
  (e: 'update:modelValue', rules: SoftRule[]): void
}>()

const rules = computed<SoftRule[]>(() => (Array.isArray(props.modelValue) ? props.modelValue : []))
const expandedIndex = ref<number | null>(null)

function updateRule(index: number, patch: Partial<SoftRule>) {
  emit(
    'update:modelValue',
    rules.value.map((rule, i) => (i === index ? { ...rule, ...patch } : rule))
  )
}

function updateId(index: number, raw: string) {
  updateRule(index, { id: sanitizeEditorId(raw, MAX_EDITOR_ID_LENGTH) })
}

function updateMaxTriggers(index: number, raw: string) {
  const parsed = parseInt(raw, 10)
  updateRule(index, { max_triggers: Number.isFinite(parsed) && parsed > 0 ? parsed : null })
}

function addRule() {
  const rule: SoftRule = {
    id: generateEditorId({
      prefix: EDITOR_ID_PREFIXES.RULE,
      takenIds: rules.value.map((r) => String(r.id || '')),
      maxLen: MAX_EDITOR_ID_LENGTH,
    }),
    condition: '',
    script: '',
    text: '',
    guard_expression: '',
    max_triggers: null,
  }
  emit('update:modelValue', [...rules.value, rule])
  expandedIndex.value = rules.value.length
}

function removeRule(index: number) {
  emit('update:modelValue', rules.value.filter((_, i) => i !== index))
  expandedIndex.value = null
}

function toggle(index: number) {
  expandedIndex.value = expandedIndex.value === index ? null : index
}
</script>

<template>
  <div class="space-y-4">
    <p class="wb-hint">
      Narrative rules that are only active during this chapter. The Game Master judges whether the condition happened;
      the engine then checks the optional guard and trigger limit and runs the script. The Game Master never sees the
      script or the guard.
    </p>

    <UiEmptyState
      v-if="rules.length === 0"
      title="No soft rules yet"
      description="Example: &quot;Arthur flirts with Brenda&quot; makes Brenda hand over her key."
    />

    <article v-for="(rule, index) in rules" :key="index" class="rounded-xl border border-wb-line bg-wb-raised">
      <div class="flex items-center gap-2 px-3 py-2">
        <button
          type="button"
          class="flex min-w-0 flex-1 items-center gap-2 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
          :aria-expanded="expandedIndex === index"
          @click="toggle(index)"
        >
          <component :is="expandedIndex === index ? ChevronDown : ChevronRight" class="h-4 w-4 shrink-0 text-wb-muted" />
          <span class="wb-mono shrink-0 text-wb-strong">{{ rule.id || '(no ID)' }}</span>
          <span class="wb-body truncate text-wb-muted">{{ rule.condition || 'No condition yet' }}</span>
        </button>
        <UiBadge v-if="rule.max_triggers">max {{ rule.max_triggers }}×</UiBadge>
        <UiIconButton :icon="Trash2" label="Remove soft rule" size="sm" variant="danger" @click="removeRule(index)" />
      </div>

      <div v-if="expandedIndex === index" class="space-y-4 border-t border-wb-line p-4">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,1fr)_140px]">
          <UiField label="Rule ID" required>
            <EditorIdInput
              :model-value="rule.id"
              :prefix="EDITOR_ID_PREFIXES.RULE"
              :source-name="rule.condition"
              :taken-ids="rules.filter((_, i) => i !== index).map((r) => String(r.id || ''))"
              :max-length="MAX_EDITOR_ID_LENGTH"
              :required="true"
              placeholder="RULE_FLIRT_KEY"
              aria-label="Rule ID"
              @update:model-value="(val) => updateId(index, val)"
            />
          </UiField>
          <UiField label="Max triggers">
            <UiInput
              type="number"
              min="1"
              placeholder="Unlimited"
              :model-value="rule.max_triggers ?? null"
              @update:model-value="(v) => updateMaxTriggers(index, String(v ?? ''))"
            />
          </UiField>
        </div>

        <UiField label="Condition" hint="Judged by the Game Master.">
          <UiTextarea
            :model-value="rule.condition"
            :rows="2"
            placeholder="e.g. Arthur flirts with Brenda"
            @update:model-value="(v) => updateRule(index, { condition: v })"
          />
        </UiField>

        <ScriptEditor
          :model-value="rule.guard_expression || ''"
          label="Guard expression (optional precondition)"
          help-text="Deterministic Python condition that must also hold. The guard can only block the rule, never trigger it."
          context="guard_expression"
          placeholder="e.g. tw.vars.get('BRENDA_TRUST', 0) >= 0"
          min-height="60px"
          @update:model-value="updateRule(index, { guard_expression: $event })"
        />

        <TriggerScriptField
          :script="rule.script || ''"
          :text="rule.text || ''"
          label="When it fires"
          help="Runs once the Game Master reports the condition and the guard passes."
          context="soft_rule"
          text-placeholder="e.g. Brenda's expression cools noticeably."
          @update:script="(v: string) => updateRule(index, { script: v })"
          @update:text="(v: string) => updateRule(index, { text: v })"
        />
      </div>
    </article>

    <UiButton size="sm" :icon="Plus" @click="addRule">Add soft rule</UiButton>
  </div>
</template>
