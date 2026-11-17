<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import RecipeEditorPanel from '@/components/editor/RecipeEditorPanel.vue'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import { Lock } from 'lucide-vue-next'
import { Sparkles } from 'lucide-vue-next'
import { ChevronDown } from 'lucide-vue-next'
import { ChevronRight } from 'lucide-vue-next'

const ef = useEntityFormContext()
</script>

<template>

  <!-- CONSTRUCTABLE: Recipe (ingredients, kept ingredients, results) -->
  <RecipeEditorPanel
    v-if="ef.currentItemType === 'CONSTRUCTABLE'"
    v-model:ingredients="ef.localForm.combination_ingredients_input"
    v-model:results="ef.localForm.result_item_ids_input"
    v-model:kept="ef.localForm.kept_ingredients_input"
    :ingredient-options="ef.recipeIngredientOptions"
    :result-options="ef.recipeResultOptions"
    :recipe-id="ef.currentEntityId || String(ef.entityId || '')"
  />

  <!-- CONSTRUCTABLE Panels: Deterministic Guard & Transition Rules -->
  <div v-if="ef.currentItemType === 'CONSTRUCTABLE'" class="space-y-4 pt-2">
    <!-- Collapsible Panel 1: Script Guard (Default Collapsed) -->
    <div class="border border-white/10 rounded-xl overflow-hidden bg-black/30">
      <button
        type="button"
        @click="ef.showConstructableGuard = !ef.showConstructableGuard"
        class="w-full px-4 py-2.5 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
      >
        <div class="flex items-center gap-2">
          <Lock class="w-3.5 h-3.5 text-orange-400" />
          <span class="text-[11px] font-black text-slate-300 uppercase tracking-wider">
            Crafting Script Guard
          </span>
          <span v-if="ef.localForm.craft_guard_expression" class="px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-400 text-[9px] font-bold">
            Configured
          </span>
        </div>
        <component :is="ef.showConstructableGuard ? ChevronDown : ChevronRight" class="w-4 h-4 text-slate-400" />
      </button>

      <div v-if="ef.showConstructableGuard" class="p-4 border-t border-white/5 space-y-2">
        <ScriptEditor
          v-model="ef.localForm.craft_guard_expression"
          label="Deterministic Script Guard Expression"
          help-text="Optional Python boolean expression evaluated in addition to required items. If false, crafting fails."
          context="guard_expression"
          placeholder="e.g. tw.vars.get('has_hammer') == True or tw.switches.get('FORGE') == 'ON'"
          min-height="90px"
        />
        <p class="text-[10px] text-slate-400">
          Optional Python boolean expression evaluated in addition to required items. If false, crafting fails.
        </p>
      </div>
    </div>

    <!-- Collapsible Panel 2: Crafting Transition Rules (Default Collapsed) -->
    <div class="border border-white/10 rounded-xl overflow-hidden bg-black/30">
      <button
        type="button"
        @click="ef.showConstructableTriggers = !ef.showConstructableTriggers"
        class="w-full px-4 py-2.5 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
      >
        <div class="flex items-center gap-2">
          <Sparkles class="w-3.5 h-3.5 text-amber-400" />
          <span class="text-[11px] font-black text-slate-300 uppercase tracking-wider">
            Crafting Transition Rules
          </span>
          <span v-if="ef.localForm.on_craft_success_script || ef.localForm.on_craft_failure_script" class="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 text-[9px] font-bold">
            Configured
          </span>
        </div>
        <component :is="ef.showConstructableTriggers ? ChevronDown : ChevronRight" class="w-4 h-4 text-slate-400" />
      </button>

      <div v-if="ef.showConstructableTriggers" class="p-4 border-t border-white/5 space-y-4">
        <ScriptEditor
          v-model="ef.localForm.on_craft_success_script"
          label="On Craft Success Script"
          help-text="Executed when this constructable item is successfully crafted."
          context="constructable_success"
          min-height="100px"
        />
        <div class="space-y-1">
          <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Craft Success Text</label>
          <textarea
            v-model="ef.localForm.on_craft_success_text"
            rows="2"
            placeholder="e.g. With careful precision, you forge the ingredients into a masterwork."
            class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-amber-500/50 outline-none"
          ></textarea>
        </div>

        <ScriptEditor
          v-model="ef.localForm.on_craft_failure_script"
          label="On Craft Failure Script"
          help-text="Executed when crafting this item fails or is blocked by guard."
          context="constructable_failure"
          min-height="100px"
        />
        <div class="space-y-1">
          <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Craft Failure Text</label>
          <textarea
            v-model="ef.localForm.on_craft_failure_text"
            rows="2"
            placeholder="e.g. The forge is too cold to fuse the metal together."
            class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-amber-500/50 outline-none"
          ></textarea>
        </div>
      </div>
    </div>
  </div>
</template>
