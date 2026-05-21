<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/composables/useApi'
import { configState, refreshConfig } from '@/store/config'
import { authState } from '@/store/auth'
import type { CatalogTile } from '@/types'
import { Sparkles, Palette, Flame } from 'lucide-vue-next'

// Components
import AdventureStatusAlerts from '@/components/create-adventure/AdventureStatusAlerts.vue'
import AdventureBasicInfo from '@/components/create-adventure/AdventureBasicInfo.vue'
import AdventureGameSettings from '@/components/create-adventure/AdventureGameSettings.vue'
import AdventureAssetSettings from '@/components/create-adventure/AdventureAssetSettings.vue'
import AdventureCatalogSelector from '@/components/create-adventure/AdventureCatalogSelector.vue'

const router = useRouter()
const route = useRoute()

type RuleMode = 'rpg' | 'story' | 'chat'

const form = ref({
  title: '',
  storyIdea: '',
  generate_npc_images: true,
  generate_item_images: true,
  generate_scene_images: true,
  automatic_npc_voice_assignment: true,
  automatic_cover_generation: true,
  clock_enabled: true,
  pacing_minutes: 5,
  rule_enforcement_mode: 'story' as RuleMode,
  selected_style_id: '',
  selected_tone_id: '',
  min_scenes: 3,
  max_scenes: 6,
  container_generation_enabled: true,
  max_containers: 8,
  can_damage_npcs: true,
  npcs_can_damage_protagonist: true,
  award_generation_enabled: true,
  min_awards: 3,
  max_awards: 8,
  language: '',
  cover_similarity_percent: 50,
  allow_reuse_source_assets: true,
})

const sourceAdventure = ref<any | null>(null)
const isLoadingCoverSource = ref(false)
const coverSourceId = computed(() => {
  const raw = route.query.cover_from
  return typeof raw === 'string' && raw.trim() ? raw.trim() : ''
})
const isCoverMode = computed(() => !!coverSourceId.value)

const imageStyles = ref<CatalogTile[]>([])
const tones = ref<CatalogTile[]>([])
const isLoadingCatalogs = ref(true)
const isGenerating = ref(false)
const errorMsg = ref('')
const config = ref<any>(null)

const hasLlmConfig = computed(() => configState.hasLlmConfig)
const hasT2iConfig = computed(() => configState.hasT2iConfig)

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
  if (isCoverMode.value && !sourceAdventure.value) {
    errorMsg.value = 'Cover source adventure could not be loaded.'
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
    selected_tone: form.value.selected_tone_id ? fullToneObj : null,
    cover_source_adventure_id: isCoverMode.value ? coverSourceId.value : undefined,
    cover_source_adventure_name: isCoverMode.value ? (sourceAdventure.value?.title || undefined) : undefined,
    cover_similarity_percent: isCoverMode.value ? form.value.cover_similarity_percent : undefined,
    allow_reuse_source_assets: isCoverMode.value ? form.value.allow_reuse_source_assets : undefined,
  }

  try {
    await api.createAdventure(payload)
    router.push({ name: 'portal', query: { new_id: payload.id, new_title: payload.title, section: 'templates' } })
  } catch (error: any) {
    const rawMessage = error?.message || 'Failed to create adventure.'
    errorMsg.value = rawMessage.startsWith('API 409:')
      ? rawMessage.replace(/^API 409:\s*/, '')
      : rawMessage
    isGenerating.value = false
  }
}

async function loadCoverSource() {
  if (!isCoverMode.value) {
    sourceAdventure.value = null
    return
  }

  isLoadingCoverSource.value = true
  try {
    const source = await api.getAdventure(coverSourceId.value)
    sourceAdventure.value = source

    if (!form.value.title.trim()) {
      form.value.title = `(Cover) ${source.title || 'Adventure'}`
    }
    if (!form.value.storyIdea.trim()) {
      form.value.storyIdea = source.original_prompt || source.plot || source.teaser || ''
    }
  } catch (error: any) {
    sourceAdventure.value = null
    errorMsg.value = error?.message || 'Failed to load source adventure for cover mode.'
  } finally {
    isLoadingCoverSource.value = false
  }
}

onMounted(() => {
  void refreshConfig()
  void loadCatalogs()
  initializeLanguage()
  void loadCoverSource()
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
      <AdventureStatusAlerts 
        :error-msg="errorMsg"
        :has-llm-config="hasLlmConfig"
        :has-t2i-config="hasT2iConfig"
        :is-loading-catalogs="isLoadingCatalogs"
      />

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-10 items-stretch">
        <!-- Configuration Panel (Left) -->
        <div class="flex flex-col h-full space-y-8">
          <div class="flex-1 bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-3xl p-8 space-y-8 overflow-y-auto">
            <section v-if="isCoverMode" class="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5 space-y-4">
              <div>
                <p class="text-[10px] font-black uppercase tracking-[0.2em] text-amber-300">Cover Source</p>
                <h3 class="text-lg font-black text-white mt-1">
                  {{ isLoadingCoverSource ? 'Loading source adventure...' : (sourceAdventure?.title || 'Unknown source') }}
                </h3>
                <p class="text-xs text-slate-300 mt-2 leading-relaxed whitespace-pre-wrap">
                  {{ sourceAdventure?.teaser || sourceAdventure?.original_prompt || sourceAdventure?.plot || 'No source description available.' }}
                </p>
              </div>

              <div class="space-y-2">
                <div class="flex items-center justify-between">
                  <label class="text-xs font-black uppercase tracking-widest text-slate-200">Similarity</label>
                  <span class="text-xs font-black text-amber-300">{{ form.cover_similarity_percent }}%</span>
                </div>
                <input
                  v-model.number="form.cover_similarity_percent"
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  class="w-full accent-amber-400"
                />
                <p class="text-[11px] text-slate-400">0% = freely inspired, 100% = very close to original.</p>
              </div>

              <label class="flex items-center justify-between gap-4 p-3 rounded-xl border border-white/10 bg-black/20">
                <span class="text-xs font-bold text-slate-200">Allow to use old assets if they fit the new story.</span>
                <input v-model="form.allow_reuse_source_assets" type="checkbox" class="h-4 w-4" />
              </label>
            </section>

            <AdventureBasicInfo 
              v-model="form"
            />

            <AdventureGameSettings 
              v-model="form"
            />

            <AdventureAssetSettings 
              v-model="form"
            />
          </div>
        </div>

        <!-- Style & Tone Selection (Right) -->
        <div class="flex flex-col gap-8 h-full">
          <AdventureCatalogSelector 
            title="Visual Style"
            subtitle="Select one aesthetic direction"
            :icon="Palette"
            :items="imageStyles"
            :selected-id="form.selected_style_id"
            accent-color-class="bg-indigo-500/20 text-indigo-400"
            @select="id => form.selected_style_id = id"
          />

          <AdventureCatalogSelector 
            title="Narrative Tone"
            subtitle="Atmosphere and description style"
            :icon="Flame"
            :items="tones"
            :selected-id="form.selected_tone_id"
            accent-color-class="bg-amber-500/20 text-amber-400"
            @select="id => form.selected_tone_id = id"
          />
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
/* No specific styles needed here as they are moved to components or use tailwind */
</style>

