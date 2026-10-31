<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Save, X } from 'lucide-vue-next'
import {
  CUSTOM_VOICE_ID,
  narratorVoiceService,
  VOICE_INSTRUCTION_MAX,
  VOICE_SAMPLE_MAX,
  type NarratorVoice,
} from '@/services/narratorVoiceService'

/**
 * Picks how the GM narrates this adventure: a voice from the admin catalog (stored as a full
 * copy, so the manifest keeps it) or a custom instruction written by the author.
 */
const props = defineProps<{
  modelValue: NarratorVoice | null
  /** The voice currently stored on the adventure, for the unsaved-changes buttons. */
  saved: NarratorVoice | null
  isSaving: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: NarratorVoice | null): void
  (e: 'save-changes'): void
}>()

const catalog = ref<NarratorVoice[]>([])
const loadError = ref('')

onMounted(async () => {
  try {
    catalog.value = (await narratorVoiceService.load()).items
  } catch (err) {
    loadError.value = (err as Error).message
  }
})

const selectedId = computed(() => props.modelValue?.id || '')
const isCustom = computed(() => selectedId.value === CUSTOM_VOICE_ID)
/** A stored preset the admin has since removed still shows up as selectable. */
const voices = computed(() => {
  const value = props.modelValue
  const missing = value && !isCustom.value && !catalog.value.some((v) => v.id === value.id)
  return missing ? [...catalog.value, value] : catalog.value
})
const isDirty = computed(() => JSON.stringify(props.modelValue || null) !== JSON.stringify(props.saved || null))

const pick = (voice: NarratorVoice | null) => emit('update:modelValue', voice ? { ...voice } : null)

const pickCustom = () => {
  if (isCustom.value) return
  emit('update:modelValue', { id: CUSTOM_VOICE_ID, name: 'Custom', instruction: '', sample: '' })
}

const updateCustom = (field: 'name' | 'instruction' | 'sample', value: string) => {
  if (!props.modelValue) return
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}

const cardClass = (active: boolean) =>
  active ? 'border-fuchsia-500 ring-4 ring-fuchsia-500/20' : 'border-white/5 hover:border-white/15'
</script>

<template>
  <section class="space-y-6 bg-slate-900/40 p-8 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-4">
        <div class="w-10 h-10 rounded-xl bg-fuchsia-500/10 flex items-center justify-center border border-fuchsia-500/20">
          <i class="ra ra-speech-bubble text-fuchsia-400"></i>
        </div>
        <div>
          <h3 class="text-sm font-black text-white uppercase tracking-[0.2em]">Narrator Voice</h3>
          <p class="text-xs font-bold text-slate-500 uppercase tracking-widest">How the Game Master speaks</p>
        </div>
      </div>
      <div v-if="isDirty" class="flex items-center gap-2 animate-fade-in">
        <button @click="emit('save-changes')" :disabled="isSaving" class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg disabled:opacity-50 flex items-center justify-center" title="Save">
          <i v-if="isSaving" class="ra ra-cycle animate-spin text-sm"></i>
          <Save v-else class="w-4 h-4" />
        </button>
        <button @click="pick(saved)" :disabled="isSaving" class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-xl transition-all flex items-center justify-center" title="Cancel">
          <X class="w-4 h-4" />
        </button>
      </div>
    </div>

    <p class="text-xs text-slate-400 leading-relaxed">
      Sets word choice, sentence rhythm and attitude of the narration. The length of the narration stays
      with the player's narration style, and NPCs keep their own way of speaking. The voice is saved with
      the adventure and exported in its manifest.
    </p>
    <p v-if="loadError" class="text-xs text-rose-400">Could not load the voice catalog: {{ loadError }}</p>

    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
      <button type="button" @click="pick(null)" class="text-left p-4 rounded-2xl border-2 bg-slate-950/40 transition-all" :class="cardClass(!selectedId)">
        <p class="text-xs font-black text-white uppercase tracking-wider">Engine default</p>
        <p class="text-xs text-slate-500 mt-1">No special voice: a neutral, clear game master.</p>
      </button>
      <button
        v-for="voice in voices"
        :key="voice.id"
        type="button"
        @click="pick(voice)"
        class="text-left p-4 rounded-2xl border-2 bg-slate-950/40 transition-all"
        :class="cardClass(selectedId === voice.id)"
        :title="voice.instruction"
      >
        <p class="text-xs font-black text-white uppercase tracking-wider">{{ voice.name }}</p>
        <p v-if="voice.description" class="text-xs text-slate-500 mt-1">{{ voice.description }}</p>
        <p v-if="voice.sample" class="text-xs text-slate-400 italic mt-2 line-clamp-3">"{{ voice.sample }}"</p>
      </button>
      <button type="button" @click="pickCustom" class="text-left p-4 rounded-2xl border-2 bg-slate-950/40 transition-all" :class="cardClass(isCustom)">
        <p class="text-xs font-black text-white uppercase tracking-wider">Custom voice</p>
        <p class="text-xs text-slate-500 mt-1">Write your own instruction for this adventure.</p>
      </button>
    </div>

    <div v-if="isCustom && modelValue" class="space-y-4 p-6 bg-slate-950/40 border border-slate-800/40 rounded-2xl">
      <label class="block space-y-1">
        <span class="text-xs font-bold text-slate-400 uppercase tracking-widest">Name</span>
        <input
          :value="modelValue.name"
          @input="updateCustom('name', ($event.target as HTMLInputElement).value)"
          maxlength="80"
          class="w-full bg-slate-950 border border-slate-800 text-white text-sm rounded-lg p-2.5"
        />
      </label>
      <label class="block space-y-1">
        <span class="text-xs font-bold text-slate-400 uppercase tracking-widest">Instruction for the GM</span>
        <textarea
          :value="modelValue.instruction"
          @input="updateCustom('instruction', ($event.target as HTMLTextAreaElement).value)"
          :maxlength="VOICE_INSTRUCTION_MAX"
          rows="4"
          placeholder="e.g. Narrate like a weary ship's captain writing in her log: terse, salty, dry humour, nautical metaphors."
          class="w-full bg-slate-950 border border-slate-800 text-white text-sm rounded-lg p-2.5"
        ></textarea>
        <span v-if="!modelValue.instruction.trim()" class="text-xs text-amber-400">
          Without an instruction the GM narrates in the engine default voice.
        </span>
      </label>
      <label class="block space-y-1">
        <span class="text-xs font-bold text-slate-400 uppercase tracking-widest">Style sample (optional)</span>
        <textarea
          :value="modelValue.sample"
          @input="updateCustom('sample', ($event.target as HTMLTextAreaElement).value)"
          :maxlength="VOICE_SAMPLE_MAX"
          rows="2"
          placeholder="One or two sentences in this voice. The GM copies the voice, not the content."
          class="w-full bg-slate-950 border border-slate-800 text-white text-sm italic rounded-lg p-2.5"
        ></textarea>
      </label>
    </div>
  </section>
</template>
