<script setup lang="ts">
import { computed } from 'vue'
import { useEditor } from '@/composables/editor/editorContext'
import { formFieldError } from '@/composables/editor/useEditorFormDraft'
import DefeatRuleSettings from '@/components/editor/DefeatRuleSettings.vue'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import FormTextField from '@/components/editor/overview/FormTextField.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

/** Win and loss conditions: a soft rule the Game Master judges and/or a guard the engine checks. */
const editor = useEditor()
const form = computed(() => editor.form as Record<string, unknown>)

const OUTCOMES = [
  {
    key: 'win',
    title: 'Victory',
    soft: 'completed_condition',
    guard: 'completed_guard_expression',
    softHint: 'Judged by the Game Master. Empty in RPG mode: all main quests done.',
    guardLabel: 'Win guard (Python expression)',
    guardHelp: 'Deterministic condition the engine checks; it must be True for victory.',
    guardPlaceholder: "e.g. tw.vars.get('boss_defeated') == True and tw.player.has_item('MOB_LEDGER')",
  },
  {
    key: 'loss',
    title: 'Defeat',
    soft: 'gameover_condition',
    guard: 'gameover_guard_expression',
    softHint: 'Judged by the Game Master. Empty in RPG mode: the protagonist falls to 0 HP.',
    guardLabel: 'Loss guard (Python expression)',
    guardHelp: 'Deterministic condition the engine checks; when True, the adventure is lost.',
    guardPlaceholder: "e.g. tw.vars.get('alarm_raised') == True",
  },
] as const

function text(field: string): string {
  return String(form.value[field] ?? '')
}

function hasBoth(soft: string, guard: string): boolean {
  return Boolean(text(soft).trim() && text(guard).trim())
}
</script>

<template>
  <UiCard title="Outcome" description="Use either a soft rule or a guard per outcome, not both.">
    <div class="grid gap-8 xl:grid-cols-2">
      <section v-for="outcome in OUTCOMES" :key="outcome.key" class="min-w-0 space-y-4">
        <h3 class="wb-subheading">{{ outcome.title }}</h3>
        <FormTextField
          :field="outcome.soft"
          label="Soft rule"
          :hint="outcome.softHint"
          placeholder="Describe the outcome in prose..."
          generatable
        />
        <div class="space-y-1">
          <ScriptEditor
            :model-value="text(outcome.guard)"
            :label="outcome.guardLabel"
            :help-text="outcome.guardHelp"
            context="guard_expression"
            :placeholder="outcome.guardPlaceholder"
            min-height="80px"
            @update:model-value="(v: string) => (form[outcome.guard] = v)"
          />
          <p v-if="formFieldError(form, outcome.guard)" class="wb-hint !text-wb-danger-text" role="alert">
            {{ formFieldError(form, outcome.guard) }}
          </p>
        </div>
        <UiNotice v-if="hasBoth(outcome.soft, outcome.guard)" tone="warn">
          Both a soft rule and a guard are set. Keep one of them so the outcome stays predictable.
        </UiNotice>
        <DefeatRuleSettings v-if="outcome.key === 'loss'" v-model="editor.form.game_over_rules" />
      </section>
    </div>
  </UiCard>
</template>
