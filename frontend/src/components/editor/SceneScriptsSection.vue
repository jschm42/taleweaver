<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronDown, ChevronUp, Code2, Save } from 'lucide-vue-next'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import { entityService } from '@/services/entityService'
import { notificationService } from '@/services/notificationService'

/**
 * Scene editor section for the scene's own scripts: enter/leave triggers (script + text) and the
 * scene helper block (functions and constants every script can call, like init_script).
 */
const props = defineProps<{
  adventureId: string
  scene: any
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
}>()

const FIELDS = [
  'on_enter_scene_script',
  'on_enter_scene_text',
  'on_leave_scene_script',
  'on_leave_scene_text',
  'helpers_script',
] as const
type Field = (typeof FIELDS)[number]
type Draft = Record<Field, string>

const savedValues = computed<Draft>(() => {
  const values = {} as Draft
  for (const field of FIELDS) values[field] = String(props.scene?.[field] || '')
  return values
})

const draft = ref<Draft>({ ...savedValues.value })
const isSaving = ref(false)
const configuredCount = computed(() => FIELDS.filter((f) => savedValues.value[f].trim()).length)
const expanded = ref(configuredCount.value > 0)

// Another scene opened, or the saved values changed after a save.
watch(savedValues, (values) => {
  draft.value = { ...values }
})

const changedFields = computed(() =>
  FIELDS.filter((f) => draft.value[f].trim() !== savedValues.value[f].trim()),
)
const isDirty = computed(() => changedFields.value.length > 0)

async function save() {
  if (!props.scene?.id || !isDirty.value) return
  isSaving.value = true
  try {
    const changes = Object.fromEntries(changedFields.value.map((f) => [f, draft.value[f].trim()]))
    await entityService.saveEntityText(props.adventureId, {
      target_type: 'scene',
      target_id: String(props.scene.id),
      ...changes,
    })
    emit('refresh')
    notificationService.add('Scene scripts saved.', 'success')
  } catch (error: any) {
    notificationService.add(error?.message || 'Failed to save scene scripts.', 'error')
  } finally {
    isSaving.value = false
  }
}

const textareaClass =
  'w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y'
</script>

<template>
  <div class="bg-slate-900/40 border border-white/5 rounded-[2rem] backdrop-blur-md">
    <button type="button" class="w-full flex items-center gap-3 px-8 py-5 text-left" @click="expanded = !expanded">
      <div class="w-8 h-8 rounded-lg bg-violet-500/20 border border-violet-500/40 flex items-center justify-center shrink-0">
        <Code2 class="w-4 h-4 text-violet-300" />
      </div>
      <div class="flex-1 min-w-0">
        <p class="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] flex items-center gap-2">
          Scene Scripts
          <span class="normal-case tracking-normal text-[10px] px-2 py-0.5 rounded-full bg-violet-500/15 border border-violet-500/30 text-violet-300 font-bold">
            {{ configuredCount }} configured
          </span>
          <span v-if="isDirty" class="normal-case tracking-normal text-[10px] text-amber-300 font-bold">unsaved</span>
        </p>
        <p class="text-[11px] text-slate-500 mt-0.5">Enter / leave triggers and the scene's helper functions.</p>
      </div>
      <component :is="expanded ? ChevronUp : ChevronDown" class="w-4 h-4 text-slate-500 shrink-0" />
    </button>

    <div v-if="expanded" class="px-8 pb-6 space-y-5 border-t border-white/5 pt-5">
      <div class="grid lg:grid-cols-2 gap-5">
        <div class="space-y-3 border border-white/5 bg-black/20 p-4 rounded-xl">
          <ScriptEditor
            v-model="draft.on_enter_scene_script"
            label="On Enter Scene Script"
            help-text="Executed immediately when the protagonist enters this scene."
            context="on_enter_scene"
            min-height="120px"
          />
          <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Enter Scene Text</label>
          <textarea v-model="draft.on_enter_scene_text" rows="3" :class="textareaClass" placeholder="Shown right after the player enters the scene."></textarea>
        </div>
        <div class="space-y-3 border border-white/5 bg-black/20 p-4 rounded-xl">
          <ScriptEditor
            v-model="draft.on_leave_scene_script"
            label="On Leave Scene Script"
            help-text="Executed immediately when the protagonist leaves this scene."
            context="on_leave_scene"
            min-height="120px"
          />
          <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Leave Scene Text</label>
          <textarea v-model="draft.on_leave_scene_text" rows="3" :class="textareaClass" placeholder="Shown right when the player leaves the scene."></textarea>
        </div>
      </div>

      <div class="space-y-2 border border-sky-500/15 bg-black/20 p-4 rounded-xl">
        <ScriptEditor
          v-model="draft.helpers_script"
          label="Scene Helpers"
          help-text="Functions and constants (def, NAME = value) that every script can call, like the global init script. Loaded on every script run, wherever the player is. Other statements never run; use the enter/leave scripts for those."
          context="init_script"
          placeholder="def crypt_curse():&#10;    tw.player.damage(8)&#10;    tw.vars.set('crypt_cursed', True)"
          min-height="140px"
        />
      </div>

      <div class="flex items-center justify-end gap-3">
        <button
          type="button"
          :disabled="!isDirty || isSaving"
          class="px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-wider text-slate-400 hover:text-white disabled:opacity-40 transition-colors"
          @click="draft = { ...savedValues }"
        >
          Revert
        </button>
        <button
          type="button"
          :disabled="!isDirty || isSaving"
          class="flex items-center gap-2 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-black uppercase tracking-wider disabled:opacity-40 transition-colors"
          @click="save"
        >
          <Save class="w-3.5 h-3.5" />
          {{ isSaving ? 'Saving...' : 'Save Scene Scripts' }}
        </button>
      </div>
    </div>
  </div>
</template>
