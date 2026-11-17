<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import SwitchStatesEditor from '@/components/editor/SwitchStatesEditor.vue'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import { Plus } from 'lucide-vue-next'
import { Trash2 } from 'lucide-vue-next'
import { Key } from 'lucide-vue-next'
import { FileText } from 'lucide-vue-next'
import { Lock } from 'lucide-vue-next'
import { Code2 } from 'lucide-vue-next'
import { Sparkles } from 'lucide-vue-next'
import { ToggleLeft } from 'lucide-vue-next'
import { ChevronDown } from 'lucide-vue-next'
import { ChevronRight } from 'lucide-vue-next'
import { Edit3 } from 'lucide-vue-next'

const ef = useEntityFormContext()
</script>

<template>


  <!-- SWITCH: Visual Configurator -->
  <div v-if="['SWITCH', 'CONTAINER_SWITCH'].includes(ef.currentItemType)" class="space-y-6">
    <!-- Section Header -->
    <div class="flex items-center gap-2 pb-2 border-b border-white/5">
      <ToggleLeft class="w-4 h-4 text-lime-400" />
      <span class="text-xs font-black text-white uppercase tracking-wider">Switch Configurator</span>
    </div>

    <!-- 1. States Management -->
    <SwitchStatesEditor
      v-model:labels="ef.switchStateLabels"
      v-model:disabled-states="ef.switchDisabledStates"
      :states="ef.switchStates"
      @add="ef.addState"
      @remove="ef.removeState"
      @rename="ef.updateStateValue"
    />

    <!-- 2. Initial State Selection & Status Text -->
    <div class="space-y-4 bg-black/20 border border-white/5 p-4 rounded-2xl">
      <div class="space-y-2">
        <label class="block text-xs font-black text-slate-400 uppercase tracking-widest">Initial State</label>
        <select
          v-model="ef.localForm.switch_initial_state"
          class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold uppercase tracking-widest focus:border-lime-500/50 outline-none transition-all"
        >
          <option v-for="state in ef.switchStates" :key="state" :value="state">{{ ef.switchStateLabels[state] ? `${state} (${ef.switchStateLabels[state]})` : state }}</option>
        </select>
      </div>
      <div class="space-y-1.5">
        <label class="block text-xs font-black text-slate-400 uppercase tracking-widest">Status / Hint Text (Optional)</label>
        <input
          v-model="ef.localForm.switch_status_text"
          type="text"
          maxlength="300"
          placeholder="e.g. The microwave needs some electrical power first."
          class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-xs text-white focus:border-lime-500/50 outline-none transition-all"
        />
        <span class="block text-[10px] text-slate-500 leading-normal">
          Shown inside the switch or container-switch dialog (can be updated or cleared via script: <code class="text-slate-400">obj.set_status_text(...)</code> / <code class="text-slate-400">obj.clear_status_text()</code>).
        </span>
      </div>
    </div>

    <!-- 3. Transitions Management -->
    <div class="space-y-3 bg-black/20 border border-white/5 p-4 rounded-2xl">
      <div class="flex justify-between items-center">
        <div class="flex items-center gap-2">
          <label class="block text-xs font-black text-slate-400 uppercase tracking-widest">Transitions & Rules</label>
          <span class="px-2 py-0.5 rounded-full bg-lime-500/10 text-lime-400 text-[10px] font-mono font-bold border border-lime-500/20">
            {{ ef.switchTransitions.length }}
          </span>
        </div>
        <button
          type="button"
          @click="ef.startAddTransition"
          class="px-3 py-1.5 bg-lime-500/10 border border-lime-500/30 hover:bg-lime-500/20 rounded-xl text-[10px] font-black text-lime-400 uppercase tracking-widest flex items-center gap-1.5 transition-all shadow-sm"
        >
          <Plus class="w-3.5 h-3.5" /> Add Transition
        </button>
      </div>

      <!-- Transitions List -->
      <div class="space-y-2.5">
        <div
          v-for="(t, idx) in ef.switchTransitions"
          :key="idx"
          :class="[
            'p-3 rounded-xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3',
            ef.editingTransitionIndex === idx
              ? 'bg-lime-500/10 border-lime-500/40 shadow-md ring-1 ring-lime-500/30'
              : 'bg-black/30 border-white/5 hover:border-white/10 hover:bg-black/40'
          ]"
        >
          <!-- Route & Badges -->
          <div class="flex flex-wrap items-center gap-2 min-w-0">
            <span class="text-[10px] font-mono font-bold text-slate-500">#{{ idx + 1 }}</span>
            
            <div class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900 border border-white/10 text-xs font-mono font-bold text-white">
              <span :class="t.from ? 'text-amber-300' : 'text-slate-400'">{{ t.from || 'ANY' }}</span>
              <span class="text-lime-400">→</span>
              <span class="text-emerald-300">{{ t.to || '?' }}</span>
            </div>

            <span v-if="t.gates?.item" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/20 text-[10px] font-mono text-amber-400">
              <Key class="w-2.5 h-2.5" /> {{ t.gates.item }}
            </span>
            <span v-if="t.gates?.code" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-cyan-500/10 border border-cyan-500/20 text-[10px] font-mono text-cyan-400">
              <Lock class="w-2.5 h-2.5" /> PIN: {{ t.gates.code }}
            </span>
            <span v-if="t.gates?.rule" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-violet-500/10 border border-violet-500/20 text-[10px] font-mono text-violet-400">
              <FileText class="w-2.5 h-2.5" /> {{ t.gates.rule }}
            </span>
            <span v-if="t.gates?.expression" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-teal-500/10 border border-teal-500/20 text-[10px] font-mono text-teal-300" title="Script Guard">
              <Code2 class="w-2.5 h-2.5" /> Guard
            </span>
            <span v-if="ef.hasActiveScripts(t)" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-indigo-500/10 border border-indigo-500/20 text-[10px] font-mono text-indigo-300">
              <Sparkles class="w-2.5 h-2.5" /> Scripts
            </span>
            <span v-if="t.fail_message || t.success_message" class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-slate-800 border border-white/5 text-[10px] text-slate-400" title="Custom message attached">
              Msg
            </span>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-1.5 shrink-0 ml-auto">
            <button
              type="button"
              @click="ef.toggleEditTransition(idx)"
              :class="[
                'px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 transition-all',
                ef.editingTransitionIndex === idx
                  ? 'bg-lime-500 text-slate-950 font-black shadow-sm'
                  : 'bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white border border-white/5'
              ]"
            >
              <Edit3 class="w-3.5 h-3.5" />
              <span>{{ ef.editingTransitionIndex === idx ? 'Editing' : 'Edit' }}</span>
            </button>
            <button
              type="button"
              @click="ef.removeTransition(idx)"
              class="p-1.5 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 hover:border-red-500/30 transition-all"
              title="Delete Transition"
            >
              <Trash2 class="w-4 h-4" />
            </button>
          </div>
        </div>

        <div v-if="ef.switchTransitions.length === 0" class="text-xs text-slate-500 italic py-3 text-center bg-black/20 rounded-xl border border-white/5">
          No transitions configured. Any state can be activated freely.
        </div>
      </div>

      <!-- Input / Editing Panel (Visible when editing or creating a transition) -->
      <div
        v-if="ef.editingTransitionIndex !== null && ef.switchTransitions[ef.editingTransitionIndex]"
        class="mt-4 p-4 bg-black/40 border border-lime-500/30 rounded-2xl space-y-4 shadow-xl"
      >
        <!-- Panel Header -->
        <div class="flex items-center justify-between pb-3 border-b border-white/10">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-lime-400 animate-pulse"></span>
            <h4 class="text-xs font-black text-lime-400 uppercase tracking-widest">
              Editing Transition #{{ ef.editingTransitionIndex + 1 }}
              <span v-if="ef.switchTransitions[ef.editingTransitionIndex].from || ef.switchTransitions[ef.editingTransitionIndex].to" class="text-white/70 font-mono font-normal ml-1">
                ({{ ef.switchTransitions[ef.editingTransitionIndex].from || 'ANY' }} → {{ ef.switchTransitions[ef.editingTransitionIndex].to || '?' }})
              </span>
            </h4>
          </div>
          <button
            type="button"
            @click="ef.editingTransitionIndex = null"
            class="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-[10px] font-bold text-slate-300 uppercase tracking-wider transition-all"
          >
            Close Editor
          </button>
        </div>

        <!-- From / To States -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">From State (optional)</span>
            <select
              v-model="ef.switchTransitions[ef.editingTransitionIndex].from"
              class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white font-bold uppercase focus:border-lime-500 outline-none"
            >
              <option value="">ANY (Matches all states)</option>
              <option v-for="state in ef.switchStates" :key="state" :value="state">{{ state }}</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">To State <span class="text-red-400">*</span></span>
            <select
              v-model="ef.switchTransitions[ef.editingTransitionIndex].to"
              class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white font-bold uppercase focus:border-lime-500 outline-none"
            >
              <option v-for="state in ef.switchStates" :key="state" :value="state">{{ state }}</option>
            </select>
          </div>
        </div>

        <!-- Messages Grid -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Failure Message</span>
            <input
              v-model="ef.switchTransitions[ef.editingTransitionIndex].fail_message"
              placeholder="e.g. The lever refuses to budge. It seems locked."
              class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-red-500/50 outline-none transition-all"
            />
          </div>
          <div class="space-y-1.5">
            <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Success Message (Optional)</span>
            <input
              v-model="ef.switchTransitions[ef.editingTransitionIndex].success_message"
              placeholder="e.g. The mechanism clicks smoothly into place."
              class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-lime-500/50 outline-none transition-all"
            />
          </div>
        </div>

        <!-- Collapsible Panel 1: Requirements & Guards (Default Collapsed) -->
        <div class="border border-white/10 rounded-xl overflow-hidden bg-black/30">
          <button
            type="button"
            @click="ef.showTransitionGuards = !ef.showTransitionGuards"
            class="w-full px-4 py-2.5 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
          >
            <div class="flex items-center gap-2">
              <Lock class="w-3.5 h-3.5 text-lime-400" />
              <span class="text-[11px] font-black text-slate-300 uppercase tracking-wider">
                Requirements & Guards
              </span>
              <span v-if="ef.hasActiveGuards(ef.switchTransitions[ef.editingTransitionIndex])" class="px-2 py-0.5 rounded-full bg-lime-500/20 text-lime-400 text-[9px] font-bold">
                Configured
              </span>
            </div>
            <component :is="ef.showTransitionGuards ? ChevronDown : ChevronRight" class="w-4 h-4 text-slate-400" />
          </button>

          <div v-if="ef.showTransitionGuards" class="p-4 border-t border-white/5 space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <!-- Required Key Item -->
              <div class="space-y-1.5">
                <span class="text-[9px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1">
                  <Key class="w-3 h-3 text-amber-500" /> Required Key Item
                </span>
                <EntityReferenceCombobox
                  v-model="ef.switchTransitions[ef.editingTransitionIndex].gates.item"
                  :options="ef.keyItemReferenceOptions"
                  placeholder="None"
                  :enable-search="true"
                />
              </div>

              <!-- Required Code / PIN -->
              <div class="space-y-1.5">
                <span class="text-[9px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1">
                  <Lock class="w-3 h-3 text-cyan-500" /> Required Code / PIN
                </span>
                <input
                  v-model="ef.switchTransitions[ef.editingTransitionIndex].gates.code"
                  placeholder="None"
                  class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white font-mono focus:border-cyan-500/50 outline-none"
                />
              </div>
            </div>

            <!-- Required Story Flag -->
            <div class="space-y-1.5">
              <span class="text-[9px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1">
                <FileText class="w-3 h-3 text-violet-500" /> Required Story Flag (Rule Key)
              </span>
              <input
                v-model="ef.switchTransitions[ef.editingTransitionIndex].gates.rule"
                placeholder="None"
                class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-violet-500/50 outline-none"
              />
            </div>

            <!-- Deterministic Script Guard (Python Boolean Expression) -->
            <div class="space-y-2">
              <ScriptEditor
                v-model="ef.switchTransitions[ef.editingTransitionIndex].gates.expression"
                label="Deterministic Script Guard (Python Boolean Expression)"
                help-text="Evaluated via sandboxed Python engine. Allows transition only when expression evaluates to True."
                context="guard_expression"
                placeholder="e.g. tw.vars.get('microwave_safe') and tw.vars.get('sink_fixed')"
                min-height="90px"
              />
              <p class="text-[9px] text-slate-400">
                Evaluated via sandboxed Python engine. Allows transition only when expression evaluates to True. Examples: <code class="text-cyan-300">tw.vars.get('flag') == True</code>, <code class="text-cyan-300">tw.player.hp > 50</code>.
              </p>
            </div>
          </div>
        </div>

        <!-- Collapsible Panel 2: Transition-Specific Scripts (Default Collapsed) -->
        <div class="border border-white/10 rounded-xl overflow-hidden bg-black/30">
          <button
            type="button"
            @click="ef.showTransitionScripts = !ef.showTransitionScripts"
            class="w-full px-4 py-2.5 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
          >
            <div class="flex items-center gap-2">
              <Code2 class="w-3.5 h-3.5 text-cyan-400" />
              <span class="text-[11px] font-black text-slate-300 uppercase tracking-wider">
                Transition-Specific Scripts
              </span>
              <span v-if="ef.hasActiveScripts(ef.switchTransitions[ef.editingTransitionIndex])" class="px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-400 text-[9px] font-bold">
                Configured
              </span>
            </div>
            <component :is="ef.showTransitionScripts ? ChevronDown : ChevronRight" class="w-4 h-4 text-slate-400" />
          </button>

          <div v-if="ef.showTransitionScripts" class="p-4 border-t border-white/5 space-y-4">
            <ScriptEditor
              v-model="ef.switchTransitions[ef.editingTransitionIndex].on_success_script"
              label="Transition On Success Script"
              help-text="Executed only when this specific transition succeeds."
              context="transition_success"
              min-height="90px"
            />
            <ScriptEditor
              v-model="ef.switchTransitions[ef.editingTransitionIndex].on_failure_script"
              label="Transition On Failure Script"
              help-text="Executed only when this specific transition fails."
              context="transition_failure"
              min-height="90px"
            />
          </div>
        </div>

        <!-- Close Editor Button -->
        <div class="flex justify-end pt-1">
          <button
            type="button"
            @click="ef.editingTransitionIndex = null"
            class="px-4 py-2 bg-lime-500/10 border border-lime-500/30 hover:bg-lime-500/20 text-lime-400 rounded-xl text-xs font-bold uppercase tracking-wider transition-all"
          >
            Done Editing Transition
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
