<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'

const props = defineProps<{
  isSaving: boolean
  editorScenes: any[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'create', payload: { sceneId: string; name: string; description: string }): void
}>()

const sceneId = ref('')
const name = ref('')
const description = ref('')
const formError = ref('')
const sceneNameInputRef = ref<HTMLInputElement | null>(null)

watch(sceneId, (newVal) => {
  sceneId.value = newVal.toUpperCase()
})

const idError = computed(() => {
  const val = sceneId.value.trim()
  if (!val) return ''
  
  const idRegex = /^[A-Z0-9_]+$/
  if (!idRegex.test(val)) {
    return 'ID must contain only uppercase letters, digits, and underscores.'
  }

  if (val.length > 30) {
    return 'ID must be 30 characters or less.'
  }

  const takenIds = new Set((props.editorScenes || []).map((scene) => String(scene.id || '').toUpperCase()))
  if (takenIds.has(val.toUpperCase())) {
    return `ID "${val}" already exists in this adventure.`
  }
  return ''
})

onMounted(() => {
  sceneNameInputRef.value?.focus()
})

function cancel() {
  emit('close')
}

function submit() {
  const sId = sceneId.value.trim()
  const sName = name.value.trim()
  const sDesc = description.value.trim()

  if (!sId) {
    formError.value = 'Scene ID is required.'
    return
  }
  const currentIdError = idError.value
  if (currentIdError) {
    formError.value = currentIdError
    return
  }
  if (!sName) {
    formError.value = 'Scene name is required.'
    return
  }
  if (sName.length > 100) {
    formError.value = 'Scene name must be 100 characters or less.'
    return
  }
  if (!sDesc) {
    formError.value = 'Scene description is required.'
    return
  }
  if (sDesc.length > 1000) {
    formError.value = 'Scene description must be 1000 characters or less.'
    return
  }

  formError.value = ''
  emit('create', { sceneId: sId, name: sName, description: sDesc })
}
</script>

<template>
  <section class="space-y-6 animate-page-in">
    <div class="flex items-center justify-between gap-3 border-b border-white/10 pb-3">
      <h3 class="text-xs font-black text-emerald-400 uppercase tracking-[0.3em]">New Scene</h3>
      <button class="px-3 py-2 text-xs font-bold rounded-lg border border-white/20 text-slate-300 hover:bg-white/10" @click="cancel">
        Cancel
      </button>
    </div>

    <div class="space-y-4">
      <!-- Scene ID (Pflichtfeld) -->
      <div>
        <div class="flex justify-between items-center mb-1.5">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">
            Scene ID <span class="text-red-400">*</span>
          </label>
          <span :class="['text-[10px] font-bold tracking-widest', (sceneId || '').length > 30 ? 'text-red-500' : 'text-emerald-500/50']">
            {{ (sceneId || '').length }} / 30
          </span>
        </div>
        <input
          v-model="sceneId"
          type="text"
          maxlength="30"
          placeholder="e.g. DARK_FOREST"
          class="w-full bg-black/60 border rounded-xl px-4 py-2.5 text-sm text-white font-mono tracking-wider placeholder:text-slate-600 focus:outline-none focus:ring-2 transition-all uppercase"
          :class="idError ? 'border-red-500 focus:ring-red-500/50' : 'border-white/10 focus:ring-emerald-500/50 focus:border-emerald-500'"
          @keydown.enter="submit"
        />
        <p v-if="idError" class="text-xs font-bold text-red-400 mt-1.5">{{ idError }}</p>
      </div>

      <!-- Scene Name (Pflichtfeld) -->
      <div>
        <div class="flex justify-between items-center mb-1.5">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">
            Scene Name <span class="text-red-400">*</span>
          </label>
          <span :class="['text-[10px] font-bold tracking-widest', (name || '').length > 100 ? 'text-red-500' : 'text-emerald-500/50']">
            {{ (name || '').length }} / 100
          </span>
        </div>
        <input
          ref="sceneNameInputRef"
          v-model="name"
          type="text"
          maxlength="100"
          placeholder="e.g. Dark Forest"
          class="w-full bg-black/60 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
          @keydown.enter="submit"
        />
      </div>

      <!-- Scene Description (Pflichtfeld) -->
      <div>
        <div class="flex justify-between items-center mb-1.5">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">
            Description <span class="text-red-400">*</span>
          </label>
          <span :class="['text-[10px] font-bold tracking-widest', (description || '').length > 1000 ? 'text-red-500' : 'text-emerald-500/50']">
            {{ (description || '').length }} / 1000
          </span>
        </div>
        <textarea
          v-model="description"
          rows="4"
          maxlength="1000"
          placeholder="A brief description of this scene..."
          class="w-full bg-black/60 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all resize-none"
        ></textarea>
      </div>

      <!-- Error -->
      <p v-if="formError" class="text-xs font-bold text-red-400">{{ formError }}</p>

      <!-- Actions -->
      <div class="flex items-center justify-end gap-3 pt-2">
        <button @click="cancel" class="px-4 py-2.5 text-xs font-bold text-slate-400 hover:text-white uppercase tracking-widest transition-all">
          Cancel
        </button>
        <button @click="submit" :disabled="isSaving" class="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg disabled:opacity-50">
          <i v-if="isSaving" class="ra ra-cycle animate-spin mr-2"></i>
          Create Scene
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.animate-page-in {
  animation: pageIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes pageIn {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

input, textarea {
  transition: all 0.3s ease;
}
</style>
