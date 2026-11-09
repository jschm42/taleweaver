<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import { api } from '@/composables/useApi'
import ElevenLabsVoiceField from '@/components/common/ElevenLabsVoiceField.vue'
import OpenAICompatibleTtsFields from '@/components/common/OpenAICompatibleTtsFields.vue'

const props = defineProps<{
  ttsForm: any
  configuredKeys: any
  isSubmitting: boolean
  testResults: any
}>()

const emit = defineEmits<{
  (e: 'save', payload: any): void
  (e: 'test', payload: any): void
  (e: 'switchSection', section: string): void
}>()

const localForm = ref({ ...props.ttsForm })
const elevenLabsModelsList = ref<Array<{ model_id: string, name: string }>>([])

const VOICE_LIST = [
  'Zephyr', 'Puck', 'Charon', 'Kore', 'Fenrir', 'Leda', 'Orus', 'Aoede', 'Callirrhoe',
  'Autonoe', 'Enceladus', 'Iapetus', 'Umbriel', 'Algieba', 'Despina', 'Erinome',
  'Algenib', 'Rasalgethi', 'Laomedeia', 'Achernar', 'Alnilam', 'Schedar', 'Gacrux',
  'Pulcherrima', 'Achird', 'Zubenelgenubi', 'Vindemiatrix', 'Sadachbia', 'Sadaltager', 'Sulafat'
]

const GEMINI_TTS_MODELS = [
  { id: 'gemini-3.8-flash-tts', name: 'Gemini 3.8 Flash TTS' },
  { id: 'gemini-3.8-flash-lite-tts', name: 'Gemini 3.8 Flash Lite TTS' },
]

async function fetchElevenLabsModels() {
  try {
    const models = await api.getElevenLabsModels()
    if (models && models.length > 0) {
      elevenLabsModelsList.value = models
    }
  } catch (err) {
    console.error('Failed to fetch ElevenLabs models:', err)
  }
}

onMounted(() => {
  if (localForm.value.provider === 'elevenlabs') {
    fetchElevenLabsModels()
  }
})

watch(() => props.ttsForm, (newVal) => {
  localForm.value = { ...newVal }
}, { deep: true })

const vocalTagsSupported = computed(() => {
  if (localForm.value.provider === 'google') return true
  if (localForm.value.provider === 'elevenlabs' && (localForm.value.selected_model === 'eleven_v3' || localForm.value.selected_model.startsWith('eleven_v4'))) return true
  return false
})

const isCompatible = computed((): boolean => localForm.value.provider === 'custom_openai')

// The OpenAI-compatible provider works without a key (local servers), so it never warns.
const isTtsKeyMissing = computed(() => {
  const provider = localForm.value.provider
  if (provider === 'custom_openai') return false
  return !props.configuredKeys[provider]
})

function formatVoiceLabel(voiceName: string): string {
  const entry = localForm.value.voice_catalog.find((voice: any) => voice.name === voiceName)
  if (!entry) return voiceName
  const detailParts = [entry.gender, entry.description].filter(Boolean)
  if (detailParts.length === 0) return voiceName
  return `${voiceName} (${detailParts.join(', ')})`
}

watch(() => localForm.value.provider, (newProvider) => {
  if (newProvider === 'elevenlabs') {
    fetchElevenLabsModels()
    if (!localForm.value.selected_model.startsWith('eleven_')) {
      localForm.value.selected_model = 'eleven_v4'
    }
  } else if (newProvider === 'google' && !localForm.value.selected_model.startsWith('gemini-')) {
    localForm.value.selected_model = 'gemini-3.8-flash-tts'
  } else if (newProvider === 'custom_openai' && /^(gemini-|eleven_)/.test(localForm.value.selected_model)) {
    localForm.value.selected_model = ''
  }
})

const handleSave = () => {
  emit('save', localForm.value)
}
</script>

<template>
  <div class="space-y-6 animate-fade-in max-w-5xl">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-3xl font-extrabold text-white tracking-tight">Speech Generation (TTS)</h1>
        <p class="text-slate-400 text-sm mt-1">Narration with Gemini, ElevenLabs or any OpenAI-compatible speech server (local or hosted).</p>
      </div>

      <button 
        type="button" 
        @click="handleSave" 
        :disabled="isSubmitting" 
        class="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-blue-900/30 disabled:opacity-50 flex items-center gap-2 self-start sm:self-auto cursor-pointer"
      >
        <i v-if="isSubmitting" class="ra ra-recycle animate-spin"></i>
        <i v-else class="ra ra-save"></i>
        <span>{{ isSubmitting ? 'Tuning...' : 'Save Speech Settings' }}</span>
      </button>
    </div>

    <div class="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-8">
      <!-- API KEY WARNING -->
      <div v-if="isTtsKeyMissing" class="p-6 bg-amber-500/10 border border-amber-500/20 rounded-2xl flex items-start gap-4">
        <div class="p-3 bg-amber-500/20 rounded-xl text-amber-500">
          <i class="ra ra-warning text-xl"></i>
        </div>
        <div>
          <h4 class="text-sm font-bold text-amber-400 uppercase tracking-widest mb-1">API Key Missing</h4>
          <p class="text-xs text-amber-500/70 leading-relaxed">
            No API key found for <strong>{{ ttsForm.provider === 'google' ? 'Google Gemini' : 'ElevenLabs' }}</strong>. 
            Please add your key in the <button @click="emit('switchSection', 'keys')" class="text-amber-400 underline font-bold hover:text-amber-300">Provider Keys</button> section before enabling speech.
          </p>
        </div>
      </div>

      <!-- ENABLED TOGGLE -->
      <div class="flex items-center justify-between p-6 bg-slate-950/50 rounded-2xl border border-blue-500/10">
        <div>
          <h3 class="text-lg font-bold text-blue-400">Enable Text-to-Speech</h3>
          <p class="text-xs text-slate-500">Allow AI-generated narration during gameplay.</p>
        </div>
        <div class="flex items-center gap-6">
          <button 
            v-if="localForm.enabled"
            @click="emit('test', localForm)"
            :disabled="testResults['tts']?.status === 'loading'"
            class="px-4 py-2 bg-blue-600/20 hover:bg-blue-600/40 text-blue-300 text-xs font-bold rounded-lg border border-blue-600/30 transition-all flex items-center gap-2"
          >
            <i class="ra ra-microphone" :class="{'animate-pulse': testResults['tts']?.status === 'loading'}"></i>
            Test Speech
          </button>
          <label class="relative inline-flex items-center cursor-pointer scale-125">
            <input type="checkbox" v-model="localForm.enabled" class="sr-only peer">
            <div class="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600 peer-checked:after:bg-white"></div>
          </label>
        </div>
      </div>

      <div v-if="testResults['tts']" :class="['mx-6 p-4 rounded-xl text-sm font-medium border animate-fade-in', testResults['tts'].status === 'loading' ? 'bg-slate-800 border-slate-700 text-slate-300' : testResults['tts'].status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400']">
        <div class="flex items-center gap-2">
          <div v-if="testResults['tts'].status === 'loading'" class="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div>
          <i v-else :class="testResults['tts'].status === 'success' ? 'ra ra-check' : 'ra ra-warning'"></i>
          {{ testResults['tts'].message }}
        </div>
      </div>

      <div v-if="localForm.enabled" class="space-y-4 p-6 bg-slate-950/50 rounded-2xl border border-blue-500/10 animate-fade-in">
        <h3 class="text-lg font-bold text-blue-400 flex items-center gap-2">
          <i class="ra ra-microphone"></i> Narration Style & Provider
        </h3>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Provider</label>
            <select v-model="localForm.provider" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-blue-500/50">
              <option value="google">Google Cloud TTS</option>
              <option value="elevenlabs">ElevenLabs</option>
              <option value="custom_openai">OpenAI-Compatible (local or hosted)</option>
            </select>
          </div>
          
          <!-- GOOGLE SETTINGS -->
          <template v-if="localForm.provider === 'google'">
            <div class="space-y-2">
              <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Voice</label>
              <select v-model="localForm.selected_voice" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-blue-500/50">
                <option v-for="voice in VOICE_LIST" :key="voice" :value="voice">{{ formatVoiceLabel(voice) }}</option>
              </select>
            </div>
          </template>

          <!-- ELEVENLABS SETTINGS -->
          <template v-if="localForm.provider === 'elevenlabs'">
            <div class="space-y-2">
              <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Narrator Voice</label>
              <ElevenLabsVoiceField
                v-model="localForm.elevenlabs_voice_id"
                input-class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-blue-500/50"
              />
              <p class="text-[11px] text-slate-500">Characters get their own voices from the voice list automatically.</p>
            </div>
          </template>
        </div>

        <!-- OPENAI-COMPATIBLE SETTINGS -->
        <div v-if="isCompatible" class="space-y-3">
          <OpenAICompatibleTtsFields
            v-model:base-url="localForm.custom_openai_url"
            v-model:model="localForm.selected_model"
            v-model:voice="localForm.custom_openai_voice"
            v-model:format="localForm.custom_openai_format"
            v-model:instructions="localForm.custom_openai_instructions"
            id-prefix="admin-tts-compat"
            input-class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-blue-500/50"
          />
          <p class="text-[11px] text-slate-500">
            Characters speak with the voices set under Character Voices (else the narrator voice); vocal tags are removed before synthesis.
          </p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div v-if="!isCompatible" class="space-y-2">
             <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">
               {{ localForm.provider === 'google' ? 'Gemini Model' : 'ElevenLabs Model' }}
             </label>
             <select v-model="localForm.selected_model" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-blue-500/50">
               <template v-if="localForm.provider === 'google'">
                 <option v-for="model in GEMINI_TTS_MODELS" :key="model.id" :value="model.id">{{ model.name }}</option>
               </template>
               <template v-else>
                 <option v-for="model in elevenLabsModelsList" :key="model.model_id" :value="model.model_id">{{ model.name }}</option>
               </template>
             </select>
          </div>
          <div v-if="!isCompatible" class="flex items-center justify-between p-4 bg-slate-900/60 rounded-xl border border-white/5" :class="{'opacity-50': !vocalTagsSupported}">
            <div>
              <div class="text-xs font-bold text-white uppercase tracking-wider">Vocal Tags</div>
              <div class="text-[10px] text-slate-500">
                <template v-if="vocalTagsSupported">Enable emotional markers like [shouting] or (whispering).</template>
                <template v-else><span class="text-amber-500/80">Not supported by this model.</span></template>
              </div>
            </div>
            <label class="relative inline-flex items-center" :class="vocalTagsSupported ? 'cursor-pointer' : 'cursor-not-allowed'">
              <input type="checkbox" v-model="localForm.use_vocal_tags" :disabled="!vocalTagsSupported" class="sr-only peer">
              <div class="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>

          <div v-if="localForm.provider === 'elevenlabs'" class="p-4 bg-slate-900/60 rounded-xl border border-white/5 col-span-1 md:col-span-2">
            <div class="text-xs font-bold text-white uppercase tracking-wider">Streaming</div>
            <div class="text-[10px] text-slate-400 mt-1">
              ElevenLabs always streams: each line starts playing while it is still being generated, and every
              character speaks with their own voice.
            </div>
          </div>

          <div v-if="localForm.provider === 'google' && localForm.selected_model.startsWith('gemini-')" class="flex items-center justify-between p-4 bg-slate-900/60 rounded-xl border border-white/5 col-span-1 md:col-span-2">
            <div class="flex-1">
              <div class="text-xs font-bold text-white uppercase tracking-wider">Streaming API</div>
              <div class="text-[10px] text-slate-400 mt-1 pr-8">
                <strong>Enabled:</strong> Connects directly to Google's streaming API (Server-Sent Events) for faster first-byte audio playback.
                <br/>
                <strong>Disabled:</strong> Standard REST API request.
              </div>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" v-model="localForm.use_streaming" class="sr-only peer">
              <div class="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>

          <div class="flex items-center justify-between p-4 bg-slate-900/60 rounded-xl border border-white/5 col-span-1 md:col-span-2">
            <div class="flex-1">
              <div class="text-xs font-bold text-white uppercase tracking-wider">Start Speech Automatically</div>
              <div class="text-[10px] text-slate-400 mt-1 pr-8">
                <strong>Enabled:</strong> Every game starts with speech on, so the story and characters are read aloud
                as they appear. Players can still switch it off in the game.
                <br/>
                <strong>Disabled:</strong> Speech starts off; players switch it on themselves.
              </div>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" v-model="localForm.auto_speak" class="sr-only peer">
              <div class="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>
        </div>

        <!-- Character voices: per-provider voice ids for the voice list -->
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 bg-slate-900/60 rounded-xl border border-white/5">
          <div>
            <div class="text-xs font-bold text-white uppercase tracking-wider">Character Voices</div>
            <div class="text-[10px] text-slate-400 mt-1 pr-8">
              NPCs and the protagonist get a voice from the voice list. ElevenLabs speaks it directly; for Google TTS and
              OpenAI-compatible servers, assign the matching voices on the Character Voices page. Unassigned voices use the narrator voice.
            </div>
          </div>
          <button
            type="button"
            class="shrink-0 px-4 py-2 rounded-xl border border-blue-500/40 bg-blue-500/10 text-blue-200 text-xs font-bold uppercase tracking-wider hover:bg-blue-500/20 cursor-pointer"
            @click="emit('switchSection', 'voice-map')"
          >
            Character Voices →
          </button>
        </div>

        <!-- Speech rate slider -->
        <div class="space-y-2">
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">
            Playback Speed
            <span class="ml-2 text-blue-400 font-mono normal-case">{{ localForm.speech_rate?.toFixed(2) }}×</span>
          </label>
          <div class="flex items-center gap-3">
            <span class="text-xs text-slate-500 w-10 text-right">0.5×</span>
            <input
              type="range"
              v-model.number="localForm.speech_rate"
              min="0.5"
              max="2.0"
              step="0.05"
              class="flex-1 h-2 rounded-lg appearance-none cursor-pointer bg-slate-800 accent-blue-500"
            />
            <span class="text-xs text-slate-500 w-10">2.0×</span>
          </div>
        </div>
      </div>


    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.4s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
