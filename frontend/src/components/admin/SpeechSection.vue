<script setup lang="ts">
import { ref, watch, computed, onMounted, onBeforeUnmount } from 'vue'
import { api } from '@/composables/useApi'

const props = defineProps<{
  ttsForm: any
  configuredKeys: any
  isSubmitting: boolean
  testResults: any
}>()

const emit = defineEmits<{
  (e: 'save', payload: any): void
  (e: 'test'): void
  (e: 'switchSection', section: string): void
}>()

const localForm = ref({ ...props.ttsForm })
const elevenLabsModelsList = ref<Array<{ model_id: string, name: string }>>([])

const DEFAULT_QWEN_MODELS = [
  { id: 'Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice', name: 'Qwen3-TTS 0.6B CustomVoice (Fast & Lightweight)', size_label: '~1.2 GB', is_downloaded: false },
  { id: 'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice', name: 'Qwen3-TTS 1.7B CustomVoice (High Fidelity)', size_label: '~3.4 GB', is_downloaded: false },
  { id: 'Qwen/Qwen3-TTS-12Hz-0.6B-Base', name: 'Qwen3-TTS 0.6B Base', size_label: '~1.2 GB', is_downloaded: false },
  { id: 'Qwen/Qwen3-TTS-12Hz-1.7B-Base', name: 'Qwen3-TTS 1.7B Base', size_label: '~3.4 GB', is_downloaded: false },
]

const DEFAULT_QWEN_VOICES = [
  { name: 'Vivian', gender: 'Female', description: 'Bright, clear narration' },
  { name: 'Serena', gender: 'Female', description: 'Warm, calm storyteller' },
  { name: 'Uncle_Fu', gender: 'Male', description: 'Gravelly, wise elder' },
  { name: 'Dylan', gender: 'Male', description: 'Youthful, energetic' },
  { name: 'Eric', gender: 'Male', description: 'Deep, confident adventurer' },
  { name: 'Ryan', gender: 'Male', description: 'Balanced, crisp narrator' },
  { name: 'Aiden', gender: 'Male', description: 'Heroic, bold delivery' },
  { name: 'Ono_Anna', gender: 'Female', description: 'Expressive, melodic' },
  { name: 'Sohee', gender: 'Female', description: 'Gentle, soothing tone' },
]

const qwenModelsList = ref<Array<any>>([...DEFAULT_QWEN_MODELS])
const qwenVoicesList = ref<Array<any>>([...DEFAULT_QWEN_VOICES])
const qwenDevice = ref<string>('Auto-detect')
const isDownloadingQwen = ref<Record<string, boolean>>({})
const downloadPollTimer = ref<any>(null)

const VOICE_LIST = [
  'Zephyr', 'Puck', 'Charon', 'Kore', 'Fenrir', 'Leda', 'Orus', 'Aoede', 'Callirrhoe',
  'Autonoe', 'Enceladus', 'Iapetus', 'Umbriel', 'Algieba', 'Despina', 'Erinome',
  'Algenib', 'Rasalgethi', 'Laomedeia', 'Achernar', 'Alnilam', 'Schedar', 'Gacrux',
  'Pulcherrima', 'Achird', 'Zubenelgenubi', 'Vindemiatrix', 'Sadachbia', 'Sadaltager'
]

const GEMINI_TTS_MODELS = [
  { id: 'gemini-2.5-flash-preview-tts', name: 'Gemini 2.5 Flash TTS (Preview)' },
  { id: 'gemini-3.1-flash-tts-preview', name: 'Gemini 3.1 Flash TTS (Preview)' },
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

async function fetchQwenInfo() {
  try {
    const data = await api.getQwenModels()
    if (data.models && data.models.length > 0) {
      qwenModelsList.value = data.models
    }
    if (data.voices && data.voices.length > 0) {
      qwenVoicesList.value = data.voices
    }
    if (data.device) {
      qwenDevice.value = data.device
    }
  } catch (err) {
    console.error('Failed to fetch Qwen models from backend:', err)
  }
}

async function handleDownloadQwenModel(modelId: string) {
  isDownloadingQwen.value[modelId] = true
  try {
    await api.downloadQwenModel(modelId)
    startDownloadPolling(modelId)
  } catch (err) {
    console.error('Failed to start model download:', err)
    isDownloadingQwen.value[modelId] = false
  }
}

function startDownloadPolling(modelId: string) {
  if (downloadPollTimer.value) clearInterval(downloadPollTimer.value)
  downloadPollTimer.value = setInterval(async () => {
    try {
      const status = await api.getQwenDownloadStatus(modelId)
      const target = qwenModelsList.value.find(m => m.id === modelId)
      if (target) {
        target.download_status = status.status
        target.download_progress = status.progress
        if (status.status === 'downloaded') {
          target.is_downloaded = true
          isDownloadingQwen.value[modelId] = false
          await fetchQwenInfo()
          clearInterval(downloadPollTimer.value)
        } else if (status.status === 'error') {
          isDownloadingQwen.value[modelId] = false
          clearInterval(downloadPollTimer.value)
        }
      }
    } catch {
      clearInterval(downloadPollTimer.value)
      isDownloadingQwen.value[modelId] = false
    }
  }, 1000)
}

function ensureValidModelAndVoice(form: any) {
  if (!form) return
  if (form.provider === 'qwen') {
    if (!form.selected_model || !form.selected_model.startsWith('Qwen/')) {
      form.selected_model = 'Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice'
    }
    if (!form.selected_voice || !DEFAULT_QWEN_VOICES.some(v => v.name === form.selected_voice)) {
      form.selected_voice = 'Vivian'
    }
  } else if (form.provider === 'elevenlabs') {
    if (!form.selected_model || !form.selected_model.startsWith('eleven_')) {
      form.selected_model = 'eleven_multilingual_v2'
    }
  } else if (form.provider === 'google') {
    if (!form.selected_model || !form.selected_model.startsWith('gemini-')) {
      form.selected_model = 'gemini-2.5-flash-preview-tts'
    }
    if (!form.selected_voice || !VOICE_LIST.includes(form.selected_voice)) {
      form.selected_voice = 'Puck'
    }
  }
}

ensureValidModelAndVoice(localForm.value)

onMounted(() => {
  fetchQwenInfo()
  ensureValidModelAndVoice(localForm.value)
  if (localForm.value.provider === 'elevenlabs') {
    fetchElevenLabsModels()
  }
})

onBeforeUnmount(() => {
  if (downloadPollTimer.value) {
    clearInterval(downloadPollTimer.value)
  }
})

watch(() => props.ttsForm, (newVal) => {
  localForm.value = { ...newVal }
  ensureValidModelAndVoice(localForm.value)
}, { deep: true })

const vocalTagsSupported = computed(() => {
  if (localForm.value.provider === 'google') return true
  if (localForm.value.provider === 'qwen') return true
  if (localForm.value.provider === 'elevenlabs' && localForm.value.selected_model === 'eleven_v3') return true
  return false
})

const isTtsKeyMissing = computed(() => {
  const provider = localForm.value.provider
  if (provider === 'qwen') return false
  return !props.configuredKeys[provider]
})

const selectedQwenModel = computed(() => {
  return qwenModelsList.value.find(m => m.id === localForm.value.selected_model) || qwenModelsList.value[0] || null
})

function formatVoiceLabel(voiceName: string): string {
  const entry = localForm.value.voice_catalog?.find((voice: any) => voice.name === voiceName)
  if (!entry) return voiceName
  const detailParts = [entry.gender, entry.description].filter(Boolean)
  if (detailParts.length === 0) return voiceName
  return `${voiceName} (${detailParts.join(', ')})`
}

watch(() => localForm.value.provider, (newProvider) => {
  ensureValidModelAndVoice(localForm.value)
  if (newProvider === 'elevenlabs') {
    fetchElevenLabsModels()
  } else if (newProvider === 'qwen') {
    fetchQwenInfo()
  }
})

const handleSave = () => {
  emit('save', localForm.value)
}
</script>

<template>
  <div class="space-y-8 animate-fade-in">
    <div>
      <h1 class="text-4xl font-extrabold text-white mb-2">Speech Generation (TTS)</h1>
      <p class="text-slate-400">Configure speech synthesis with Google Cloud, ElevenLabs, or local Qwen3-TTS models.</p>
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
            @click="emit('test')"
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
              <option value="google">Google Cloud TTS (Gemini)</option>
              <option value="elevenlabs">ElevenLabs</option>
              <option value="qwen">Qwen3-TTS (Local AI)</option>
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
              <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">ElevenLabs Voice ID</label>
              <input v-model="localForm.elevenlabs_voice_id" type="text" placeholder="e.g. 21m00Tcm4TlvDq8ikWAM" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-blue-500/50 font-mono" />
            </div>
          </template>

          <!-- QWEN SETTINGS -->
          <template v-if="localForm.provider === 'qwen'">
            <div class="space-y-2">
              <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Speaker Voice</label>
              <select v-model="localForm.selected_voice" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-blue-500/50">
                <option v-for="voice in qwenVoicesList" :key="voice.name" :value="voice.name">
                  {{ voice.name }} ({{ voice.gender }} - {{ voice.description }})
                </option>
              </select>
            </div>
          </template>
        </div>

        <!-- MODEL SELECTION -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-2">
             <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">
               {{ localForm.provider === 'google' ? 'Gemini Model' : localForm.provider === 'elevenlabs' ? 'ElevenLabs Model' : 'Qwen3-TTS Model Variant' }}
             </label>
             <select v-model="localForm.selected_model" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-blue-500/50">
               <template v-if="localForm.provider === 'google'">
                 <option v-for="model in GEMINI_TTS_MODELS" :key="model.id" :value="model.id">{{ model.name }}</option>
               </template>
               <template v-else-if="localForm.provider === 'elevenlabs'">
                 <option v-for="model in elevenLabsModelsList" :key="model.model_id" :value="model.model_id">{{ model.name }}</option>
               </template>
               <template v-else>
                 <option v-for="model in qwenModelsList" :key="model.id" :value="model.id">
                   {{ model.name }} ({{ model.size_label }})
                 </option>
               </template>
             </select>
          </div>

          <div class="flex items-center justify-between p-4 bg-slate-900/60 rounded-xl border border-white/5" :class="{'opacity-50': !vocalTagsSupported}">
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

          <!-- QWEN LOCAL MODEL STATUS & DOWNLOAD MANAGER -->
          <div v-if="localForm.provider === 'qwen'" class="col-span-1 md:col-span-2 p-5 bg-slate-900/90 rounded-2xl border border-blue-500/20 space-y-4">
            <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div>
                <div class="flex items-center gap-2">
                  <span class="text-xs font-bold uppercase tracking-wider text-slate-300">Local Model Status</span>
                  <span 
                    v-if="selectedQwenModel?.is_downloaded" 
                    class="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1"
                  >
                    <i class="ra ra-check"></i> Downloaded ({{ selectedQwenModel.disk_size_formatted }})
                  </span>
                  <span 
                    v-else-if="selectedQwenModel?.download_status === 'downloading'" 
                    class="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-blue-500/20 text-blue-400 border border-blue-500/30 flex items-center gap-1 animate-pulse"
                  >
                    <i class="ra ra-cycle animate-spin"></i> Downloading ({{ selectedQwenModel.download_progress }}%)
                  </span>
                  <span 
                    v-else 
                    class="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center gap-1"
                  >
                    <i class="ra ra-warning"></i> Not Downloaded
                  </span>
                </div>
                <p class="text-xs text-slate-400 mt-1">
                  Target: <span class="font-mono text-slate-300">{{ selectedQwenModel?.name || localForm.selected_model }}</span> 
                  &bull; Hardware: <span class="text-blue-400 font-semibold">{{ qwenDevice || 'Auto-detect' }}</span>
                </p>
              </div>

              <!-- Download Button -->
              <div>
                <button
                  type="button"
                  @click="handleDownloadQwenModel(localForm.selected_model)"
                  :disabled="selectedQwenModel?.download_status === 'downloading' || isDownloadingQwen[localForm.selected_model]"
                  class="px-4 py-2 text-xs font-bold rounded-xl transition-all flex items-center gap-2"
                  :class="selectedQwenModel?.is_downloaded 
                    ? 'bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700' 
                    : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/30'"
                >
                  <i 
                    class="ra" 
                    :class="(selectedQwenModel?.download_status === 'downloading' || isDownloadingQwen[localForm.selected_model]) ? 'ra-cycle animate-spin' : selectedQwenModel?.is_downloaded ? 'ra-refresh' : 'ra-save'"
                  ></i>
                  <span>
                    {{ (selectedQwenModel?.download_status === 'downloading' || isDownloadingQwen[localForm.selected_model]) 
                        ? `Downloading... ${selectedQwenModel?.download_progress || 0}%` 
                        : selectedQwenModel?.is_downloaded 
                        ? 'Re-download Model' 
                        : `Download Model (${selectedQwenModel?.size_label || 'weights'})` }}
                  </span>
                </button>
              </div>
            </div>

            <!-- Progress Bar -->
            <div v-if="selectedQwenModel?.download_status === 'downloading' || isDownloadingQwen[localForm.selected_model]" class="space-y-1">
              <div class="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-blue-500/30">
                <div 
                  class="bg-blue-500 h-full rounded-full transition-all duration-300"
                  :style="{ width: `${selectedQwenModel?.download_progress || 0}%` }"
                ></div>
              </div>
              <div class="flex justify-between text-[10px] text-slate-400">
                <span>Downloading from Hugging Face...</span>
                <span>{{ selectedQwenModel?.download_progress || 0 }}%</span>
              </div>
            </div>
          </div>

          <div class="flex items-center justify-between p-4 bg-slate-900/60 rounded-xl border border-white/5 col-span-1 md:col-span-2">
            <div class="flex-1">
              <div class="text-xs font-bold text-white uppercase tracking-wider">Text Chunking</div>
              <div class="text-[10px] text-slate-400 mt-1 pr-8">
                <strong>Enabled (Recommended):</strong> Breaks text into segments for faster start times and reliability.
                <br/>
                <strong>Disabled:</strong> Sends full text at once for best prosody, but has higher initial delay and may hit length limits.
              </div>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" v-model="localForm.use_text_chunking" class="sr-only peer">
              <div class="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>
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

        <div v-if="localForm.provider === 'google'" class="space-y-2">
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Narration Context (Style Description)</label>
          <textarea 
            v-model="localForm.sample_context" 
            rows="3" 
            placeholder="Describe the voice style and tone..."
            class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white outline-none focus:ring-2 focus:ring-blue-500/50 resize-none font-sans text-sm"
          ></textarea>
          <p class="text-[10px] text-slate-500 italic">Example: "A resonant, authoritative voice. Cinematic, grand, and articulate. The tone is epic and wise..."</p>
        </div>
      </div>

      <button type="button" @click="handleSave" :disabled="isSubmitting" class="w-full py-4 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl transition-all shadow-lg disabled:opacity-50">
         {{ isSubmitting ? 'Tuning...' : 'Update Speech Settings' }}
      </button>
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

