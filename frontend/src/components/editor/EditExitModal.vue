<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import { Lock, Sparkles, ChevronDown, ChevronRight } from 'lucide-vue-next'

const props = defineProps<{
  show: boolean
  isCreateMode: boolean
  fromSceneId: string
  activeEditExitId: string | null
  initialForm: {
    from_scene_id: string
    to_scene_id: string
    label: string
    exit_type: 'one_way' | 'bidirectional'
    lock_description: string
    code_to_unlock?: string
    item_to_unlock?: string
    rule_to_unlock?: string
    unlock_expression?: string
    on_unlock_success_script?: string
    on_unlock_success_text?: string
    on_unlock_failure_script?: string
    on_unlock_failure_text?: string
    on_open_exit_script?: string
    on_open_exit_text?: string
    on_exit_used_script?: string
    on_exit_used_text?: string
  }
  sceneReferenceOptions: any[]
  referenceOptions: any[]
  isSavingText: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', form: {
    from_scene_id: string
    to_scene_id: string
    label: string
    exit_type: 'one_way' | 'bidirectional'
    lock_description: string
    code_to_unlock?: string
    item_to_unlock?: string
    rule_to_unlock?: string
    unlock_expression?: string
    on_unlock_success_script?: string
    on_unlock_success_text?: string
    on_unlock_failure_script?: string
    on_unlock_failure_text?: string
    on_open_exit_script?: string
    on_open_exit_text?: string
    on_exit_used_script?: string
    on_exit_used_text?: string
  }): void
}>()

const EMPTY_FORM = {
  from_scene_id: '',
  to_scene_id: '',
  label: '',
  exit_type: 'one_way' as 'one_way' | 'bidirectional',
  lock_description: '',
  code_to_unlock: '',
  item_to_unlock: '',
  rule_to_unlock: '',
  unlock_expression: '',
  on_unlock_success_script: '',
  on_unlock_success_text: '',
  on_unlock_failure_script: '',
  on_unlock_failure_text: '',
  on_open_exit_script: '',
  on_open_exit_text: '',
  on_exit_used_script: '',
  on_exit_used_text: '',
}

const showExitGuard = ref(false)
const showExitUnlockTriggers = ref(false)

const form = ref({ ...(props.initialForm || EMPTY_FORM) })

watch(
  () => props.initialForm,
  (newVal) => {
    form.value = { ...(newVal || EMPTY_FORM) }
  },
  { deep: true, immediate: true }
)

watch(
  () => props.show,
  (open) => {
    if (open) {
      form.value = { ...(props.initialForm || EMPTY_FORM) }
      showExitGuard.value = false
      showExitUnlockTriggers.value = false
    } else {
      form.value = { ...EMPTY_FORM }
    }
  },
)

const itemReferenceOptions = computed(() => {
  const source = props.referenceOptions || []
  return source
    .filter((option) => String(option.type || '').toUpperCase() === 'OBJECT')
    .map((option) => ({
      ...option,
      name: option.name || option.id || '',
    }))
})

const hasGate = computed(() => {
  return Boolean(
    (form.value.code_to_unlock || '').trim()
    || (form.value.item_to_unlock || '').trim()
    || (form.value.rule_to_unlock || '').trim()
    || (form.value.unlock_expression || '').trim()
  )
})

const isFormInvalid = computed(() => {
  const labelText = (form.value.label || '').trim()
  if (!labelText || labelText.length > 100) return true
  if ((form.value.lock_description || '').length > 255) return true
  if ((form.value.code_to_unlock || '').length > 32) return true
  if ((form.value.rule_to_unlock || '').length > 500) return true
  if (hasGate.value && !(form.value.lock_description || '').trim()) return true
  return false
})

function submit() {
  if (isFormInvalid.value) return
  emit('save', { ...form.value })
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="fixed inset-0 z-[190] flex items-center justify-center p-6 backdrop-blur-xl bg-slate-950/60">
        <div class="w-full max-w-2xl bg-slate-900 border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden max-h-[92vh] flex flex-col">
          <!-- Fixed Header -->
          <div class="px-6 py-5 flex justify-between items-center border-b border-white/10 text-slate-200">
            <div class="space-y-1">
              <h3 class="text-xs font-black text-emerald-500 uppercase tracking-widest">
                {{ isCreateMode ? 'Create Exit' : (form.label || 'Edit Exit') }}
              </h3>
              <p class="text-slate-500 text-xs uppercase font-bold tracking-tighter">
                {{ isCreateMode ? `From: ${form.from_scene_id || fromSceneId || 'n/a'}` : (activeEditExitId ? `ID: ${activeEditExitId}` : '') }}
              </p>
            </div>
            <button @click="emit('close')" class="text-slate-500 hover:text-white transition-colors">
              <i class="ra ra-cancel text-xl"></i>
            </button>
          </div>

          <!-- Scrollable Content -->
          <div class="p-6 space-y-5 overflow-y-auto flex-1 text-slate-200">
            <div class="grid md:grid-cols-2 gap-3">
              <label class="text-xs text-slate-300 space-y-1">
                <span>From Scene</span>
                <input :value="form.from_scene_id || fromSceneId" class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-200" disabled />
              </label>
              <label class="text-xs text-slate-300 space-y-1">
                <span>To Scene</span>
                <EntityReferenceCombobox
                  v-if="isCreateMode"
                  v-model="form.to_scene_id"
                  :options="sceneReferenceOptions.filter((scene) => scene.id !== (form.from_scene_id || fromSceneId))"
                  placeholder="Select destination scene"
                  :enable-search="true"
                />
                <input
                  v-else
                  :value="form.to_scene_id"
                  class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-200"
                  disabled
                />
              </label>
            </div>

            <div class="grid md:grid-cols-2 gap-3">
              <label class="text-xs text-slate-300 space-y-1">
                <div class="flex justify-between items-center">
                  <span>Label <span class="text-red-400">*</span></span>
                  <span :class="['text-[10px] font-mono', (form.label || '').length > 100 || !(form.label || '').trim() ? 'text-red-500 font-bold' : 'text-emerald-500/40']">
                    {{ (form.label || '').length }} / 100
                  </span>
                </div>
                <input v-model="form.label" maxlength="100" class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-white focus:border-emerald-500 outline-none transition-all" />
              </label>
              <label class="text-xs text-slate-300 space-y-1">
                <span>Type</span>
                <select v-model="form.exit_type" class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-white focus:border-emerald-500 outline-none transition-all">
                  <option value="one_way">one_way</option>
                  <option value="bidirectional">bidirectional</option>
                </select>
              </label>
            </div>

            <label class="text-xs text-slate-300 space-y-1 block">
              <div class="flex justify-between items-center">
                <span>Lock Description<span v-if="hasGate" class="text-red-400"> *</span></span>
                <span :class="['text-[10px] font-mono', (form.lock_description || '').length > 255 ? 'text-red-500 font-bold' : 'text-emerald-500/40']">
                  {{ (form.lock_description || '').length }} / 255
                </span>
              </div>
              <ReferenceTextarea
                v-model="form.lock_description"
                :rows="3"
                :options="referenceOptions"
                :maxlength="255"
                class-name="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all"
              />
            </label>

            <div class="grid md:grid-cols-2 gap-3">
              <label class="text-xs text-slate-300 space-y-1">
                <div class="flex justify-between items-center">
                  <span>Code To Unlock</span>
                  <span :class="['text-[10px] font-mono', (form.code_to_unlock || '').length > 32 ? 'text-red-500 font-bold' : 'text-emerald-500/40']">
                    {{ (form.code_to_unlock || '').length }} / 32
                  </span>
                </div>
                <input v-model="form.code_to_unlock" maxlength="32" class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-white focus:border-emerald-500 outline-none transition-all" placeholder="e.g. 1234 or WORD" />
              </label>
              <label class="text-xs text-slate-300 space-y-1">
                <span>Item ID To Unlock</span>
                <EntityReferenceCombobox
                  v-model="form.item_to_unlock as string"
                  :options="itemReferenceOptions"
                  placeholder="Select key item reference"
                  :enable-search="true"
                />
              </label>
            </div>

            <label class="text-xs text-slate-300 space-y-1 block">
              <div class="flex justify-between items-center">
                <span>Rule To Unlock (Narrative Requirement)</span>
                <span :class="['text-[10px] font-mono', (form.rule_to_unlock || '').length > 500 ? 'text-red-500 font-bold' : 'text-emerald-500/40']">
                  {{ (form.rule_to_unlock || '').length }} / 500
                </span>
              </div>
              <input v-model="form.rule_to_unlock" maxlength="500" class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-white focus:border-emerald-500 outline-none transition-all" placeholder="e.g. Protagonist defeats NPC_2" />
            </label>

            <!-- On Open Exit Trigger (Unified in General) -->
            <div class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
              <ScriptEditor
                v-model="form.on_open_exit_script"
                label="On Open Exit Script"
                help-text="Executed immediately when the player unlocks/opens this exit."
                context="on_open_exit"
                min-height="100px"
              />
              <div class="space-y-1">
                <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Open Exit Text</label>
                <textarea v-model="form.on_open_exit_text" rows="2" placeholder="e.g. The rusty heavy iron door slowly creaks open." class="w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y"></textarea>
              </div>
            </div>

            <!-- On Exit Used Transition Trigger -->
            <div class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
              <ScriptEditor
                v-model="form.on_exit_used_script"
                label="On Exit Used Script (Transition Trigger)"
                help-text="Executed immediately when the player traverses this exit."
                context="exit_used"
                min-height="100px"
              />
              <div class="space-y-1">
                <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Exit Used Text</label>
                <textarea v-model="form.on_exit_used_text" rows="2" placeholder="e.g. You step through the threshold into the dark corridor." class="w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y"></textarea>
              </div>
            </div>

            <!-- Collapsible Panel 1: Deterministic Guard (Default Collapsed) -->
            <div class="border border-white/10 rounded-xl overflow-hidden bg-black/30">
              <button
                type="button"
                @click="showExitGuard = !showExitGuard"
                class="w-full px-4 py-2.5 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
              >
                <div class="flex items-center gap-2">
                  <Lock class="w-3.5 h-3.5 text-emerald-400" />
                  <span class="text-[11px] font-black text-slate-300 uppercase tracking-wider">
                    Deterministic Guard Expression
                  </span>
                  <span v-if="form.unlock_expression" class="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-[9px] font-bold">
                    Configured
                  </span>
                </div>
                <component :is="showExitGuard ? ChevronDown : ChevronRight" class="w-4 h-4 text-slate-400" />
              </button>

              <div v-if="showExitGuard" class="p-4 border-t border-white/5 space-y-2">
                <ScriptEditor
                  v-model="form.unlock_expression"
                  label="Deterministic Script Guard Expression"
                  help-text="Deterministic Python boolean expression evaluated when attempting to unlock. If false, unlocking fails."
                  context="guard_expression"
                  placeholder="e.g. tw.switches.get('DRAWBRIDGE') == 'LOWERED' or tw.vars.get('guard_bribed') == True"
                  min-height="90px"
                />
                <p class="text-[10px] text-slate-400">
                  Deterministic Python boolean expression evaluated when attempting to unlock. If false, unlocking fails.
                </p>
              </div>
            </div>

            <!-- Collapsible Panel 2: Unlocking Transition Rules (Default Collapsed) -->
            <div class="border border-white/10 rounded-xl overflow-hidden bg-black/30">
              <button
                type="button"
                @click="showExitUnlockTriggers = !showExitUnlockTriggers"
                class="w-full px-4 py-2.5 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
              >
                <div class="flex items-center gap-2">
                  <Sparkles class="w-3.5 h-3.5 text-emerald-400" />
                  <span class="text-[11px] font-black text-slate-300 uppercase tracking-wider">
                    Unlocking Transition Rules
                  </span>
                  <span v-if="form.on_unlock_success_script || form.on_unlock_failure_script" class="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-[9px] font-bold">
                    Configured
                  </span>
                </div>
                <component :is="showExitUnlockTriggers ? ChevronDown : ChevronRight" class="w-4 h-4 text-slate-400" />
              </button>

              <div v-if="showExitUnlockTriggers" class="p-4 border-t border-white/5 space-y-4">
                <ScriptEditor
                  v-model="form.on_unlock_success_script"
                  label="On Unlock Success Script"
                  help-text="Executed immediately when this exit is successfully unlocked."
                  context="exit_unlock_success"
                  min-height="100px"
                />
                <div class="space-y-1">
                  <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Unlock Success Text</label>
                  <textarea
                    v-model="form.on_unlock_success_text"
                    rows="2"
                    placeholder="e.g. The mechanism unlatches with a heavy metallic sound."
                    class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-emerald-500/50 outline-none"
                  ></textarea>
                </div>

                <ScriptEditor
                  v-model="form.on_unlock_failure_script"
                  label="On Unlock Failure Script"
                  help-text="Executed when unlocking this exit fails or is blocked by guard."
                  context="exit_unlock_failure"
                  min-height="100px"
                />
                <div class="space-y-1">
                  <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Unlock Failure Text</label>
                  <textarea
                    v-model="form.on_unlock_failure_text"
                    rows="2"
                    placeholder="e.g. The locking bar refuses to shift. You cannot force it open."
                    class="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-emerald-500/50 outline-none"
                  ></textarea>
                </div>
              </div>
            </div>
          </div>

          <!-- Fixed Footer -->
          <div class="px-6 py-5 border-t border-white/10 flex justify-end gap-3 bg-slate-900/55 rounded-b-[2.5rem]">
            <button class="px-4 py-2 rounded-xl border border-white/15 text-slate-300 hover:bg-white/5" @click="emit('close')">Cancel</button>
            <button class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold disabled:opacity-50" :disabled="isSavingText || isFormInvalid" @click="submit">
              {{ isCreateMode ? 'Create Exit' : 'Save Exit' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
