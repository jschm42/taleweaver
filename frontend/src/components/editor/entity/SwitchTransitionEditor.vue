<script setup lang="ts">
import { computed } from 'vue'
import { X } from 'lucide-vue-next'
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiDisclosure from '@/components/ui/UiDisclosure.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

/** Edit panel of the switch transition selected in the list (ef.editingTransitionIndex). */
const ef = useEntityFormContext()

const transition = computed(() =>
  ef.editingTransitionIndex !== null ? ef.switchTransitions[ef.editingTransitionIndex] : null,
)
const stateOptions = computed(() => ef.switchStates.map((state: string) => ({ value: state, label: state })))
const fromOptions = computed(() => [{ value: '', label: 'Any state' }, ...stateOptions.value])
</script>

<template>
  <div v-if="transition" class="space-y-4 rounded-xl border border-wb-accent/40 bg-wb-raised/40 p-4">
    <div class="flex items-center justify-between gap-3">
      <h4 class="wb-subheading">
        Transition {{ (ef.editingTransitionIndex ?? 0) + 1 }}
        <span v-if="transition.from || transition.to" class="wb-mono text-wb-muted">
          ({{ transition.from || 'any' }} → {{ transition.to || '?' }})
        </span>
      </h4>
      <UiIconButton :icon="X" label="Close the transition editor" size="sm" @click="ef.editingTransitionIndex = null" />
    </div>

    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <UiField label="From state">
        <UiSelect v-model="transition.from" :options="fromOptions" />
      </UiField>
      <UiField label="To state" required>
        <UiSelect v-model="transition.to" :options="stateOptions" />
      </UiField>
      <UiField label="Failure message">
        <UiInput v-model="transition.fail_message" placeholder="e.g. The lever refuses to budge. It seems locked." />
      </UiField>
      <UiField label="Success message" hint="Optional.">
        <UiInput v-model="transition.success_message" placeholder="e.g. The mechanism clicks smoothly into place." />
      </UiField>
    </div>

    <!-- Contents are created only when opened: the script editor measures itself on creation. -->
    <UiDisclosure
      v-model:open="ef.showTransitionGuards"
      label="Requirements"
      :hint="ef.hasActiveGuards(transition) ? 'configured' : 'key item, code, story flag, guard'"
    >
      <div v-if="ef.showTransitionGuards" class="space-y-4">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <UiField label="Key item">
            <EntityReferenceCombobox
              v-model="transition.gates.item"
              :options="ef.keyItemReferenceOptions"
              placeholder="None"
              :enable-search="true"
            />
          </UiField>
          <UiField label="Code">
            <UiInput v-model="transition.gates.code" placeholder="None" class="wb-mono" />
          </UiField>
        </div>
        <UiField label="Story flag" hint="Rule key that must be set.">
          <UiInput v-model="transition.gates.rule" placeholder="None" class="wb-mono" />
        </UiField>
        <ScriptEditor
          v-model="transition.gates.expression"
          label="Guard expression"
          help-text="Python boolean expression; the transition is allowed only when it is true, e.g. tw.vars.get('flag') == True or tw.player.hp > 50."
          context="guard_expression"
          placeholder="e.g. tw.vars.get('microwave_safe') and tw.vars.get('sink_fixed')"
          min-height="90px"
        />
      </div>
    </UiDisclosure>

    <UiDisclosure
      v-model:open="ef.showTransitionScripts"
      label="Transition scripts"
      :hint="ef.hasActiveScripts(transition) ? 'configured' : 'optional'"
    >
      <div v-if="ef.showTransitionScripts" class="space-y-4">
        <ScriptEditor
          v-model="transition.on_success_script"
          label="On success script"
          help-text="Runs only when this transition succeeds."
          context="transition_success"
          min-height="90px"
        />
        <ScriptEditor
          v-model="transition.on_failure_script"
          label="On failure script"
          help-text="Runs only when this transition fails."
          context="transition_failure"
          min-height="90px"
        />
      </div>
    </UiDisclosure>

    <div class="flex justify-end">
      <UiButton size="sm" @click="ef.editingTransitionIndex = null">Done</UiButton>
    </div>
  </div>
</template>
