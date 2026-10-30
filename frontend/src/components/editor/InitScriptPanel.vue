<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronDown, ChevronUp, Save, Sigma } from 'lucide-vue-next'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'

/**
 * Editor for the adventure's global init_script: runs once at session start and provides
 * shared helper functions (incl. tw.dialog on_choice handlers) to every other script.
 */
const props = defineProps<{
  initScript?: string | null
  isSaving?: boolean
}>()

const emit = defineEmits<{
  (e: 'save', initScript: string): void
}>()

const draft = ref(props.initScript || '')
const expanded = ref(Boolean(props.initScript))

watch(() => props.initScript, (value) => {
  draft.value = value || ''
})

const isDirty = computed(() => draft.value.trim() !== String(props.initScript || '').trim())
const functionCount = computed(() => (draft.value.match(/^def\s+\w+/gm) || []).length)
</script>

<template>
  <div class="bg-slate-900/60 border border-white/10 rounded-2xl backdrop-blur-md">
    <button
      type="button"
      class="w-full flex items-center gap-3 px-6 py-4 text-left"
      @click="expanded = !expanded"
    >
      <div class="w-8 h-8 rounded-lg bg-violet-500/20 border border-violet-500/40 flex items-center justify-center shrink-0">
        <Sigma class="w-4 h-4 text-violet-300" />
      </div>
      <div class="flex-1 min-w-0">
        <p class="text-sm font-black text-white flex items-center gap-2">
          Global Init Script
          <span class="text-[10px] px-2 py-0.5 rounded-full bg-violet-500/15 border border-violet-500/30 text-violet-300 font-bold">
            {{ functionCount }} {{ functionCount === 1 ? 'function' : 'functions' }}
          </span>
          <span v-if="isDirty" class="text-[10px] text-amber-300 font-bold">unsaved</span>
        </p>
        <p class="text-[11px] text-slate-400">
          Runs once when a session starts. Functions defined here are available in every script,
          and choice-dialog handlers (<code>on_choice</code>) live here or in a scene's or sequence's helpers (Advanced tab).
        </p>
      </div>
      <component :is="expanded ? ChevronUp : ChevronDown" class="w-4 h-4 text-slate-500 shrink-0" />
    </button>

    <div v-if="expanded" class="px-6 pb-5 space-y-3 border-t border-white/5 pt-4">
      <ScriptEditor
        v-model="draft"
        label="init_script"
        help-text="Top-level code runs once at session start. Function definitions and constant assignments are also loaded before every other script."
        context="init_script"
        placeholder="def on_bomb_wire(answ):&#10;    if answ == 0:&#10;        tw.vars.set('bomb_disarmed', True)"
        min-height="200px"
      />
      <div class="flex items-center justify-end gap-3">
        <button
          type="button"
          :disabled="!isDirty || isSaving"
          class="px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-wider text-slate-400 hover:text-white disabled:opacity-40 transition-colors"
          @click="draft = initScript || ''"
        >
          Revert
        </button>
        <button
          type="button"
          :disabled="!isDirty || isSaving"
          class="flex items-center gap-2 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-black uppercase tracking-wider disabled:opacity-40 transition-colors"
          @click="emit('save', draft)"
        >
          <Save class="w-3.5 h-3.5" />
          Save Init Script
        </button>
      </div>
    </div>
  </div>
</template>
