<script setup lang="ts">
import { computed } from 'vue'
import { Code2, FileText, Key, Lock, Pencil, Plus, Sparkles, Trash2 } from 'lucide-vue-next'
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import SwitchStatesEditor from '@/components/editor/SwitchStatesEditor.vue'
import SwitchTransitionEditor from '@/components/editor/entity/SwitchTransitionEditor.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const ef = useEntityFormContext()

const initialStateOptions = computed(() =>
  ef.switchStates.map((state: string) => ({
    value: state,
    label: ef.switchStateLabels[state] ? `${state} (${ef.switchStateLabels[state]})` : state,
  })),
)
</script>

<template>
  <UiSection v-if="['SWITCH', 'CONTAINER_SWITCH'].includes(ef.currentItemType)" title="Switch" class="border-t border-wb-line pt-6">
    <SwitchStatesEditor
      v-model:labels="ef.switchStateLabels"
      v-model:disabled-states="ef.switchDisabledStates"
      :states="ef.switchStates"
      @add="ef.addState"
      @remove="ef.removeState"
      @rename="ef.updateStateValue"
    />

    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <UiField label="Initial state">
        <UiSelect v-model="ef.localForm.switch_initial_state" :options="initialStateOptions" />
      </UiField>
      <UiField
        label="Status text"
        info="Shown in the switch dialog. Scripts can change it with obj.set_status_text(...) or obj.clear_status_text()."
      >
        <UiInput v-model="ef.localForm.switch_status_text" maxlength="300" placeholder="e.g. The microwave needs some electrical power first." />
      </UiField>
    </div>

    <div class="space-y-3">
      <div class="flex items-center justify-between gap-3">
        <p class="wb-label flex items-center gap-2">Transitions <UiBadge>{{ ef.switchTransitions.length }}</UiBadge></p>
        <UiButton size="sm" :icon="Plus" @click="ef.startAddTransition">Add transition</UiButton>
      </div>

      <ul v-if="ef.switchTransitions.length" class="divide-y divide-wb-line rounded-xl border border-wb-line">
        <li
          v-for="(t, idx) in ef.switchTransitions"
          :key="idx"
          :class="['flex flex-wrap items-center justify-between gap-3 px-3 py-2', ef.editingTransitionIndex === idx ? 'bg-wb-accent-soft' : '']"
        >
          <div class="flex min-w-0 flex-wrap items-center gap-2">
            <span class="wb-hint tabular-nums">{{ idx + 1 }}</span>
            <span class="wb-mono text-wb-strong">{{ t.from || 'any' }} → {{ t.to || '?' }}</span>
            <UiBadge v-if="t.gates?.item" tone="warn"><Key class="h-3 w-3" aria-hidden="true" />{{ t.gates.item }}</UiBadge>
            <UiBadge v-if="t.gates?.code" tone="info"><Lock class="h-3 w-3" aria-hidden="true" />code {{ t.gates.code }}</UiBadge>
            <UiBadge v-if="t.gates?.rule"><FileText class="h-3 w-3" aria-hidden="true" />{{ t.gates.rule }}</UiBadge>
            <UiBadge v-if="t.gates?.expression"><Code2 class="h-3 w-3" aria-hidden="true" />guard</UiBadge>
            <UiBadge v-if="ef.hasActiveScripts(t)"><Sparkles class="h-3 w-3" aria-hidden="true" />scripts</UiBadge>
            <UiBadge v-if="t.fail_message || t.success_message">message</UiBadge>
          </div>
          <div class="ml-auto flex items-center gap-1">
            <UiButton
              size="sm"
              :variant="ef.editingTransitionIndex === idx ? 'primary' : 'ghost'"
              :icon="Pencil"
              @click="ef.toggleEditTransition(idx)"
            >
              {{ ef.editingTransitionIndex === idx ? 'Editing' : 'Edit' }}
            </UiButton>
            <UiIconButton :icon="Trash2" :label="`Delete transition ${idx + 1}`" variant="danger" size="sm" @click="ef.removeTransition(idx)" />
          </div>
        </li>
      </ul>
      <p v-else class="wb-hint">No transitions: every state can be set freely.</p>

      <SwitchTransitionEditor />
    </div>
  </UiSection>
</template>
