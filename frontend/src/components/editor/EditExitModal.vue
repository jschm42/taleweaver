<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'

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
  }): void
}>()

const form = ref({ ...props.initialForm })

watch(
  () => props.initialForm,
  (newVal) => {
    form.value = { ...newVal }
  },
  { deep: true, immediate: true }
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

const isFormInvalid = computed(() => {
  const labelText = (form.value.label || '').trim()
  if (!labelText || labelText.length > 100) return true
  if ((form.value.lock_description || '').length > 255) return true
  if ((form.value.code_to_unlock || '').length > 32) return true
  if ((form.value.rule_to_unlock || '').length > 500) return true
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
          <div class="p-6 pb-28 space-y-5 overflow-y-auto flex-1 text-slate-200">
            <div class="flex justify-between items-center">
              <div class="space-y-1">
                <h3 class="text-xs font-black text-emerald-500 uppercase tracking-widest">
                  {{ isCreateMode ? 'Create Exit' : 'Edit Exit' }}
                </h3>
                <p class="text-slate-500 text-xs uppercase font-bold tracking-tighter">
                  {{ isCreateMode ? `From: ${form.from_scene_id || fromSceneId || 'n/a'}` : `ID: ${activeEditExitId || 'n/a'}` }}
                </p>
              </div>
              <button @click="emit('close')" class="text-slate-500 hover:text-white transition-colors">
                <i class="ra ra-cancel text-xl"></i>
              </button>
            </div>

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
                <span>Lock Description</span>
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
                  v-model="form.item_to_unlock"
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
          </div>

          <div class="p-4 border-t border-white/10 flex justify-end gap-2">
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
