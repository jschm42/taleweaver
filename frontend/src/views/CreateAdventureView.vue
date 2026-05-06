<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/composables/useApi'
import { configState } from '@/store/config'
import type { CatalogTile } from '@/types'
import { 
  Sparkles, Palette, Flame, Check, Image, 
  ImageIcon, Users, Sword, MapPin, Trophy, AlertTriangle
} from 'lucide-vue-next'

const router = useRouter()

type RuleMode = 'rpg' | 'story' | 'chat'

const form = ref({
  title: '',
  storyIdea: '',
  generate_npc_images: true,
  generate_item_images: true,
  generate_scene_images: true,
  automatic_cover_generation: true,
  clock_enabled: true,
  pacing_minutes: 5,
  rule_enforcement_mode: 'story' as RuleMode,
  selected_style_id: '',
  selected_tone_id: '',
  min_scenes: 3,
  max_scenes: 6,
  award_generation_enabled: true,
  min_awards: 3,
  max_awards: 8,
  language: '',
})

const automatedAssetsEnabled = ref(true)

const assetOptions: Array<{
  key: 'automatic_cover_generation' | 'generate_npc_images' | 'generate_item_images' | 'generate_scene_images'
  label: string
  icon: any
}> = [
  { key: 'automatic_cover_generation', label: 'Cover Art', icon: ImageIcon },
  { key: 'generate_npc_images', label: 'NPC Portraits', icon: Users },
  { key: 'generate_item_images', label: 'Item Icons', icon: Sword },
  { key: 'generate_scene_images', label: 'Scene Visuals', icon: MapPin },
]

const imageStyles = ref<CatalogTile[]>([])
const tones = ref<CatalogTile[]>([])
const isLoadingCatalogs = ref(true)
const isGenerating = ref(false)
const errorMsg = ref('')
const config = ref<any>(null)

const hasLlmConfig = computed(() => configState.hasLlmConfig)
const hasT2iConfig = computed(() => configState.hasT2iConfig);

const isImageLlmConfigured = computed(() => hasLlmConfig.value && hasT2iConfig.value);

const ruleModeHelp = computed(() => {
  if (form.value.rule_enforcement_mode === 'rpg') {
    return 'The Game Master enforces strict rules and mechanics. Best for a challenging RPG experience.'
  }
  if (form.value.rule_enforcement_mode === 'story') {
    return 'Story and atmosphere foreground. RPG elements optional.'
  }
  return 'Story, atmosphere, chatting with NPCs. No strict rules check.'
})

function toggleStyle(id: string) {
  form.value.selected_style_id = id
}

function toggleTone(id: string) {
  form.value.selected_tone_id = id
}

function toggleAllAssets() {
  automatedAssetsEnabled.value = !automatedAssetsEnabled.value
  if (automatedAssetsEnabled.value) {
    form.value.generate_npc_images = true
    form.value.generate_item_images = true
    form.value.generate_scene_images = true
    form.value.automatic_cover_generation = true
  } else {
    form.value.generate_npc_images = false
    form.value.generate_item_images = false
    form.value.generate_scene_images = false
    form.value.automatic_cover_generation = false
  }
}

function toggleAsset(key: 'automatic_cover_generation' | 'generate_npc_images' | 'generate_item_images' | 'generate_scene_images') {
  if (automatedAssetsEnabled.value) return
  form.value[key] = !form.value[key]
}

async function loadCatalogs() {
  isLoadingCatalogs.value = true
  try {
    const data = await api.getSettings()
    config.value = data
    imageStyles.value = data.image_styles_catalog || []
    tones.value = data.tone_catalog || []
    
    if (!form.value.selected_style_id && imageStyles.value.length > 0) {
      form.value.selected_style_id = imageStyles.value[0].id
    }
    if (!form.value.selected_tone_id && tones.value.length > 0) {
      form.value.selected_tone_id = tones.value[0].id
    }
  } catch (error: any) {
    errorMsg.value = error?.message || 'Failed to load configurations.'
  } finally {
    isLoadingCatalogs.value = false
  }
}

import { authState } from '@/store/auth'

function initializeLanguage() {
  if (authState.user?.default_language) {
    form.value.language = authState.user.default_language
  }
}

async function handleCreate() {
  if (!form.value.title.trim()) {
    errorMsg.value = 'Title is required.'
    return
  }

  isGenerating.value = true
  errorMsg.value = ''
  
  const fullStyleObj = imageStyles.value.find(s => s.id === form.value.selected_style_id) || { id: form.value.selected_style_id, name: form.value.selected_style_id }
  const fullToneObj = tones.value.find(t => t.id === form.value.selected_tone_id) || { id: form.value.selected_tone_id, name: form.value.selected_tone_id }

  const payload: any = {
    ...form.value,
    id: crypto.randomUUID(),
    title: form.value.title.trim() || 'Untitled Odyssey',
    original_prompt: form.value.storyIdea.trim(),
    time_per_turn: form.value.pacing_minutes,
    selected_image_styles: form.value.selected_style_id ? [fullStyleObj] : [],
    selected_tone: form.value.selected_tone_id ? fullToneObj : null
  }

  try {
    await api.createAdventure(payload)
    router.push({ name: 'portal', query: { new_id: payload.id, new_title: payload.title, section: 'templates' } })
  } catch (error: any) {
    errorMsg.value = error?.message || 'Failed to create adventure.'
    isGenerating.value = false
  }
}

onMounted(() => {
  void refreshConfig()
  void loadCatalogs()
  initializeLanguage()
})
</script>

<template>
  <div class="h-full min-h-0 overflow-y-auto bg-slate-950 text-slate-200 font-sans p-8 md:p-12">
    <header class="max-w-7xl mx-auto mb-12 flex items-center justify-between">
      <div>
        <h1 class="text-4xl font-black text-white uppercase tracking-tight">New Adventure</h1>
        <p class="text-slate-500 mt-2 tracking-wide text-sm">Weave the parameters of your next odyssey.</p>
      </div>
      <button @click="router.back()" class="px-6 py-3 rounded-xl border border-white/5 hover:bg-white/5 transition-all">Back</button>
    </header>

    <main class="max-w-7xl mx-auto">
      <!-- Error Message -->
      <div v-if="errorMsg" class="mb-8 p-4 rounded-2xl border border-red-500/30 bg-red-500/10 text-red-300 text-sm flex items-center gap-3">
        <div class="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div>
        {{ errorMsg }}
      </div>

      <!-- CRITICAL: No LLM -->
      <div v-if="!hasLlmConfig && configState.isLoaded" class="mb-8 p-6 rounded-2xl border border-red-500/50 bg-red-500/10 flex flex-col md:flex-row items-center justify-between gap-6">
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center text-red-500 text-xl">
            <i class="ra ra-warning"></i>
          </div>
          <div>
            <h3 class="text-red-500 font-black uppercase tracking-widest text-xs mb-1">Intelligence Required</h3>
            <p class="text-slate-400 text-xs">No AI provider is configured for world generation. You cannot weave new realities without a connection.</p>
          </div>
        </div>
        <router-link to="/admin" class="px-6 py-3 rounded-xl bg-red-600 text-white font-black text-xxs uppercase tracking-widest hover:bg-red-500 transition-all whitespace-nowrap">
          Go to Configuration
        </router-link>
      </div>

      <!-- Warning if no image model -->
      <div v-if="hasLlmConfig && !hasT2iConfig && !isLoadingCatalogs" class="mb-8 p-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 text-amber-300 text-sm flex items-center gap-3">
        <div class="w-2 h-2 rounded-full bg-amber-500"></div>
        Warning: No image generation model is configured. You can still generate the adventure, but visual assets will be skipped.
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-10 items-stretch">
        <!-- Configuration Panel (Left) -->
        <div class="flex flex-col h-full space-y-8">
          <div class="flex-1 bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-3xl p-8 space-y-8 overflow-y-auto">
            <!-- Basic Info -->
            <div class="space-y-6">
              <div>
                <label class="block text-xxs font-black text-white/40 uppercase tracking-[0.2em] mb-3">Adventure Title</label>
                <input
                  v-model="form.title"
                  type="text"
                  placeholder="Enter a title..."
                  class="w-full bg-white/5 border border-white/10 rounded-2xl px-6 py-4 text-white focus:border-aether-primary outline-none transition-all placeholder:text-white/10"
                />
              </div>

              <div>
                <label class="block text-xxs font-black text-white/40 uppercase tracking-[0.2em] mb-3">Story Idea & Context</label>
                <textarea
                  v-model="form.storyIdea"
                  rows="4"
                  placeholder="The Weaver will use this to seed the world's history and current conflicts..."
                  class="w-full bg-white/5 border border-white/10 rounded-2xl px-6 py-4 text-white resize-y min-h-[7rem] focus:border-aether-primary outline-none transition-all placeholder:text-white/10"
                ></textarea>
              </div>
            </div>

            <!-- Rule Enforcement -->
            <div class="space-y-4">
              <label class="block text-xxs font-black text-white/40 uppercase tracking-[0.2em]">Rule Enforcement Mode</label>
              <div class="grid grid-cols-3 gap-3">
                <button
                  v-for="mode in ['rpg', 'story', 'chat']"
                  :key="mode"
                  @click="form.rule_enforcement_mode = mode as RuleMode"
                  class="px-4 py-4 rounded-2xl border-2 transition-all flex flex-col items-center gap-1"
                  :class="form.rule_enforcement_mode === mode ? 'border-aether-primary bg-aether-primary/10 text-white' : 'border-white/5 bg-white/5 text-white/40 hover:border-white/10'"
                >
                  <span class="text-xxs font-black uppercase tracking-widest">{{ mode === 'rpg' ? 'RPG (EXPERIMENTAL)' : mode }}</span>
                </button>
              </div>
              <p class="text-xxs text-white/30 uppercase tracking-widest text-center">{{ ruleModeHelp }}</p>
              
              <!-- Experimental Warning -->
              <div v-if="form.rule_enforcement_mode === 'rpg'" class="mt-4 p-5 rounded-2xl border border-amber-500/30 bg-amber-500/5 flex items-start gap-4">
                <div class="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center text-amber-500 shrink-0">
                  <AlertTriangle class="w-5 h-5" />
                </div>
                <div>
                  <h4 class="text-amber-500 font-black uppercase tracking-widest text-xxs mb-1">Experimental System</h4>
                  <p class="text-slate-400 text-xxs leading-relaxed">The RPG mode is currently under heavy development. Deterministic mechanics like combat, attribute checks, and automatic world updates may behave unexpectedly. Use with caution!</p>
                </div>
              </div>
            </div>

            <!-- Target Language -->
            <div class="p-6 bg-cyan-500/5 border border-cyan-500/10 rounded-2xl space-y-4">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-cyan-500/20 flex items-center justify-center text-cyan-400">
                  <Sparkles class="w-5 h-5" />
                </div>
                <span class="text-xs font-black text-white/80 uppercase tracking-widest">Target Generation Language</span>
              </div>
              <div class="grid grid-cols-1 gap-3">
                <select 
                  v-model="form.language"
                  class="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-cyan-400 outline-none transition-all cursor-pointer appearance-none"
                >
                  <option value="">Default (English)</option>
                  <option value="German">Deutsch</option>
                  <option value="English">English</option>
                  <option value="French">Français</option>
                  <option value="Spanish">Español</option>
                  <option value="Italian">Italiano</option>
                  <option value="Japanese">Japanese</option>
                  <option value="Chinese">Chinese</option>
                  <option value="Russian">Russian</option>
                  <option value="Portuguese">Portuguese</option>
                </select>
                <p class="text-xxs text-white/30 uppercase tracking-[0.1em]">The Weaver will generate all names, descriptions, and plot points in this language.</p>
              </div>
            </div>

            <!-- World Pacing & Time -->
            <div class="p-6 bg-emerald-500/5 border border-emerald-500/10 rounded-2xl space-y-6">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center text-emerald-400">
                    <MapPin class="w-5 h-5" />
                  </div>
                  <span class="text-xs font-black text-white/80 uppercase tracking-widest">In-Game Pacing</span>
                </div>
                <div 
                  @click="form.clock_enabled = !form.clock_enabled"
                  :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', form.clock_enabled ? 'bg-emerald-500' : 'bg-slate-700']"
                >
                  <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', form.clock_enabled ? 'left-6' : 'left-1']"></div>
                </div>
              </div>

              <div class="space-y-4" v-if="form.clock_enabled">
                <div class="flex justify-between items-center">
                  <span class="text-xxs font-black text-white/40 uppercase tracking-widest">Pacing (Min/Action)</span>
                  <span class="text-xs font-mono text-emerald-400">{{ form.pacing_minutes }}m</span>
                </div>
                <input 
                  type="range" 
                  v-model.number="form.pacing_minutes" 
                  min="1" 
                  max="30" 
                  class="w-full accent-emerald-500 bg-white/5 h-1.5 rounded-lg appearance-none cursor-pointer"
                />
              </div>
            </div>

            <!-- Asset Toggles -->
            <div class="space-y-6">
              <div class="flex items-center justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-[0.2em]">Automated Assets</label>
                <div 
                  @click="toggleAllAssets"
                  :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', automatedAssetsEnabled ? 'bg-aether-primary' : 'bg-slate-700']"
                >
                  <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', automatedAssetsEnabled ? 'left-6' : 'left-1']"></div>
                </div>
              </div>
              
              <div class="grid grid-cols-2 gap-4">
                <button 
                  v-for="asset in assetOptions"
                  :key="asset.key"
                  :disabled="automatedAssetsEnabled"
                  @click="toggleAsset(asset.key)"
                  class="p-4 rounded-2xl border-2 transition-all flex items-center gap-3 disabled:opacity-40 disabled:cursor-not-allowed"
                  :class="form[asset.key] ? 'border-sky-500/50 bg-sky-500/10 text-white' : 'border-white/5 bg-white/5 text-white/40 hover:border-white/10'"
                >
                  <component :is="asset.icon" class="w-4 h-4" />
                  <span class="text-xxs font-black uppercase tracking-widest">{{ asset.label }}</span>
                </button>
              </div>
            </div>

            <!-- Scene Generation Settings -->
            <div class="p-6 bg-blue-500/5 border border-blue-500/10 rounded-2xl space-y-6">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center text-blue-400">
                  <MapPin class="w-5 h-5" />
                </div>
                <span class="text-xs font-black text-white/80 uppercase tracking-widest">World Complexity (Scenes)</span>
              </div>

              <div class="grid grid-cols-2 gap-8">
                <div class="space-y-3">
                  <div class="flex justify-between">
                    <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min</label>
                    <span class="text-xs font-mono text-blue-400">{{ form.min_scenes }}</span>
                  </div>
                  <input type="range" v-model.number="form.min_scenes" min="1" :max="form.max_scenes" class="w-full accent-blue-500" />
                </div>
                <div class="space-y-3">
                  <div class="flex justify-between">
                    <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max</label>
                    <span class="text-xs font-mono text-blue-400">{{ form.max_scenes }}</span>
                  </div>
                  <input type="range" v-model.number="form.max_scenes" :min="form.min_scenes" max="20" class="w-full accent-blue-500" />
                </div>
              </div>
            </div>

            <!-- Awards Section -->
            <div class="p-6 bg-indigo-500/5 border border-indigo-500/10 rounded-2xl space-y-6">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center text-indigo-400">
                    <Trophy class="w-5 h-5" />
                  </div>
                  <span class="text-xs font-black text-white/80 uppercase tracking-widest">Awards Weaver</span>
                </div>
                <div 
                  @click="form.award_generation_enabled = !form.award_generation_enabled"
                  :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', form.award_generation_enabled ? 'bg-indigo-500' : 'bg-slate-700']"
                >
                  <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', form.award_generation_enabled ? 'left-6' : 'left-1']"></div>
                </div>
              </div>

              <div v-if="form.award_generation_enabled" class="grid grid-cols-2 gap-8">
                <div class="space-y-3">
                  <div class="flex justify-between">
                    <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min</label>
                    <span class="text-xs font-mono text-indigo-400">{{ form.min_awards }}</span>
                  </div>
                  <input type="range" v-model.number="form.min_awards" min="1" :max="form.max_awards" class="w-full accent-indigo-500" />
                </div>
                <div class="space-y-3">
                  <div class="flex justify-between">
                    <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max</label>
                    <span class="text-xs font-mono text-indigo-400">{{ form.max_awards }}</span>
                  </div>
                  <input type="range" v-model.number="form.max_awards" :min="form.min_awards" max="20" class="w-full accent-indigo-500" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Style & Tone Selection (Right) -->
        <div class="flex flex-col gap-8 h-full">
          <!-- Image Style -->
          <div class="flex-1 bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-3xl p-8 flex flex-col min-h-0">
            <div class="flex items-center gap-4 mb-8">
              <div class="w-12 h-12 rounded-2xl bg-indigo-500/20 flex items-center justify-center text-indigo-400">
                <Palette class="w-6 h-6" />
              </div>
              <div>
                <h3 class="text-sm font-black text-white uppercase tracking-[0.2em]">Visual Style</h3>
                <p class="text-xxs text-white/40 uppercase tracking-widest">Select one aesthetic direction</p>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-4 overflow-y-auto pr-2 custom-scrollbar max-h-[416px]">
              <button
                v-for="style in imageStyles"
                :key="style.id"
                @click="toggleStyle(style.id)"
                class="relative h-32 rounded-2xl overflow-hidden border-4 transition-all duration-300 group"
                :class="form.selected_style_id === style.id ? 'border-blue-500 ring-8 ring-blue-500/10' : 'border-transparent hover:border-white/10'"
              >
                <img :src="style.image_url" class="w-full h-full object-cover object-top transition-transform duration-700 group-hover:scale-110" />
                <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
                <div class="absolute bottom-4 left-4 right-4">
                  <p class="text-xxs font-black text-white uppercase tracking-widest">{{ style.name }}</p>
                </div>
              </button>
            </div>
          </div>

          <!-- World Tone -->
          <div class="flex-1 bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-3xl p-8 flex flex-col min-h-0">
            <div class="flex items-center gap-4 mb-8">
              <div class="w-12 h-12 rounded-2xl bg-amber-500/20 flex items-center justify-center text-amber-400">
                <Flame class="w-6 h-6" />
              </div>
              <div>
                <h3 class="text-sm font-black text-white uppercase tracking-[0.2em]">Narrative Tone</h3>
                <p class="text-xxs text-white/40 uppercase tracking-widest">Atmosphere and description style</p>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-4 overflow-y-auto pr-2 custom-scrollbar max-h-[416px]">
              <button
                v-for="tone in tones"
                :key="tone.id"
                @click="toggleTone(tone.id)"
                class="relative h-32 rounded-2xl overflow-hidden border-4 transition-all duration-300 group"
                :class="form.selected_tone_id === tone.id ? 'border-blue-500 ring-8 ring-blue-500/10' : 'border-transparent hover:border-white/10'"
              >
                <img :src="tone.image_url" class="w-full h-full object-cover object-top transition-transform duration-700 group-hover:scale-110" />
                <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
                <div class="absolute bottom-4 left-4 right-4">
                  <p class="text-xxs font-black text-white uppercase tracking-widest">{{ tone.name }}</p>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Action Button (Centered at bottom) -->
      <div class="mt-16 flex flex-col items-center gap-6">
        <button
          @click="handleCreate"
          :disabled="isGenerating || isLoadingCatalogs || !hasLlmConfig"
          class="group relative px-20 py-6 bg-gradient-to-br from-aether-primary to-aether-secondary rounded-3xl font-black text-white shadow-2xl shadow-aether-primary/30 hover:scale-105 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed overflow-hidden"
        >
          <div class="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-500"></div>
          <div class="relative flex items-center gap-4">
            <div v-if="isGenerating" class="w-6 h-6 border-4 border-white/30 border-t-white rounded-full animate-spin"></div>
            <Sparkles v-else class="w-7 h-7" />
            <span class="text-xl tracking-[0.2em]">{{ isGenerating ? 'WEAVING REALITY...' : (!hasLlmConfig ? 'CONFIGURATION REQUIRED' : 'BEGIN WEAVING') }}</span>
          </div>
        </button>
        <p class="text-xxs text-white/20 uppercase tracking-[0.3em]">The process may take a few minutes as the world is manifest</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 8px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.25);
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.45);
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-4px); }
  75% { transform: translateX(4px); }
}
.animate-shake {
  animation: shake 0.2s ease-in-out 0s 2;
}
</style>

