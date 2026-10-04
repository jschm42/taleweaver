<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/composables/useApi'
import { configState, refreshConfig } from '@/store/config'
import { authState } from '@/store/auth'
import type { CatalogTile } from '@/types'
import { Sparkles, Palette, Flame, Dices, Loader2, ArrowLeft, Sliders, Info, AlertTriangle, CheckCircle2 } from 'lucide-vue-next'
import { CREATE_ADVENTURE_HELP_TEXTS } from '@/constants/createAdventureHelpTexts'

// Components
import AdventureStatusAlerts from '@/components/create-adventure/AdventureStatusAlerts.vue'
import AdventureBasicInfo from '@/components/create-adventure/AdventureBasicInfo.vue'
import AdventureGameSettings from '@/components/create-adventure/AdventureGameSettings.vue'
import AdventureAssetSettings from '@/components/create-adventure/AdventureAssetSettings.vue'
import AdventureCatalogSelector from '@/components/create-adventure/AdventureCatalogSelector.vue'
import AdventureRuleModeSelector from '@/components/create-adventure/AdventureRuleModeSelector.vue'
import AdventureWorldConstraints from '@/components/create-adventure/AdventureWorldConstraints.vue'

const router = useRouter()
const route = useRoute()

type RuleMode = 'rpg' | 'story' | 'chat'

const form = ref({
  title: '',
  storyIdea: '',
  generation_strictness: 'creative' as 'creative' | 'strict',
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
  scripts_generation_enabled: true,
  min_sequences: null as number | null,
  max_sequences: null as number | null,
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

const generatorMode = ref<'simple' | 'advanced'>(
  (localStorage.getItem('tw_generator_mode') as 'simple' | 'advanced') || 'simple'
)

function setGeneratorMode(mode: 'simple' | 'advanced') {
  generatorMode.value = mode
  localStorage.setItem('tw_generator_mode', mode)
  if (mode === 'simple') {
    // In Simple mode: activate scripting engine, auto pacing, auto density/bounds
    form.value.scripts_generation_enabled = true
    form.value.time_auto = true
    form.value.min_scenes = null
    form.value.max_scenes = null
    form.value.min_items = null
    form.value.max_items = null
    form.value.min_quests = null
    form.value.max_quests = null
    form.value.min_sequences = null
    form.value.max_sequences = null
    form.value.min_containers = null
    form.value.max_containers = null
    form.value.min_text_logs = null
    form.value.max_text_logs = null
    form.value.min_awards = null
    form.value.max_awards = null
    form.value.quest_generation_enabled = true
    form.value.container_generation_enabled = true
    form.value.text_log_generation_enabled = true
    form.value.award_generation_enabled = true
    form.value.generate_npc_images = true
    form.value.generate_item_images = true
    form.value.generate_scene_images = true
    form.value.automatic_cover_generation = true
    form.value.automatic_npc_voice_assignment = true
    form.value.generation_strictness = 'creative'
  }
}

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

  if (generatorMode.value === 'simple') {
    form.value.scripts_generation_enabled = true
    form.value.time_auto = true
    if (!form.value.storyIdea.trim()) {
      errorMsg.value = 'Please provide a concept prompt for your adventure.'
      return
    }
  }

  if (!form.value.title.trim()) {
    if (form.value.storyIdea.trim()) {
      const clean = form.value.storyIdea.trim().replace(/^(\[.*?\]|\W)+/, '')
      const firstLine = clean.split('\n')[0].replace(/[.!?].*$/, '')
      const words = firstLine.split(/\s+/).slice(0, 5).join(' ')
      form.value.title = words.slice(0, 45) || 'A New Adventure'
    } else {
      errorMsg.value = 'Title is required.'
      return
    }
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

  let promptStr = form.value.storyIdea.trim()
  let parsedSequences = undefined

  // Parse [Sequence] tags
  const seqRegex = /\[Sequence[\s:]*\d*\]/i
  if (seqRegex.test(promptStr)) {
    const blocks = promptStr.split(new RegExp('\\[Sequence[\\s:]*\\d*\\]', 'ig'))
    const sequences = []
    promptStr = blocks[0].trim()

    for (let i = 1; i < blocks.length; i++) {
      if (sequences.length >= 15) break
      const block = blocks[i].trim()
      const lines = block.split('\n')
      const title = lines[0].trim() || `Sequence ${i}`
      const description = lines.slice(1).join('\n').trim() || 'Follow the sequence blueprint.'

      sequences.push({
        id: crypto.randomUUID(),
        order: i,
        title: title,
        description: description.slice(0, 500),
        walkthrough: description,
        end_condition: 'Complete the sequence objectives.',
        exp_reward: 100,
      })
    }
    if (sequences.length > 0) {
      parsedSequences = sequences
    }
  }

  const payload: any = {
    ...form.value,
    id: crypto.randomUUID(),
    title: (form.value.title.trim() || 'Untitled Odyssey').slice(0, 50),
    original_prompt: promptStr,
    sequences: parsedSequences,
    generation_strictness: form.value.generation_strictness,
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
  <div class="h-full min-h-0 overflow-y-auto bg-slate-950 text-slate-200 font-sans p-3 sm:p-5 md:p-6 lg:p-8">
    <header class="max-w-7xl mx-auto mb-4 sm:mb-6 md:mb-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 class="text-xl sm:text-2xl md:text-3xl font-black text-white uppercase tracking-tight">Generate Adventure</h1>
        <p class="text-slate-500 mt-0.5 sm:mt-1 tracking-wide text-xs sm:text-sm">Weave the parameters of your next odyssey.</p>
      </div>
      <div class="flex items-center gap-2.5 sm:gap-3">
        <!-- Mode Switcher -->
        <div class="inline-flex p-1 rounded-xl bg-slate-900/90 border border-white/10 shadow-md">
          <button
            type="button"
            @click="setGeneratorMode('simple')"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-black uppercase tracking-wider transition-all cursor-pointer"
            :class="generatorMode === 'simple'
              ? 'bg-gradient-to-r from-aether-primary to-cyan-500 text-white shadow'
              : 'text-slate-400 hover:text-white hover:bg-white/5'"
          >
            <Sparkles class="w-3.5 h-3.5" />
            <span>Simple</span>
          </button>
          <button
            type="button"
            @click="setGeneratorMode('advanced')"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-black uppercase tracking-wider transition-all cursor-pointer"
            :class="generatorMode === 'advanced'
              ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow'
              : 'text-slate-400 hover:text-white hover:bg-white/5'"
          >
            <Sliders class="w-3.5 h-3.5" />
            <span>Advanced</span>
          </button>
        </div>

        <button
          type="button"
          :disabled="isSurprising || !hasLlmConfig"
          @click="handleSurpriseMe"
          class="px-3.5 sm:px-5 py-2 sm:py-2.5 rounded-xl border border-purple-500/40 bg-purple-950/40 hover:bg-purple-900/50 text-purple-300 hover:text-purple-100 font-bold text-xs sm:text-sm uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg shadow-purple-950/30 transition-all hover:scale-[1.02] active:scale-95 disabled:opacity-50"
          title="Randomly pre-fill the entire adventure configuration using the world-gen LLM"
        >
          <Dices v-if="!isSurprising" class="w-4 h-4 text-purple-400" />
          <Loader2 v-else class="w-4 h-4 text-purple-400 animate-spin" />
          <span>{{ isSurprising ? 'Weaving Surprise...' : 'Surprise Me' }}</span>
        </button>

        <button
          type="button"
          @click="router.back()"
          class="flex items-center gap-2 px-3.5 sm:px-4 py-2 sm:py-2.5 rounded-xl bg-slate-900/80 hover:bg-slate-800 border border-white/10 hover:border-white/25 text-slate-300 hover:text-white font-bold text-xs sm:text-sm uppercase tracking-wider transition-all duration-200 shadow-md shadow-black/30 group active:scale-95"
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

      <!-- ================= SIMPLE MODE VIEW ================= -->
      <div v-if="generatorMode === 'simple'" class="space-y-4 sm:space-y-6 max-w-5xl mx-auto">
        <!-- Helpful Intelligence / Visuals Provider Alerts -->
        <div v-if="!hasLlmConfig && configState.isLoaded" class="p-4 sm:p-5 rounded-2xl border border-rose-500/40 bg-rose-500/10 text-rose-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg">
          <div class="flex items-start sm:items-center gap-3">
            <div class="w-9 h-9 rounded-xl bg-rose-500/20 border border-rose-500/30 flex items-center justify-center text-rose-400 shrink-0">
              <AlertTriangle class="w-5 h-5" />
            </div>
            <div>
              <h4 class="text-xs sm:text-sm font-black uppercase tracking-wider text-rose-300">Intelligence Provider Required</h4>
              <p class="text-xs text-slate-300 mt-0.5">TaleWeaver needs an active LLM (such as Google Gemini, OpenAI GPT, Anthropic Claude, or local Ollama) to weave plotlines, characters, and quests.</p>
            </div>
          </div>
          <router-link to="/admin" class="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-black uppercase tracking-wider whitespace-nowrap text-center transition-all shrink-0">
            Configure LLM
          </router-link>
        </div>

        <div v-else-if="hasLlmConfig && !hasT2iConfig && !isLoadingCatalogs" class="p-3.5 sm:p-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 text-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div class="flex items-start sm:items-center gap-3">
            <div class="w-8 h-8 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0">
              <Info class="w-4 h-4" />
            </div>
            <div>
              <h4 class="text-xs sm:text-sm font-black uppercase tracking-wider text-amber-300">Visuals Model Not Configured</h4>
              <p class="text-xs text-slate-300 mt-0.5">No image generation model is active in Admin. You can still weave your adventure; scenes and NPCs will use atmospheric style fallbacks.</p>
            </div>
          </div>
          <router-link to="/admin" class="px-3.5 py-1.5 rounded-xl border border-amber-500/40 bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 text-xs font-bold uppercase tracking-wider whitespace-nowrap text-center transition-all shrink-0">
            Configure Visuals
          </router-link>
        </div>

        <!-- 1. Concept Prompt Card -->
        <div class="bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-2xl md:rounded-3xl p-4 sm:p-6 space-y-4">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
            <div>
              <div class="flex items-center gap-2">
                <span class="text-[10px] font-black uppercase tracking-[0.2em] text-cyan-400">Step 1</span>
                <span class="text-xs sm:text-sm font-black text-white uppercase tracking-wider">Concept Blueprint</span>
              </div>
              <p class="text-xs text-slate-400 mt-0.5">Enter a concept prompt describing the world, setting, heroes, or conflict.</p>
            </div>

            <button
              v-if="hasLlmConfig"
              type="button"
              :disabled="isSuggestingStoryIdea"
              @click="handleSuggestStoryIdea"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 text-xs font-bold transition-all active:scale-95 disabled:opacity-50 self-start sm:self-auto cursor-pointer"
              title="Use LLM to generate an inspiring concept"
            >
              <Sparkles class="w-3.5 h-3.5" :class="{ 'animate-spin': isSuggestingStoryIdea }" />
              <span>{{ isSuggestingStoryIdea ? 'Inspiring...' : 'Inspire Idea' }}</span>
            </button>
          </div>

          <textarea
            v-model="form.storyIdea"
            rows="5"
            class="w-full bg-slate-950/80 border border-slate-800 focus:border-cyan-500/80 rounded-xl p-3.5 sm:p-4 text-xs sm:text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 transition-all resize-y custom-scrollbar"
            placeholder="e.g. A forgotten star observatory buried beneath a glacial mountain peak. An ancient mechanical astrolabe has reawakened and started transmitting coordinates across the stars..."
          ></textarea>

          <div class="flex flex-col sm:flex-row sm:items-center gap-2.5 pt-2 border-t border-white/5">
            <label class="text-xs font-bold text-slate-400 whitespace-nowrap">Adventure Title (Optional):</label>
            <input
              v-model="form.title"
              type="text"
              maxlength="50"
              class="flex-1 bg-slate-950/60 border border-slate-800 focus:border-cyan-500/80 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none transition-all"
              placeholder="Leave blank to automatically derive from your concept"
            />
          </div>
        </div>

        <!-- 2. Game Mode Selector (RPG, Story, Chat) -->
        <div class="bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-2xl md:rounded-3xl p-4 sm:p-6 space-y-3">
          <div>
            <span class="text-[10px] font-black uppercase tracking-[0.2em] text-cyan-400">Step 2</span>
            <h3 class="text-xs sm:text-sm font-black text-white uppercase tracking-wider mt-0.5">Game Mode</h3>
            <p class="text-xs text-slate-400 mt-0.5">Select how mechanics and narrative rules are enforced during play.</p>
          </div>
          <AdventureRuleModeSelector
            :model-value="form.rule_enforcement_mode"
            @update:model-value="form.rule_enforcement_mode = $event"
          />
        </div>

        <!-- 3. Image Style & Narrative Tone Catalogs -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
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

        <!-- Engine & Auto Info Footer Banner -->
        <div class="p-3.5 rounded-2xl bg-slate-900/60 border border-white/5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
          <div class="flex items-center gap-2 text-emerald-400 font-bold">
            <CheckCircle2 class="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Deterministic Python Scripting Engine Active</span>
          </div>
          <span class="text-slate-500 text-[11px]">
            Asset density, time pacing, quests, and containers will automatically adapt to your prompt.
          </span>
        </div>
      </div>

      <!-- ================= ADVANCED MODE VIEW (TWO-COLUMN BALANCED) ================= -->
      <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 lg:gap-8 items-start">
        <!-- Configuration Panel (Left / Column 1) -->
        <div class="flex flex-col h-full space-y-4 sm:space-y-6">
          <div class="bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-2xl md:rounded-3xl p-3.5 sm:p-5 md:p-6 space-y-4 sm:space-y-6">
            <section v-if="isCoverMode" class="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-3.5 sm:p-4 space-y-3.5">
              <div>
                <p class="text-[10px] font-black uppercase tracking-[0.2em] text-amber-300">Cover Source</p>
                <h3 class="text-sm sm:text-base font-black text-white mt-1">
                  {{ isLoadingCoverSource ? 'Loading source adventure...' : (sourceAdventure?.title || 'Unknown source') }}
                </h3>
                <p class="text-xs text-slate-300 mt-1.5 leading-relaxed whitespace-pre-wrap">
                  {{ sourceAdventure?.teaser || sourceAdventure?.original_prompt || sourceAdventure?.plot || 'No source description available.' }}
                </p>
              </div>

              <div class="space-y-1.5">
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
                <p class="text-[10px] text-slate-400">0% = freely inspired, 100% = very close to original.</p>
              </div>

              <label class="flex items-center justify-between gap-3 p-2.5 sm:p-3 rounded-xl border border-white/10 bg-black/20">
                <span class="text-xs font-bold text-slate-200">Allow to use old assets if they fit the new story.</span>
                <input v-model="form.allow_reuse_source_assets" type="checkbox" class="h-4 w-4 shrink-0" />
              </label>

              <label class="flex items-center justify-between gap-3 p-2.5 sm:p-3 rounded-xl border border-white/10 bg-black/20 cursor-pointer hover:border-amber-500/30 transition-all">
                <div class="flex flex-col gap-0.5">
                  <span class="text-xs font-bold text-slate-200">Generate Event Scripts</span>
                  <span class="text-[10px] text-slate-400">
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

        <!-- Style, Constraints & Asset Settings (Right / Column 2) -->
        <div class="flex flex-col gap-4 sm:gap-6">
          <AdventureAssetSettings
            v-model="form"
          />

          <!-- Min/Max Asset Counts Configuration Panel (Moved to Column 2 for balanced column heights) -->
          <AdventureWorldConstraints
            :min-scenes="form.min_scenes"
            :max-scenes="form.max_scenes"
            :min-items="form.min_items"
            :max-items="form.max_items"
            :quest-generation-enabled="form.quest_generation_enabled"
            :min-quests="form.min_quests"
            :max-quests="form.max_quests"
            :min-sequences="form.min_sequences"
            :max-sequences="form.max_sequences"
            :container-generation-enabled="form.container_generation_enabled"
            :min-containers="form.min_containers"
            :max-containers="form.max_containers"
            :text-log-generation-enabled="form.text_log_generation_enabled"
            :min-text-logs="form.min_text_logs"
            :max-text-logs="form.max_text_logs"
            :award-generation-enabled="form.award_generation_enabled"
            :min-awards="form.min_awards"
            :max-awards="form.max_awards"
            :scripts-generation-enabled="form.scripts_generation_enabled ?? true"
            @update:min-scenes="form.min_scenes = $event"
            @update:max-scenes="form.max_scenes = $event"
            @update:min-items="form.min_items = $event"
            @update:max-items="form.max_items = $event"
            @update:quest-generation-enabled="form.quest_generation_enabled = $event"
            @update:min-quests="form.min_quests = $event"
            @update:max-quests="form.max_quests = $event"
            @update:min-sequences="form.min_sequences = $event"
            @update:max-sequences="form.max_sequences = $event"
            @update:container-generation-enabled="form.container_generation_enabled = $event"
            @update:min-containers="form.min_containers = $event"
            @update:max-containers="form.max_containers = $event"
            @update:text-log-generation-enabled="form.text_log_generation_enabled = $event"
            @update:min-text-logs="form.min_text_logs = $event"
            @update:max-text-logs="form.max_text_logs = $event"
            @update:award-generation-enabled="form.award_generation_enabled = $event"
            @update:min-awards="form.min_awards = $event"
            @update:max-awards="form.max_awards = $event"
            @update:scripts-generation-enabled="form.scripts_generation_enabled = $event"
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
      <div class="mt-6 sm:mt-10 flex flex-col items-center gap-2 sm:gap-3 px-2">
        <button
          @click="handleCreate"
          :disabled="isGenerating || isLoadingCatalogs || !hasLlmConfig"
          class="group relative w-full sm:w-auto px-6 sm:px-10 md:px-14 py-3 sm:py-3.5 md:py-4 bg-gradient-to-br from-aether-primary to-aether-secondary rounded-2xl font-black text-white shadow-2xl shadow-aether-primary/30 hover:scale-105 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed overflow-hidden cursor-pointer"
        >
          <div class="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-500"></div>
          <div class="relative flex items-center justify-center gap-3 md:gap-4">
            <div v-if="isGenerating" class="w-4 h-4 md:w-5 md:h-5 border-3 border-white/30 border-t-white rounded-full animate-spin"></div>
            <Sparkles v-else class="w-4 h-4 md:w-5 md:h-5" />
            <span class="text-xs sm:text-sm md:text-base tracking-[0.2em] text-center">{{ isGenerating ? 'WEAVING REALITY...' : (!hasLlmConfig ? 'CONFIGURATION REQUIRED' : 'BEGIN WEAVING') }}</span>
          </div>
        </button>
        <p class="text-[10px] text-white/30 uppercase tracking-[0.25em] text-center px-2">The process may take a few minutes as the world is manifest</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* No specific styles needed here as they are moved to components or use tailwind */
</style>

