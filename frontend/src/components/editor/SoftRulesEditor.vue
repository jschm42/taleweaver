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
import { Plus, Trash2, ChevronDown, ChevronUp, MessageSquareQuote } from 'lucide-vue-next'

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
    <div class="space-y-1">
      <p class="text-xs font-black text-amber-400 uppercase tracking-widest flex items-center gap-2">
        <MessageSquareQuote class="w-4 h-4" /> Soft Rules
      </p>
      <p class="text-[11px] text-slate-400">
        Narrative rules that are only active during this sequence. The GM judges whether the condition
        happened; the engine then checks the optional guard and trigger limit and runs the script.
        The GM never sees the script or guard.
      </p>
    </div>

    <p v-if="rules.length === 0" class="text-[11px] text-slate-500 italic">
      No soft rules yet. Example: "Arthur flirts with Brenda" → Brenda hands over her key.
    </p>

    <div
      v-for="(rule, index) in rules"
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
          <span class="text-[10px] font-mono text-amber-300 shrink-0">{{ rule.id || '(no id)' }}</span>
          <span class="text-xs text-slate-300 truncate">{{ rule.condition || 'No condition yet' }}</span>
        </button>
        <span v-if="rule.max_triggers" class="shrink-0 text-[10px] text-slate-500">max {{ rule.max_triggers }}×</span>
        <button
          type="button"
          class="shrink-0 p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
          title="Remove soft rule"
          @click="removeRule(index)"
        >
          <Trash2 class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- Body -->
      <div v-if="expandedIndex === index" class="space-y-4 px-4 pb-4 border-t border-white/5 pt-4">
        <div class="grid grid-cols-1 sm:grid-cols-[1fr_140px] gap-3">
          <div class="space-y-1">
            <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">Rule ID</label>
            <EditorIdInput
              :model-value="rule.id"
              :prefix="EDITOR_ID_PREFIXES.RULE"
              :source-name="rule.condition"
              :taken-ids="rules.filter((_, i) => i !== index).map((r) => String(r.id || ''))"
              :max-length="MAX_EDITOR_ID_LENGTH"
              :compact="true"
              :required="true"
              placeholder="RULE_FLIRT_KEY"
              aria-label="Rule ID"
              @update:model-value="(val) => updateId(index, val)"
            />
          </div>
          <div class="space-y-1">
            <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">Max Triggers</label>
            <input
              :value="rule.max_triggers ?? ''"
              type="number"
              min="1"
              placeholder="Unlimited"
              class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-amber-500/50 outline-none"
              @input="updateMaxTriggers(index, ($event.target as HTMLInputElement).value)"
            />
          </div>
        </div>

        <div class="space-y-1">
          <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">Condition (judged by the GM)</label>
          <textarea
            :value="rule.condition"
            rows="2"
            placeholder="e.g. Arthur flirts with Brenda"
            class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-amber-500/50 outline-none resize-y"
            @input="updateRule(index, { condition: ($event.target as HTMLTextAreaElement).value })"
          ></textarea>
        </div>

        <ScriptEditor
          :model-value="rule.guard_expression || ''"
          label="Guard Expression (optional precondition)"
          help-text="Deterministic Python condition that must also hold. The guard can only block the rule, never trigger it."
          context="guard_expression"
          placeholder="e.g. tw.vars.get('BRENDA_TRUST', 0) >= 0"
          min-height="60px"
          @update:model-value="updateRule(index, { guard_expression: $event })"
        />

        <ScriptEditor
          :model-value="rule.script || ''"
          label="Script (runs when the rule fires)"
          help-text="Executed by the engine once the GM reports the condition and the guard passes."
          context="soft_rule"
          placeholder="e.g. tw.npcs.give_to_player('BRENDA', 'BRENDA_KEY')"
          min-height="100px"
          @update:model-value="updateRule(index, { script: $event })"
        />

        <div class="space-y-1">
          <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">Text (optional)</label>
          <textarea
            :value="rule.text || ''"
            rows="2"
            placeholder="e.g. Brenda's expression cools noticeably."
            class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-amber-500/50 outline-none resize-y"
            @input="updateRule(index, { text: ($event.target as HTMLTextAreaElement).value })"
          ></textarea>
        </div>
      </div>
    </div>

    <button
      type="button"
      class="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-dashed border-white/15 text-xs font-bold uppercase tracking-wider text-slate-400 hover:text-amber-300 hover:border-amber-500/40 transition-colors"
      @click="addRule"
    >
      <Plus class="w-4 h-4" /> Add Soft Rule
    </button>
  </div>
</template>
