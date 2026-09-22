<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/composables/useApi'
import { configState, refreshConfig } from '@/store/config'
import { authState } from '@/store/auth'
import type { CatalogTile } from '@/types'
import { Sparkles, Palette, Flame, Dices, Loader2, ArrowLeft } from 'lucide-vue-next'
import { CREATE_ADVENTURE_HELP_TEXTS } from '@/constants/createAdventureHelpTexts'

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
  min_scenes: null as number | null,
  max_scenes: null as number | null,
  quest_generation_enabled: true,
  min_quests: null as number | null,
  max_quests: null as number | null,
  min_items: null as number | null,
  max_items: null as number | null,
  container_generation_enabled: true,
  scripts_generation_enabled: false,
  min_containers: null as number | null,
  max_containers: null as number | null,
  text_log_generation_enabled: true,
  min_text_logs: null as number | null,
  max_text_logs: null as number | null,
  can_damage_npcs: false,
  npcs_can_damage_protagonist: false,
  award_generation_enabled: true,
  min_awards: null as number | null,
  max_awards: null as number | null,
  language: '',
  cover_similarity_percent: 50,
  allow_reuse_source_assets: true,
  time_auto: true,
  time_system: 'calendar' as 'calendar' | 'units',
  time_config: null as any,
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
const isSuggestingStoryIdea = ref(false)
const errorMsg = ref('')
const config = ref<any>(null)

const hasLlmConfig = computed(() => configState.hasLlmConfig)
const hasT2iConfig = computed(() => configState.hasT2iConfig)
const selectedToneObject = computed(() => {
  return tones.value.find(t => t.id === form.value.selected_tone_id) || null
})

const resolveStyleIdFromAdventure = (adventure: any): string => {
  const rawStyles = Array.isArray(adventure?.selected_image_styles) ? adventure.selected_image_styles : []
  const firstStyle = rawStyles[0]
  if (!firstStyle) return ''
  if (typeof firstStyle === 'string') return firstStyle
  if (typeof firstStyle === 'object') {
    return String(firstStyle.id || firstStyle.name || '').trim()
  }
  return ''
}

const resolveToneIdFromAdventure = (adventure: any): string => {
  const rawTone = adventure?.selected_tone
  if (!rawTone) return ''
  if (typeof rawTone === 'string') {
    const trimmed = rawTone.trim()
    if (!trimmed) return ''
    if (!trimmed.startsWith('{')) return trimmed
    try {
      const parsed = JSON.parse(trimmed)
      return String(parsed?.id || parsed?.name || '').trim()
    } catch {
      return trimmed
    }
  }
  if (typeof rawTone === 'object') {
    return String(rawTone.id || rawTone.name || '').trim()
  }
  return ''
}

const resolveRuleModeFromAdventure = (adventure: any): RuleMode | null => {
  const rawMode = String(adventure?.rule_enforcement_mode || '').trim().toLowerCase()
  if (!rawMode) return null
  if (rawMode === 'rpg' || rawMode === 'story' || rawMode === 'chat') {
    return rawMode as RuleMode
  }
  // Legacy mode value used in older data snapshots.
  if (rawMode === 'strict') return 'rpg'
  return null
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

function initializeLanguage() {
  if (authState.user?.default_language) {
    form.value.language = authState.user.default_language
  }
}

async function handleCreate() {
  form.value.title = (form.value.title || '').slice(0, 50)

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

  // Enforce combat permissions only if RPG mode is active
  const isRpg = form.value.rule_enforcement_mode === 'rpg'
  const canDamageNpcs = isRpg ? form.value.can_damage_npcs : false
  const npcsCanDamageProtagonist = isRpg ? form.value.npcs_can_damage_protagonist : false

  // Construct structured time_config
  let timeConfigPayload: any = null
  let pacingVal = form.value.pacing_minutes || 5
  let timeSystemVal = form.value.time_system || 'calendar'

  if (!form.value.time_auto && form.value.time_config) {
    const tc = form.value.time_config
    if (form.value.time_system === 'units') {
      timeConfigPayload = {
        time_system: 'units',
        unit_name: tc.unit_name || 'Units',
        initial_units: tc.initial_units ?? 0,
        units_per_turn: tc.units_per_turn ?? 1,
        max_units_per_turn: tc.max_units_per_turn ?? null,
      }
      pacingVal = tc.units_per_turn ?? 1
    } else {
      timeConfigPayload = {
        time_system: 'calendar',
        day_label: tc.day_label || 'Day',
        initial_day: tc.initial_day ?? 1,
        start_time: tc.start_time || '08:00',
        time_format: tc.time_format || '24h',
        pacing_minutes: tc.pacing_minutes ?? 5,
        max_time_per_turn: tc.max_time_per_turn ?? null,
      }
      pacingVal = tc.pacing_minutes ?? 5
    }
  }

  const payload: any = {
    ...form.value,
    id: crypto.randomUUID(),
    title: (form.value.title.trim() || 'Untitled Odyssey').slice(0, 50),
    original_prompt: form.value.storyIdea.trim(),
    clock_enabled: form.value.clock_enabled,
    time_system: timeSystemVal,
    time_per_turn: pacingVal,
    pacing_minutes: pacingVal,
    time_config: timeConfigPayload,
    can_damage_npcs: canDamageNpcs,
    npcs_can_damage_protagonist: npcsCanDamageProtagonist,
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

async function handleSuggestStoryIdea() {
  if (!hasLlmConfig.value) {
    errorMsg.value = 'LLM configuration is required to generate a story idea.'
    return
  }

  isSuggestingStoryIdea.value = true
  errorMsg.value = ''
  try {
    const suggestion = await api.suggestStoryIdea({
      title: form.value.title,
      story_idea: form.value.storyIdea,
      selected_tone: selectedToneObject.value,
      rule_enforcement_mode: form.value.rule_enforcement_mode,
      language: form.value.language || undefined,
    })

    form.value.title = (suggestion.title || '').slice(0, 50)
    form.value.storyIdea = suggestion.story_idea || ''
  } catch (error: any) {
    errorMsg.value = error?.message || 'Failed to generate story idea.'
  } finally {
    isSuggestingStoryIdea.value = false
  }
}

const isSurprising = ref(false)

async function handleSurpriseMe() {
  if (isSurprising.value) return
  if (!hasLlmConfig.value) {
    errorMsg.value = 'LLM configuration is required to generate a surprise preset.'
    return
  }

  isSurprising.value = true
  errorMsg.value = ''
  try {
    const available_tones = tones.value.map(t => t.name || t.id)
    const available_styles = imageStyles.value.map(s => s.id)

    const preset = await api.generateSurprisePreset({
      available_tones,
      available_styles,
      language: form.value.language || undefined,
    })

    if (preset) {
      if (preset.title) form.value.title = preset.title.slice(0, 50)
      if (preset.story_idea) form.value.storyIdea = preset.story_idea

      if (preset.selected_tone) {
        const foundTone = tones.value.find(
          t => t.id.toLowerCase() === preset.selected_tone!.toLowerCase() ||
               (t.name && t.name.toLowerCase() === preset.selected_tone!.toLowerCase())
        )
        form.value.selected_tone_id = foundTone ? foundTone.id : preset.selected_tone
      }

      if (preset.selected_style) {
        const foundStyle = imageStyles.value.find(
          s => s.id.toLowerCase() === preset.selected_style!.toLowerCase() ||
               (s.name && s.name.toLowerCase() === preset.selected_style!.toLowerCase())
        )
        form.value.selected_style_id = foundStyle ? foundStyle.id : preset.selected_style
      }

      if (preset.rule_enforcement_mode) form.value.rule_enforcement_mode = preset.rule_enforcement_mode
      if (preset.generate_scene_images !== undefined) form.value.generate_scene_images = preset.generate_scene_images
      if (preset.generate_npc_images !== undefined) form.value.generate_npc_images = preset.generate_npc_images
      if (preset.generate_item_images !== undefined) form.value.generate_item_images = preset.generate_item_images

      // Time settings
      if (preset.clock_enabled !== undefined) form.value.clock_enabled = preset.clock_enabled
      if (preset.time_system) form.value.time_system = preset.time_system
      if (preset.pacing_minutes !== undefined) form.value.pacing_minutes = preset.pacing_minutes

      // Construct time_config
      if (preset.time_system === 'units') {
        form.value.time_config = {
          time_system: 'units',
          unit_name: preset.unit_name || 'Units',
          initial_units: preset.initial_units ?? 0,
          units_per_turn: preset.units_per_turn ?? 1,
        }
      } else {
        form.value.time_config = {
          time_system: 'calendar',
          day_label: preset.day_label || 'Day',
          initial_day: preset.initial_day ?? 1,
          start_time: preset.start_time || '08:00',
          time_format: preset.time_format || '24h',
          pacing_minutes: preset.pacing_minutes ?? 5,
        }
      }
      form.value.time_auto = false

      // World constraints
      if (preset.min_scenes !== undefined) form.value.min_scenes = preset.min_scenes
      if (preset.max_scenes !== undefined) form.value.max_scenes = preset.max_scenes
      if (preset.min_quests !== undefined) form.value.min_quests = preset.min_quests
      if (preset.max_quests !== undefined) form.value.max_quests = preset.max_quests
    }
  } catch (error: any) {
    errorMsg.value = error?.message || 'Failed to generate surprise preset.'
  } finally {
    isSurprising.value = false
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
      form.value.title = (`(Cover) ${source.title || 'Adventure'}`).slice(0, 50)
    }
    if (!form.value.storyIdea.trim()) {
      form.value.storyIdea = source.original_prompt || source.plot || source.teaser || ''
    }

    const sourceStyleId = resolveStyleIdFromAdventure(source)
    if (sourceStyleId) {
      form.value.selected_style_id = sourceStyleId
    }

    const sourceToneId = resolveToneIdFromAdventure(source)
    if (sourceToneId) {
      form.value.selected_tone_id = sourceToneId
    }

    const sourceRuleMode = resolveRuleModeFromAdventure(source)
    if (sourceRuleMode) {
      form.value.rule_enforcement_mode = sourceRuleMode
    }

    if (source.clock_enabled !== undefined) {
      form.value.clock_enabled = !!source.clock_enabled
    }
    if (source.time_system) {
      form.value.time_system = source.time_system === 'units' ? 'units' : 'calendar'
    }
    if (source.time_config) {
      form.value.time_config = source.time_config
      form.value.time_auto = false
    }

    if (source.scripts_generation_enabled !== undefined) {
      form.value.scripts_generation_enabled = !!source.scripts_generation_enabled
    } else if (Array.isArray(source.scripts) && source.scripts.length > 0) {
      form.value.scripts_generation_enabled = true
    } else if (Array.isArray(source.original_manifest?.scripts) && source.original_manifest.scripts.length > 0) {
      form.value.scripts_generation_enabled = true
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
  <div class="h-full min-h-0 overflow-y-auto bg-slate-950 text-slate-200 font-sans p-4 sm:p-6 md:p-8 lg:p-12">
    <header class="max-w-7xl mx-auto mb-6 sm:mb-10 md:mb-12 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 class="text-2xl sm:text-3xl md:text-4xl font-black text-white uppercase tracking-tight">Generate Adventure</h1>
        <p class="text-slate-500 mt-1 sm:mt-2 tracking-wide text-xs sm:text-sm">Weave the parameters of your next odyssey.</p>
      </div>
      <div class="flex items-center gap-3">
        <button
          type="button"
          :disabled="isSurprising || !hasLlmConfig"
          @click="handleSurpriseMe"
          class="px-4 sm:px-6 py-2.5 sm:py-3 rounded-xl border border-purple-500/40 bg-purple-950/40 hover:bg-purple-900/50 text-purple-300 hover:text-purple-100 font-bold text-xs sm:text-sm uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg shadow-purple-950/30 transition-all hover:scale-[1.02] active:scale-95 disabled:opacity-50"
          title="Randomly pre-fill the entire adventure configuration using the world-gen LLM"
        >
          <Dices v-if="!isSurprising" class="w-4 h-4 text-purple-400" />
          <Loader2 v-else class="w-4 h-4 text-purple-400 animate-spin" />
          <span>{{ isSurprising ? 'Weaving Surprise...' : 'Surprise Me' }}</span>
        </button>

        <button
          type="button"
          @click="router.back()"
          class="flex items-center gap-2 px-4 sm:px-5 py-2.5 sm:py-3 rounded-xl bg-slate-900/80 hover:bg-slate-800 border border-white/10 hover:border-white/25 text-slate-300 hover:text-white font-bold text-xs sm:text-sm uppercase tracking-wider transition-all duration-200 shadow-md shadow-black/30 group active:scale-95"
          title="Return to previous page"
        >
          <ArrowLeft class="w-4 h-4 text-slate-400 group-hover:text-white group-hover:-translate-x-0.5 transition-all" />
          <span>Back</span>
        </button>
      </div>
    </header>

    <main class="max-w-7xl mx-auto">
      <AdventureStatusAlerts
        :error-msg="errorMsg"
        :has-llm-config="hasLlmConfig"
        :has-t2i-config="hasT2iConfig"
        :is-loading-catalogs="isLoadingCatalogs"
      />

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 md:gap-8 lg:gap-10 items-stretch">
        <!-- Configuration Panel (Left) -->
        <div class="flex flex-col h-full space-y-6 md:space-y-8">
          <div class="flex-1 bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-2xl md:rounded-3xl p-4 sm:p-6 md:p-8 space-y-6 md:space-y-8 overflow-y-auto">
            <section v-if="isCoverMode" class="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 sm:p-5 space-y-4">
              <div>
                <p class="text-[10px] font-black uppercase tracking-[0.2em] text-amber-300">Cover Source</p>
                <h3 class="text-base sm:text-lg font-black text-white mt-1">
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

              <label class="flex items-center justify-between gap-3 sm:gap-4 p-3 rounded-xl border border-white/10 bg-black/20">
                <span class="text-xs font-bold text-slate-200">Allow to use old assets if they fit the new story.</span>
                <input v-model="form.allow_reuse_source_assets" type="checkbox" class="h-4 w-4 shrink-0" />
              </label>

              <label class="flex items-center justify-between gap-3 sm:gap-4 p-3 rounded-xl border border-white/10 bg-black/20 cursor-pointer hover:border-amber-500/30 transition-all">
                <div class="flex flex-col gap-0.5">
                  <span class="text-xs font-bold text-slate-200">Generate Event Scripts</span>
                  <span class="text-[11px] text-slate-400">
                    Instructs the World-Builder to generate deterministic Python event scripts (puzzles, traps, scene logic) for this cover adventure.
                  </span>
                </div>
                <input v-model="form.scripts_generation_enabled" type="checkbox" class="h-4 w-4 shrink-0 accent-amber-400 cursor-pointer" />
              </label>
            </section>

            <AdventureBasicInfo
              v-model="form"
              :is-suggesting-story-idea="isSuggestingStoryIdea"
              :can-suggest-story-idea="hasLlmConfig"
              @suggest-story-idea="handleSuggestStoryIdea"
            />

            <AdventureGameSettings
              v-model="form"
            />
          </div>
        </div>

        <!-- Style & Tone Selection (Right) -->
        <div class="flex flex-col gap-6 md:gap-8 h-full">
          <AdventureAssetSettings
            v-model="form"
          />

          <AdventureCatalogSelector
            title="Visual Style"
            subtitle="Select one aesthetic direction"
            :icon="Palette"
            :items="imageStyles"
            :selected-id="form.selected_style_id"
            accent-color-class="bg-indigo-500/20 text-indigo-400"
            :help-text="CREATE_ADVENTURE_HELP_TEXTS.visualStyle"
            @select="id => form.selected_style_id = id"
          />

          <AdventureCatalogSelector
            title="Narrative Tone"
            subtitle="Atmosphere and description style"
            :icon="Flame"
            :items="tones"
            :selected-id="form.selected_tone_id"
            accent-color-class="bg-amber-500/20 text-amber-400"
            :help-text="CREATE_ADVENTURE_HELP_TEXTS.narrativeTone"
            @select="id => form.selected_tone_id = id"
          />
        </div>
      </div>

      <!-- Action Button (Centered at bottom) -->
      <div class="mt-10 md:mt-16 flex flex-col items-center gap-4 md:gap-6 px-2">
        <button
          @click="handleCreate"
          :disabled="isGenerating || isLoadingCatalogs || !hasLlmConfig"
          class="group relative w-full sm:w-auto px-6 sm:px-12 md:px-20 py-4 sm:py-5 md:py-6 bg-gradient-to-br from-aether-primary to-aether-secondary rounded-2xl md:rounded-3xl font-black text-white shadow-2xl shadow-aether-primary/30 hover:scale-105 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed overflow-hidden"
        >
          <div class="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-500"></div>
          <div class="relative flex items-center justify-center gap-3 md:gap-4">
            <div v-if="isGenerating" class="w-5 h-5 md:w-6 md:h-6 border-4 border-white/30 border-t-white rounded-full animate-spin"></div>
            <Sparkles v-else class="w-5 h-5 md:w-7 md:h-7" />
            <span class="text-sm sm:text-base md:text-xl tracking-[0.2em] text-center">{{ isGenerating ? 'WEAVING REALITY...' : (!hasLlmConfig ? 'CONFIGURATION REQUIRED' : 'BEGIN WEAVING') }}</span>
          </div>
        </button>
        <p class="text-xxs text-white/20 uppercase tracking-[0.3em] text-center px-2">The process may take a few minutes as the world is manifest</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* No specific styles needed here as they are moved to components or use tailwind */
</style>

