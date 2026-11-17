<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import { Lock } from 'lucide-vue-next'
import { Sparkles } from 'lucide-vue-next'
import { ChevronDown } from 'lucide-vue-next'
import { ChevronRight } from 'lucide-vue-next'

const ef = useEntityFormContext()
</script>

<template>

  <!-- CONTAINER -->
  <div v-if="['CONTAINER', 'CONTAINER_SWITCH'].includes(ef.currentItemType)" class="p-3 bg-black/20 border border-white/10 rounded-xl">
    <div class="flex items-center justify-between">
      <div class="space-y-1 pr-4">
        <p class="text-xs font-black text-slate-200 uppercase tracking-widest">Locked State</p>
        <p class="text-[10px] text-slate-500 uppercase tracking-tighter">If enabled, this container needs either a code or a key item.</p>
      </div>
      <button
        type="button"
        @click="ef.localForm.locked = !ef.localForm.locked"
        :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1', ef.localForm.locked ? 'bg-emerald-600' : 'bg-slate-700']"
      >
        <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', ef.localForm.locked ? 'translate-x-6' : 'translate-x-0']"></div>
      </button>
    </div>
  </div>

  <div v-if="['CONTAINER', 'CONTAINER_SWITCH'].includes(ef.currentItemType)" class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <div class="space-y-2">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Code To Unlock</label>
      <input
        v-model="ef.localForm.code_to_unlock"
        maxlength="20"
        class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white focus:border-amber-500/50 outline-none transition-all"
        placeholder="ALPHA or 4711"
      />
    </div>
    <div class="space-y-2">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Item ID To Unlock</label>
      <EntityReferenceCombobox
        v-model="ef.localForm.item_to_unlock"
        :options="ef.keyItemReferenceOptions"
        placeholder="Select item reference"
        :enable-search="true"
      />
    </div>
  </div>

  <div v-if="['CONTAINER', 'CONTAINER_SWITCH'].includes(ef.currentItemType)" class="space-y-4">
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div class="space-y-2">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Min Items Required</label>
        <input
          v-model.number="ef.localForm.min_items"
          type="number"
          min="0"
          max="50"
          placeholder="0 (No minimum)"
          class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white focus:border-amber-500/50 outline-none transition-all"
        />
        <span class="block text-[10px] text-slate-500 leading-normal">
          Minimum items needed inside (e.g. 3 for a fuse box requiring 3 components).
        </span>
      </div>
      <div class="space-y-2">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Max Items Capacity</label>
        <input
          v-model.number="ef.localForm.max_items"
          type="number"
          min="0"
          max="50"
          placeholder="0 (Unlimited)"
          class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white focus:border-amber-500/50 outline-none transition-all"
        />
        <span class="block text-[10px] text-slate-500 leading-normal">
          Maximum items that fit inside (e.g. 1 for a microwave or coin slot).
        </span>
      </div>
    </div>
    <p
      v-if="Number(ef.localForm.min_items || 0) > 0 && Number(ef.localForm.max_items || 0) > 0 && Number(ef.localForm.min_items) > Number(ef.localForm.max_items)"
      class="text-xs text-red-400 font-bold"
    >
      Min Items cannot be greater than Max Items Capacity.
    </p>
  </div>

  <div v-if="['CONTAINER', 'CONTAINER_SWITCH'].includes(ef.currentItemType)" class="space-y-3">
    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Contained Items</label>
    <div class="space-y-2">
      <div
        v-for="(_item, idx) in ef.localForm.inventory_input"
        :key="idx"
        class="flex items-center gap-2"
      >
        <EntityReferenceCombobox
          v-model="ef.localForm.inventory_input[idx]"
          :options="ef.containedItemReferenceOptions"
          placeholder="Select contained item"
          :enable-search="true"
        />
        <button
          type="button"
          @click="ef.localForm.inventory_input = ef.localForm.inventory_input.filter((_: string, i: number) => i !== idx)"
          class="shrink-0 px-2 py-1.5 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 text-[10px] font-bold uppercase tracking-widest transition-all"
        >
          <i class="ra ra-cancel"></i>
        </button>
      </div>
      <button
        type="button"
        @click="ef.localForm.inventory_input = [...(ef.localForm.inventory_input || []), '']"
        class="w-full py-2 bg-amber-500/5 border border-amber-500/10 hover:bg-amber-500/10 hover:border-amber-500/30 rounded-xl text-[10px] font-black text-amber-400 uppercase tracking-widest transition-all"
      >
        + Add Item
      </button>
    </div>
    <p class="text-[10px] text-slate-500 uppercase tracking-wider">Select items contained inside this container.</p>
  </div>

  <!-- CONTAINER Panels: Deterministic Guard & Unlocking Transition Rules -->
  <div v-if="['CONTAINER', 'CONTAINER_SWITCH'].includes(ef.currentItemType)" class="space-y-4 pt-2">
    <!-- Collapsible Panel 1: Deterministic Guard (Default Collapsed) -->
    <div class="border border-white/10 rounded-xl overflow-hidden bg-black/30">
      <button
        type="button"
        @click="ef.showContainerGuard = !ef.showContainerGuard"
        class="w-full px-4 py-2.5 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
      >
        <div class="flex items-center gap-2">
          <Lock class="w-3.5 h-3.5 text-amber-400" />
          <span class="text-[11px] font-black text-slate-300 uppercase tracking-wider">
            Deterministic Guard Expression
          </span>
          <span v-if="ef.localForm.unlock_expression" class="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 text-[9px] font-bold">
            Configured
          </span>
        </div>
        <component :is="ef.showContainerGuard ? ChevronDown : ChevronRight" class="w-4 h-4 text-slate-400" />
      </button>

      <div v-if="ef.showContainerGuard" class="p-4 border-t border-white/5 space-y-2">
        <ScriptEditor
          v-model="ef.localForm.unlock_expression"
          label="Deterministic Script Guard Expression"
          help-text="Deterministic Python boolean expression evaluated when attempting to unlock. If evaluated to false, unlocking fails."
          context="guard_expression"
          placeholder="e.g. tw.vars.get('has_badge') == True or tw.switches.get('CHEST_LOCK') == 'OPEN'"
          min-height="90px"
        />
        <p class="text-[10px] text-slate-400">
          Deterministic Python boolean expression evaluated when attempting to unlock. If evaluated to false, unlocking fails.
        </p>
      </div>
    </div>

    <!-- Collapsible Panel 2: Unlocking Transition Rules (Default Collapsed) -->
    <div class="border border-white/10 rounded-xl overflow-hidden bg-black/30">
      <button
        type="button"
        @click="ef.showContainerTriggers = !ef.showContainerTriggers"
        class="w-full px-4 py-2.5 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
      >
        <div class="flex items-center gap-2">
          <Sparkles class="w-3.5 h-3.5 text-amber-400" />
          <span class="text-[11px] font-black text-slate-300 uppercase tracking-wider">
            Unlocking Transition Rules
          </span>
          <span v-if="ef.localForm.on_unlock_success_script || ef.localForm.on_unlock_failure_script || ef.localForm.on_items_added_script || ef.localForm.on_items_removed_script" class="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 text-[9px] font-bold">
            Configured
          </span>
        </div>
        <component :is="ef.showContainerTriggers ? ChevronDown : ChevronRight" class="w-4 h-4 text-slate-400" />
      </button>

      <div v-if="ef.showContainerTriggers" class="p-4 border-t border-white/5 space-y-4">
        <ScriptEditor
          v-model="ef.localForm.on_unlock_success_script"
          label="On Unlock Success Script"
          help-text="Executed immediately when this container is successfully unlocked."
          context="container_unlock_success"
          min-height="100px"
        />
        <div class="space-y-1">
          <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Unlock Success Text</label>
          <textarea
            v-model="ef.localForm.on_unlock_success_text"
            rows="2"
            placeholder="e.g. The heavy chest lid springs open with a satisfying clack."
            class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-amber-500/50 outline-none"
          ></textarea>
        </div>

        <ScriptEditor
          v-model="ef.localForm.on_unlock_failure_script"
          label="On Unlock Failure Script"
          help-text="Executed when unlocking this container fails or is blocked by guard."
          context="container_unlock_failure"
          min-height="100px"
        />
        <div class="space-y-1">
          <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Unlock Failure Text</label>
          <textarea
            v-model="ef.localForm.on_unlock_failure_text"
            rows="2"
            placeholder="e.g. A small jolt zaps your fingers! The container remains shut."
            class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-amber-500/50 outline-none"
          ></textarea>
        </div>

        <ScriptEditor
          v-model="ef.localForm.on_items_added_script"
          label="On Items Added Script"
          help-text="Executed once after the player put one or more items into this container. added_items (list of dicts) and added_item_ids (list of IDs) are in scope."
          context="container_items_added"
          min-height="100px"
        />
        <div class="space-y-1">
          <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Items Added Text</label>
          <textarea
            v-model="ef.localForm.on_items_added_text"
            rows="2"
            placeholder="e.g. The offering bowl glows faintly as the items settle inside."
            class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-amber-500/50 outline-none"
          ></textarea>
        </div>

        <ScriptEditor
          v-model="ef.localForm.on_items_removed_script"
          label="On Items Removed Script"
          help-text="Executed once after the player takes or drops one or more items from this container. removed_items (list of dicts) and removed_item_ids (list of IDs) are in scope."
          context="container_items_removed"
          min-height="100px"
        />
        <div class="space-y-1">
          <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Items Removed Text</label>
          <textarea
            v-model="ef.localForm.on_items_removed_text"
            rows="2"
            placeholder="e.g. The chamber resets as you take the item out."
            class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-amber-500/50 outline-none"
          ></textarea>
        </div>
      </div>
    </div>
  </div>
</template>
