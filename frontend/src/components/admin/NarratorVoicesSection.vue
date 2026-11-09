<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  narratorVoiceService,
  VOICE_INSTRUCTION_MAX,
  VOICE_SAMPLE_MAX,
  type NarratorVoice,
} from '@/services/narratorVoiceService'

const voices = ref<NarratorVoice[]>([])
const defaults = ref<NarratorVoice[]>([])
const isLoading = ref(true)
const isSaving = ref(false)
const status = ref<{ type: 'success' | 'error'; text: string } | null>(null)

const copy = (list: NarratorVoice[]) => list.map((voice) => ({ ...voice }))

onMounted(async () => {
  try {
    const catalog = await narratorVoiceService.load()
    voices.value = copy(catalog.items)
    defaults.value = catalog.defaults
  } catch (err) {
    status.value = { type: 'error', text: (err as Error).message }
  } finally {
    isLoading.value = false
  }
})

const addVoice = () => {
  voices.value.push({ id: '', name: '', description: '', instruction: '', sample: '' })
}

const removeVoice = (index: number) => {
  voices.value.splice(index, 1)
}

const restoreDefaults = () => {
  voices.value = copy(defaults.value)
  status.value = null
}

const save = async () => {
  isSaving.value = true
  status.value = null
  try {
    const complete = voices.value.filter((voice) => voice.name.trim() && voice.instruction.trim())
    voices.value = copy(await narratorVoiceService.save(complete))
    status.value = { type: 'success', text: 'Narrator personas saved.' }
  } catch (err) {
    status.value = { type: 'error', text: (err as Error).message }
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div class="space-y-6 animate-fade-in max-w-5xl">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-3xl font-extrabold text-white tracking-tight">Narrator Personas</h1>
        <p class="text-slate-400 text-sm mt-1">
          How the Game Master narrates: word choice, sentence rhythm and attitude. Authors pick a persona
          per adventure in the editor (Tone tab) or write their own. The narration length stays with the
          player's narration style.
        </p>
      </div>

      <button 
        type="button" 
        @click="save" 
        :disabled="isSaving" 
        class="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-indigo-900/30 disabled:opacity-50 flex items-center gap-2 self-start sm:self-auto cursor-pointer shrink-0"
      >
        <i v-if="isSaving" class="ra ra-recycle animate-spin"></i>
        <i v-else class="ra ra-save"></i>
        <span>{{ isSaving ? 'Saving...' : 'Save Narrator Personas' }}</span>
      </button>
    </div>

    <div v-if="isLoading" class="text-slate-500 text-sm">Loading personas...</div>

    <div v-else class="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
      <div
        v-for="(voice, index) in voices"
        :key="index"
        class="p-6 bg-slate-950/40 border border-slate-800/40 rounded-2xl space-y-4"
      >
        <div class="flex items-start gap-4">
          <div class="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
            <label class="space-y-1">
              <span class="text-xs font-bold text-slate-400 uppercase tracking-widest">Name</span>
              <input
                v-model="voice.name"
                maxlength="80"
                placeholder="e.g. Hardboiled Noir Detective"
                class="w-full bg-slate-950 border border-slate-800 text-white text-sm rounded-lg p-2.5"
              />
            </label>
            <label class="space-y-1">
              <span class="text-xs font-bold text-slate-400 uppercase tracking-widest">Short description</span>
              <input
                v-model="voice.description"
                maxlength="300"
                placeholder="Genre and character of the persona"
                class="w-full bg-slate-950 border border-slate-800 text-white text-sm rounded-lg p-2.5"
              />
            </label>
          </div>
          <button
            type="button"
            @click="removeVoice(index)"
            class="mt-6 px-3 py-2 text-xs font-bold text-rose-400 hover:text-white hover:bg-rose-600 rounded-lg transition-colors"
            title="Remove this persona"
          >
            Remove
          </button>
        </div>
        <label class="block space-y-1">
          <span class="text-xs font-bold text-slate-400 uppercase tracking-widest">Instruction for the GM</span>
          <textarea
            v-model="voice.instruction"
            :maxlength="VOICE_INSTRUCTION_MAX"
            rows="3"
            placeholder="Narrate like ... Use ... Never ..."
            class="w-full bg-slate-950 border border-slate-800 text-white text-sm rounded-lg p-2.5"
          ></textarea>
        </label>
        <label class="block space-y-1">
          <span class="text-xs font-bold text-slate-400 uppercase tracking-widest">Style sample (optional)</span>
          <textarea
            v-model="voice.sample"
            :maxlength="VOICE_SAMPLE_MAX"
            rows="2"
            placeholder="One or two sentences in this persona. The GM copies the style, not the content."
            class="w-full bg-slate-950 border border-slate-800 text-white text-sm italic rounded-lg p-2.5"
          ></textarea>
        </label>
      </div>

      <p v-if="!voices.length" class="text-sm text-slate-500">
        No personas. Saving an empty list restores the built-in defaults.
      </p>

      <div class="flex flex-wrap gap-3">
        <button
          type="button"
          @click="addVoice"
          class="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-white text-sm font-bold rounded-xl"
        >
          Add persona
        </button>
        <button
          type="button"
          @click="restoreDefaults"
          class="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-bold rounded-xl"
          title="Replace the list with the built-in personas (not saved until you click Save)"
        >
          Restore defaults
        </button>
      </div>

      <p
        v-if="status"
        class="text-sm font-bold"
        :class="status.type === 'success' ? 'text-emerald-400' : 'text-rose-400'"
      >
        {{ status.text }}
      </p>


    </div>
  </div>
</template>
