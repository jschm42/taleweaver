<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { Save, X } from 'lucide-vue-next'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'

const props = withDefaults(defineProps<{
  value: string | number
  type?: 'text' | 'textarea' | 'number'
  maxlength?: number
  min?: number
  max?: number
  placeholder?: string
  required?: boolean
  isSaving?: boolean
  useReferences?: boolean
  referenceOptions?: any[]
  showAiGenerate?: boolean
  isGeneratingAi?: boolean
  rows?: number
  emptyText?: string
  displayClass?: string
  inputClass?: string
  editId?: string
  activeEditId?: string | null
}>(), {
  type: 'text',
  placeholder: '',
  required: false,
  isSaving: false,
  useReferences: false,
  referenceOptions: () => [],
  showAiGenerate: false,
  isGeneratingAi: false,
  rows: 3,
  emptyText: 'No content set. Click to edit.',
  displayClass: 'group cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center w-full min-h-[46px]',
  inputClass: 'flex-grow bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all',
  activeEditId: null
})

const emit = defineEmits<{
  (e: 'save', val: string | number): void
  (e: 'ai-generate'): void
  (e: 'start-edit', editId: string): void
}>()

const isEditing = ref(false)
const tempValue = ref<string | number>('')

const inputRef = ref<HTMLInputElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)

function startEdit() {
  if (props.isSaving) return
  tempValue.value = props.value ?? ''
  isEditing.value = true
  if (props.editId) {
    emit('start-edit', props.editId)
  }
  nextTick(() => {
    if (props.type === 'text' || props.type === 'number') {
      inputRef.value?.focus()
      inputRef.value?.select()
    } else if (props.type === 'textarea' && !props.useReferences) {
      textareaRef.value?.focus()
    }
  })
}

function cancelEdit() {
  isEditing.value = false
  tempValue.value = ''
}

function handleSave() {
  if (props.required && !String(tempValue.value).trim()) {
    return
  }
  if (props.maxlength && String(tempValue.value).length > props.maxlength) {
    return
  }
  emit('save', props.type === 'number' ? Number(tempValue.value) : tempValue.value)
}

function setEditValue(val: string | number) {
  tempValue.value = val ?? ''
  if (!isEditing.value) {
    isEditing.value = true
  }
}

watch(() => props.value, (newVal) => {
  if (isEditing.value && newVal === tempValue.value) {
    isEditing.value = false
  }
})

watch(() => props.isSaving, (newIsSaving, oldIsSaving) => {
  if (oldIsSaving && !newIsSaving) {
    if (props.value === tempValue.value) {
      isEditing.value = false
    }
  }
})

watch(() => props.activeEditId, (newActiveEditId) => {
  if (props.editId && newActiveEditId !== props.editId && isEditing.value) {
    cancelEdit()
  }
})

defineExpose({
  setEditValue,
  isEditing,
  tempValue
})
</script>

<template>
  <div class="w-full">
    <div v-if="isEditing" class="flex gap-2 animate-fade-in w-full" :class="type === 'textarea' ? 'items-start' : 'items-center'">
      <!-- Input / Textarea -->
      <template v-if="type === 'number'">
        <input
          ref="inputRef"
          type="number"
          v-model.number="tempValue"
          :min="min"
          :max="max"
          :class="inputClass"
          @keydown.enter="handleSave"
          @keydown.esc="cancelEdit"
        />
      </template>
      <template v-else-if="type === 'textarea'">
        <ReferenceTextarea
          v-if="useReferences"
          :model-value="String(tempValue)"
          @update:model-value="tempValue = $event"
          :rows="rows"
          :maxlength="maxlength"
          :placeholder="placeholder"
          class-name="w-full bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm focus:ring-2 ring-emerald-500/20 outline-none transition-all resize-y min-h-[80px]"
          class="flex-grow min-w-0"
        />
        <textarea
          v-else
          ref="textareaRef"
          v-model="tempValue"
          :maxlength="maxlength"
          :rows="rows"
          :placeholder="placeholder"
          class="flex-grow bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm focus:ring-2 ring-emerald-500/20 outline-none transition-all resize-y min-h-[80px]"
          @keydown.esc="cancelEdit"
        ></textarea>
      </template>
      <template v-else>
        <input
          ref="inputRef"
          type="text"
          v-model="tempValue"
          :maxlength="maxlength"
          :placeholder="placeholder"
          :class="inputClass"
          @keydown.enter="handleSave"
          @keydown.esc="cancelEdit"
        />
      </template>

      <!-- Action Buttons -->
      <div :class="type === 'textarea' ? 'flex flex-col gap-1.5 justify-center shrink-0' : 'flex gap-1.5 items-center shrink-0'">
        <button
          @click="handleSave"
          :disabled="isSaving || (required && !String(tempValue).trim()) || (maxlength && String(tempValue).length > maxlength)"
          class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg disabled:opacity-50 shrink-0 flex items-center justify-center"
          title="Save"
        >
          <i v-if="isSaving" class="ra ra-cycle animate-spin text-sm"></i>
          <Save v-else class="w-4 h-4" />
        </button>

        <button
          v-if="showAiGenerate"
          type="button"
          :disabled="isSaving || isGeneratingAi"
          class="p-2.5 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-400 rounded-xl transition-all shrink-0 flex items-center justify-center"
          title="AI Generate"
          @click="emit('ai-generate')"
        >
          <i class="ra ra-crystals" :class="{ 'animate-spin': isGeneratingAi }"></i>
        </button>

        <button
          @click="cancelEdit"
          :disabled="isSaving"
          class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-xl transition-all shrink-0 flex items-center justify-center"
          title="Cancel"
        >
          <X class="w-4 h-4" />
        </button>
      </div>
    </div>

    <!-- View Mode -->
    <div
      v-else
      @click="startEdit"
      :class="displayClass"
    >
      <div class="flex-grow min-w-0">
        <slot :value="value">
          <span v-if="value !== undefined && value !== null && value !== ''" class="text-sm font-bold text-white leading-relaxed">{{ value }}</span>
          <span v-else class="text-xs italic text-slate-600 uppercase tracking-widest">{{ emptyText }}</span>
        </slot>
      </div>
      <i class="ra ra-quill-pen text-xs text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-2 self-center"></i>
    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.3s ease-out forwards;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
