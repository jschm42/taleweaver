<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'

interface SceneOption {
  id: string
  name: string
  imageUrl?: string | null
  type?: string
}

const props = withDefaults(
  defineProps<{
    show: boolean
    itemName: string
    itemId: string
    currentSceneId: string
    sceneOptions: SceneOption[]
    isSaving: boolean
    entityType?: 'npc' | 'item' | 'object'
  }>(),
  {
    entityType: 'item',
  },
)

const isNpc = computed(() => props.entityType === 'npc')
const entityLabel = computed(() => (isNpc.value ? 'NPC' : 'Item'))

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm', targetSceneId: string): void
}>()

const targetSceneId = ref<string>('')

watch(
  () => props.show,
  (isOpen) => {
    if (isOpen) {
      targetSceneId.value = ''
    }
  },
)

const currentSceneName = computed(() => {
  if (!props.currentSceneId) return 'Unassigned'
  const match = props.sceneOptions.find((s) => String(s.id).toUpperCase() === String(props.currentSceneId || '').toUpperCase())
  return match?.name || props.currentSceneId || 'Unassigned'
})

const availableSceneOptions = computed(() => {
  return props.sceneOptions.filter((s) => String(s.id).toUpperCase() !== String(props.currentSceneId || '').toUpperCase())
})

const canConfirm = computed(
  () =>
    String(targetSceneId.value).trim().length > 0 &&
    String(targetSceneId.value).toUpperCase() !== String(props.currentSceneId || '').toUpperCase() &&
    !props.isSaving,
)

function handleConfirm() {
  if (!canConfirm.value) return
  emit('confirm', String(targetSceneId.value).trim().toUpperCase())
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="show"
        class="fixed inset-0 z-[220] flex items-center justify-center p-6 backdrop-blur-xl bg-slate-950/60"
        @click.self="emit('close')"
      >
        <div class="modal-content w-full max-w-xl bg-slate-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
          <div class="p-6 border-b border-white/5">
            <div class="flex items-start justify-between gap-4">
              <div class="space-y-1">
                <h3 class="text-xs font-black uppercase tracking-widest" :class="isNpc ? 'text-cyan-400' : 'text-emerald-500'">
                  Move {{ entityLabel }} to Scene
                </h3>
                <p class="text-slate-500 text-xs uppercase font-bold tracking-tighter">
                  {{ entityLabel }}: <span class="text-slate-200">{{ itemName || itemId }}</span>
                </p>
              </div>
              <button @click="emit('close')" class="text-slate-500 hover:text-white transition-colors">
                <i class="ra ra-cancel text-xl"></i>
              </button>
            </div>
          </div>

          <div class="p-6 space-y-5">
            <div>
              <p class="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Currently in</p>
              <div class="px-4 py-3 rounded-xl bg-slate-950/60 border border-white/5">
                <div class="text-sm text-slate-300 font-mono">{{ currentSceneName }}</div>
                <div v-if="currentSceneId" class="text-[10px] text-slate-500 mt-0.5 font-mono">{{ currentSceneId }}</div>
              </div>
            </div>

            <div>
              <p class="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Move to</p>
              <EntityReferenceCombobox
                v-model="targetSceneId"
                :options="availableSceneOptions"
                placeholder="Select target scene"
                search-placeholder="Search scenes by id or name"
                :enable-search="true"
              />
              <p v-if="availableSceneOptions.length === 0" class="text-[11px] text-slate-500 mt-2">
                No other scenes available — create one in Scenes tab first.
              </p>
            </div>

            <div
              class="px-3 py-2 rounded-lg border border-sky-500/30 bg-sky-500/10 text-[11px] text-sky-200/90 leading-relaxed flex items-start gap-2"
              role="note"
            >
              <i class="ra ra-info text-sky-400 mt-0.5 shrink-0"></i>
              <span v-if="isNpc">
                The NPC keeps their portrait, stats, dialogue, and inventory. Only the
                <code class="text-sky-100">current_scene_id</code> column is updated.
              </span>
              <span v-else>
                The item keeps its type, image, name, and metadata. Only the
                <code class="text-sky-100">current_scene_id</code> column is updated.
              </span>
            </div>
          </div>

          <div class="p-4 border-t border-white/5 flex items-center justify-end gap-3">
            <button
              @click="emit('close')"
              :disabled="isSaving"
              class="px-5 py-2 text-slate-400 hover:text-white font-black uppercase text-xs tracking-widest transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              @click="handleConfirm"
              :disabled="!canConfirm"
              class="px-5 py-2 rounded-lg font-black uppercase text-xs tracking-widest transition-colors"
              :class="
                canConfirm
                  ? (isNpc ? 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 shadow-lg' : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-lg')
                  : 'bg-slate-800 text-slate-500 cursor-not-allowed'
              "
            >
              <i v-if="isSaving" class="ra ra-cycle animate-spin mr-1"></i>
              Move {{ entityLabel }}
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
  transition: opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-active .modal-content {
  animation: modalScaleIn 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}
.modal-leave-active .modal-content {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  transform: scale(0.95);
}
@keyframes modalScaleIn {
  from {
    opacity: 0;
    transform: scale(0.9) translateY(40px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
</style>
