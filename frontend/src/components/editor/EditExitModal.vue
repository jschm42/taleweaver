<script setup lang="ts">
import { ref, watch } from 'vue'
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

function submit() {
  emit('save', { ...form.value })
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="fixed inset-0 z-[190] flex items-center justify-center p-6 backdrop-blur-xl bg-slate-950/60">
        <div class="w-full max-w-2xl bg-slate-900 border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden max-h-[92vh] flex flex-col">
          <div class="p-6 space-y-5 overflow-y-auto flex-1 text-slate-200">
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
                <span>Label</span>
                <input v-model="form.label" class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-white focus:border-emerald-500 outline-none transition-all" />
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
              <span>Lock Description</span>
              <ReferenceTextarea
                v-model="form.lock_description"
                :rows="3"
                :options="referenceOptions"
                class-name="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all"
              />
            </label>
          </div>

          <div class="p-4 border-t border-white/10 flex justify-end gap-2">
            <button class="px-4 py-2 rounded-xl border border-white/15 text-slate-300 hover:bg-white/5" @click="emit('close')">Cancel</button>
            <button class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold disabled:opacity-50" :disabled="isSavingText" @click="submit">
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
