<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Sparkles,
  CheckCircle2,
  ShieldAlert,
  Play,
  Edit3,
  X,
  Wand2,
  Dices,
  Loader2,
} from 'lucide-vue-next'
import { api, GENERATION_SAYINGS } from '@/composables/useApi'
import type { CatalogTile } from '@/types'

// Modular Subcomponents
import GeneratorBasicInfo from './generator/GeneratorBasicInfo.vue'
import GeneratorStyleTone from './generator/GeneratorStyleTone.vue'
import GeneratorTimeSettings from './generator/GeneratorTimeSettings.vue'
import GeneratorAdvancedSettings from './generator/GeneratorAdvancedSettings.vue'
import GeneratorProgressStream, { type LogEntry } from './generator/GeneratorProgressStream.vue'
import GeneratorAssetStats, { type AssetStatsMap } from './generator/GeneratorAssetStats.vue'
import GeneratorLightbox from './generator/GeneratorLightbox.vue'

const props = defineProps<{
  open: boolean
  proposal?: any | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'completed', adventureId: string, title: string): void
}>()

const router = useRouter()

// View state: 'form' | 'progress'
const viewState = ref<'form' | 'progress'>('form')

const logs = ref<LogEntry[]>([])
const isLoadingLogs = ref(true)
const previewImageUrl = ref<string | null>(null)
const streamComponent = ref<InstanceType<typeof GeneratorProgressStream> | null>(null)

const isReady = ref(false)
const hasError = ref(false)

const currentSaying = ref(GENERATION_SAYINGS[Math.floor(Math.random() * GENERATION_SAYINGS.length)])
let sayingTimer: number | null = null

function updateSaying() {
  const randomIndex = Math.floor(Math.random() * GENERATION_SAYINGS.length)
  currentSaying.value = GENERATION_SAYINGS[randomIndex]
}

const lastStatusIndex = computed(() => {
  let lastIdx = -1
  for (let i = logs.value.length - 1; i >= 0; i--) {
    if (logs.value[i].type === 'status') {
      lastIdx = i
      break
    }
  }
  return lastIdx
})

const assetStats = computed<AssetStatsMap>(() => {
  const stats: AssetStatsMap = {
    cover: { generated: 0, reused: 0 },
    protagonist: { generated: 0, reused: 0 },
    scene: { generated: 0, reused: 0 },
    npc: { generated: 0, reused: 0 },
    item: { generated: 0, reused: 0 },
  }

  const detectAssetType = (text: string): keyof AssetStatsMap | null => {
    const lower = text.toLowerCase()
    if (lower.includes('adventure cover')) return 'cover'
    if (lower.includes('protagonist')) return 'protagonist'
    if (lower.includes('scene ') || lower.includes('scene:')) return 'scene'
    if (lower.includes('npc:')) return 'npc'
    if (lower.includes('item:')) return 'item'
    return null
  }

  logs.value.forEach((log, index) => {
    if (log.type !== 'image_generation') return

    const isReused = log.content.includes('Reused source asset')
    if (isReused) {
      const assetType = detectAssetType(log.content)
      if (assetType) stats[assetType].reused++
    } else {
      let assetType: keyof AssetStatsMap | null = null
      for (let i = index - 1; i >= 0; i--) {
        if (logs.value[i].type === 'status') {
          const statusLower = logs.value[i].content.toLowerCase()
          if (statusLower.includes('painting adventure cover') || statusLower.includes('adventure cover')) {
            assetType = 'cover'
          } else if (statusLower.includes('portrait for ')) {
            assetType = 'protagonist'
          } else if (statusLower.includes('portrait ')) {
            assetType = 'npc'
          } else if (statusLower.includes('reifying artifact') || statusLower.includes('artifact ')) {
            assetType = 'item'
          } else if (statusLower.includes('scene ') || statusLower.includes('scene:')) {
            assetType = 'scene'
          }
          break
        }
      }
      if (assetType) stats[assetType].generated++
    }
  })

  return stats
})

const totalStats = computed(() => {
  let generated = 0
  let reused = 0
  Object.values(assetStats.value).forEach((stat) => {
    generated += stat.generated
    reused += stat.reused
  })
  return { generated, reused }
})

// Comprehensive generator form state including time handling
const form = ref({
  title: '',
  storyIdea: '',
  selected_tone_id: '',
  selected_style_id: '',
  generate_scene_images: true,
  generate_npc_images: true,
  generate_item_images: true,
  min_scenes: 4 as number | null,
  max_scenes: 6 as number | null,
  quest_generation_enabled: true,
  min_quests: 2 as number | null,
  max_quests: 4 as number | null,
  container_generation_enabled: true,
  min_containers: 2 as number | null,
  max_containers: 4 as number | null,
  text_log_generation_enabled: true,
  min_text_logs: 2 as number | null,
  max_text_logs: 4 as number | null,
  award_generation_enabled: true,
  min_awards: 2 as number | null,
  max_awards: 4 as number | null,
  rule_enforcement_mode: 'rpg' as 'rpg' | 'story' | 'chat',
  language: '',
  // Time Handling
  clock_enabled: true,
  time_system: 'calendar' as 'calendar' | 'units',
  day_label: 'Day',
  initial_day: 1,
  start_time: '08:00',
  time_format: '24h' as '24h' | '12h',
  pacing_minutes: 5,
  max_time_per_turn: null as number | null,
  unit_name: 'Units',
  initial_units: 0,
  units_per_turn: 1,
  max_units_per_turn: null as number | null,
})

const imageStyles = ref<CatalogTile[]>([])
const tones = ref<CatalogTile[]>([])
const isLoadingCatalogs = ref(false)

const createdAdventureId = ref<string | null>(null)
const currentStatusText = ref<string>('Initializing world weaving...')
const errorMessage = ref<string>('')
const isCancelling = ref(false)

let pollTimer: number | null = null

const DEFAULT_TONES = ['Heroic', 'Grimdark', 'Whimsical', 'Mystery', 'Cyberpunk', 'Horror', 'Sci-Fi', 'Satirical']
const DEFAULT_STYLES = ['cinematic-realism', 'dark-fantasy', 'anime', 'pixel-art', 'vintage-comic', 'watercolor']

// Pre-fill form from proposal whenever proposal updates or modal opens
watch(
  () => [props.open, props.proposal],
  ([isOpen, newProposal]) => {
    if (isOpen) {
      viewState.value = 'form'
      errorMessage.value = ''
      createdAdventureId.value = null
      currentStatusText.value = 'Initializing world weaving...'
      isReady.value = false
      hasError.value = false
      logs.value = []
      isLoadingLogs.value = true
      previewImageUrl.value = null
      void loadCatalogs()

      if (newProposal) {
        populateFromProposal(newProposal)
      } else if (!form.value.title) {
        form.value.title = 'A New Reality'
        form.value.storyIdea = 'A mysterious uncharted realm awaiting its champions.'
      }
    } else {
      stopPolling()
    }
  },
  { immediate: true }
)

function populateFromProposal(p: any) {
  form.value.title = (p.title || 'A New Reality').slice(0, 50)
  form.value.storyIdea = p.prompt || p.storyIdea || ''

  // Tone
  if (typeof p.selected_tone === 'string') {
    form.value.selected_tone_id = p.selected_tone
  } else if (p.selected_tone?.id || p.selected_tone?.name) {
    form.value.selected_tone_id = p.selected_tone.id || p.selected_tone.name
  }

  // Style
  if (Array.isArray(p.selected_image_styles) && p.selected_image_styles.length > 0) {
    const s = p.selected_image_styles[0]
    form.value.selected_style_id = typeof s === 'string' ? s : (s?.id || s?.name || '')
  } else if (typeof p.selected_style === 'string') {
    form.value.selected_style_id = p.selected_style
  }

  // Image flags
  if (p.generate_scene_images !== undefined) form.value.generate_scene_images = !!p.generate_scene_images
  if (p.generate_npc_images !== undefined) form.value.generate_npc_images = !!p.generate_npc_images
  if (p.generate_item_images !== undefined) form.value.generate_item_images = !!p.generate_item_images

  // Bounds & feature toggles
  if (p.min_scenes !== undefined && p.min_scenes !== null) form.value.min_scenes = p.min_scenes
  if (p.max_scenes !== undefined && p.max_scenes !== null) form.value.max_scenes = p.max_scenes

  if (p.quest_generation_enabled !== undefined) form.value.quest_generation_enabled = !!p.quest_generation_enabled
  if (p.min_quests !== undefined && p.min_quests !== null) form.value.min_quests = p.min_quests
  if (p.max_quests !== undefined && p.max_quests !== null) form.value.max_quests = p.max_quests

  if (p.container_generation_enabled !== undefined) form.value.container_generation_enabled = !!p.container_generation_enabled
  if (p.min_containers !== undefined && p.min_containers !== null) form.value.min_containers = p.min_containers
  if (p.max_containers !== undefined && p.max_containers !== null) form.value.max_containers = p.max_containers

  if (p.text_log_generation_enabled !== undefined) form.value.text_log_generation_enabled = !!p.text_log_generation_enabled
  if (p.min_text_logs !== undefined && p.min_text_logs !== null) form.value.min_text_logs = p.min_text_logs
  if (p.max_text_logs !== undefined && p.max_text_logs !== null) form.value.max_text_logs = p.max_text_logs

  if (p.award_generation_enabled !== undefined) form.value.award_generation_enabled = !!p.award_generation_enabled
  if (p.min_awards !== undefined && p.min_awards !== null) form.value.min_awards = p.min_awards
  if (p.max_awards !== undefined && p.max_awards !== null) form.value.max_awards = p.max_awards

  if (p.rule_enforcement_mode) form.value.rule_enforcement_mode = p.rule_enforcement_mode
  if (p.language) form.value.language = p.language

  // TIME HANDLING FROM PROPOSAL
  if (p.clock_enabled !== undefined) form.value.clock_enabled = !!p.clock_enabled
  if (p.time_system) {
    form.value.time_system = p.time_system === 'units' ? 'units' : 'calendar'
  }
  if (p.pacing_minutes !== undefined && p.pacing_minutes !== null) form.value.pacing_minutes = p.pacing_minutes
  if (p.time_per_turn !== undefined && p.time_per_turn !== null) form.value.pacing_minutes = p.time_per_turn

  const tc = p.time_config || {}
  if (tc.day_label) form.value.day_label = tc.day_label
  if (tc.initial_day !== undefined) form.value.initial_day = Number(tc.initial_day) || 1
  if (tc.start_time) form.value.start_time = tc.start_time
  if (tc.time_format) form.value.time_format = tc.time_format === '12h' ? '12h' : '24h'
  if (tc.pacing_minutes !== undefined) form.value.pacing_minutes = Number(tc.pacing_minutes) || 5
  if (tc.max_time_per_turn !== undefined) form.value.max_time_per_turn = tc.max_time_per_turn ? Number(tc.max_time_per_turn) : null

  if (tc.unit_name) form.value.unit_name = tc.unit_name
  if (tc.initial_units !== undefined) form.value.initial_units = Number(tc.initial_units) || 0
  if (tc.units_per_turn !== undefined) form.value.units_per_turn = Number(tc.units_per_turn) || 1
  if (tc.max_units_per_turn !== undefined) form.value.max_units_per_turn = tc.max_units_per_turn ? Number(tc.max_units_per_turn) : null
}

async function loadCatalogs() {
  if (imageStyles.value.length > 0 && tones.value.length > 0) return
  isLoadingCatalogs.value = true
  try {
    const data = await api.getSettings()
    imageStyles.value = data.image_styles_catalog || []
    tones.value = data.tone_catalog || []

    if (!form.value.selected_style_id && imageStyles.value.length > 0) {
      form.value.selected_style_id = imageStyles.value[0].id
    }
    if (!form.value.selected_tone_id && tones.value.length > 0) {
      form.value.selected_tone_id = tones.value[0].id
    }
  } catch (err) {
    console.warn('Could not load catalogs in generator modal', err)
  } finally {
    isLoadingCatalogs.value = false
  }
}

const displayTones = computed(() => {
  if (tones.value.length > 0) {
    return tones.value.map(t => ({ id: t.id, name: t.name || t.id }))
  }
  return DEFAULT_TONES.map(t => ({ id: t.toLowerCase(), name: t }))
})

const displayStyles = computed(() => {
  if (imageStyles.value.length > 0) {
    return imageStyles.value.map(s => ({ id: s.id, name: s.name || s.id }))
  }
  return DEFAULT_STYLES.map(s => ({ id: s, name: s.replace(/-/g, ' ') }))
})

const isSurprising = ref(false)

async function handleSurpriseMe() {
  if (isSurprising.value) return
  isSurprising.value = true
  errorMessage.value = ''

  try {
    const available_tones = displayTones.value.map(t => t.name || t.id)
    const available_styles = displayStyles.value.map(s => s.id)

    const preset = await api.generateSurprisePreset({
      available_tones,
      available_styles,
      language: form.value.language || undefined,
    })

    if (preset) {
      if (preset.title) form.value.title = preset.title.slice(0, 50)
      if (preset.story_idea) form.value.storyIdea = preset.story_idea

      // Match tone ID or name
      if (preset.selected_tone) {
        const foundTone = tones.value.find(
          t => t.id.toLowerCase() === preset.selected_tone!.toLowerCase() ||
               (t.name && t.name.toLowerCase() === preset.selected_tone!.toLowerCase())
        )
        form.value.selected_tone_id = foundTone ? foundTone.id : preset.selected_tone
      }

      // Match style ID or name
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
      if (preset.day_label) form.value.day_label = preset.day_label
      if (preset.initial_day !== undefined) form.value.initial_day = preset.initial_day
      if (preset.start_time) form.value.start_time = preset.start_time
      if (preset.time_format) form.value.time_format = preset.time_format
      if (preset.pacing_minutes !== undefined) form.value.pacing_minutes = preset.pacing_minutes
      if (preset.unit_name) form.value.unit_name = preset.unit_name
      if (preset.initial_units !== undefined) form.value.initial_units = preset.initial_units
      if (preset.units_per_turn !== undefined) form.value.units_per_turn = preset.units_per_turn

      // World constraints / bounds if present
      if (preset.min_scenes !== undefined && preset.min_scenes !== null) form.value.min_scenes = preset.min_scenes
      if (preset.max_scenes !== undefined && preset.max_scenes !== null) form.value.max_scenes = preset.max_scenes
      if (preset.min_quests !== undefined && preset.min_quests !== null) form.value.min_quests = preset.min_quests
      if (preset.max_quests !== undefined && preset.max_quests !== null) form.value.max_quests = preset.max_quests
    }
  } catch (err: any) {
    console.error('Failed to generate surprise preset:', err)
    errorMessage.value = err?.message || 'Could not generate surprise preset.'
  } finally {
    isSurprising.value = false
  }
}

async function fetchLogs(advId: string) {
  try {
    const data = await api.getAdventureGenerationLogs(advId)
    const prevCount = logs.value.length
    logs.value = data.logs || []
    if (logs.value.length !== prevCount) {
      await nextTick()
      streamComponent.value?.scrollToBottom()
    }
  } catch (error) {
    console.error('Error fetching generation logs:', error)
  } finally {
    isLoadingLogs.value = false
  }
}

async function startGeneration() {
  if (!form.value.title.trim()) {
    errorMessage.value = 'Please provide an adventure title.'
    return
  }

  viewState.value = 'progress'
  currentStatusText.value = 'The Architect is preparing the Construct...'
  errorMessage.value = ''
  isCancelling.value = false
  isReady.value = false
  hasError.value = false
  logs.value = []
  isLoadingLogs.value = true

  const fullStyleObj = imageStyles.value.find(s => s.id === form.value.selected_style_id) || {
    id: form.value.selected_style_id,
    name: form.value.selected_style_id,
  }
  const fullToneObj = tones.value.find(t => t.id === form.value.selected_tone_id) || {
    id: form.value.selected_tone_id,
    name: form.value.selected_tone_id,
  }

  // Construct structured time_config
  const time_config: Record<string, any> = form.value.time_system === 'units'
    ? {
        time_system: 'units',
        unit_name: form.value.unit_name || 'Units',
        initial_units: form.value.initial_units || 0,
        units_per_turn: form.value.units_per_turn || 1,
        max_units_per_turn: form.value.max_units_per_turn || null,
      }
    : {
        time_system: 'calendar',
        day_label: form.value.day_label || 'Day',
        initial_day: form.value.initial_day || 1,
        start_time: form.value.start_time || '08:00',
        time_format: form.value.time_format || '24h',
        pacing_minutes: form.value.pacing_minutes || 5,
        max_time_per_turn: form.value.max_time_per_turn || null,
      }

  const pacingVal = form.value.time_system === 'units' ? form.value.units_per_turn : form.value.pacing_minutes

  const payload: any = {
    ...form.value,
    id: crypto.randomUUID(),
    title: (form.value.title.trim() || 'A New Reality').slice(0, 50),
    original_prompt: form.value.storyIdea.trim(),
    selected_image_styles: form.value.selected_style_id ? [fullStyleObj] : [],
    selected_tone: form.value.selected_tone_id ? fullToneObj : null,
    // Time & Pacing
    clock_enabled: form.value.clock_enabled,
    time_system: form.value.time_system,
    pacing_minutes: pacingVal,
    time_per_turn: pacingVal,
    max_time_per_turn: form.value.time_system === 'units' ? form.value.max_units_per_turn : form.value.max_time_per_turn,
    time_config,
  }

  try {
    const result = await api.createAdventure(payload)
    createdAdventureId.value = result.adventure_id || payload.id
    startPolling(createdAdventureId.value!)
  } catch (err: any) {
    console.error('Failed to create adventure from in-game generator:', err)
    errorMessage.value = err?.message || 'Failed to start world generation.'
    hasError.value = true
  }
}

function startPolling(advId: string) {
  stopPolling()
  isLoadingLogs.value = true
  void fetchLogs(advId)

  sayingTimer = window.setInterval(updateSaying, 5000)

  pollTimer = window.setInterval(async () => {
    try {
      void fetchLogs(advId)

      const data = await api.getAdventureStatus(advId)
      if (data.status) {
        currentStatusText.value = data.status
      }

      if (data.is_ready || data.status === 'Ready') {
        stopPolling()
        isReady.value = true
        hasError.value = false
        await fetchLogs(advId)
        emit('completed', advId, form.value.title)
      } else if (data.status === 'Failed' || data.status === 'Cancelled' || data.error) {
        stopPolling()
        hasError.value = true
        errorMessage.value = data.error || (data.status === 'Cancelled' ? 'Generation was cancelled.' : 'World generation encountered a critical flaw.')
        await fetchLogs(advId)
      }
    } catch (err: any) {
      console.warn('Status poll error:', err)
    }
  }, 1500)
}

function stopPolling() {
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (sayingTimer !== null) {
    clearInterval(sayingTimer)
    sayingTimer = null
  }
}

async function cancelActiveGeneration() {
  if (!createdAdventureId.value || isCancelling.value) return
  isCancelling.value = true
  try {
    await api.cancelAdventure(createdAdventureId.value)
    currentStatusText.value = 'Cancelling reality generation...'
  } catch (err: any) {
    console.error('Cancel adventure failed:', err)
  }
}

async function handlePlayNow() {
  if (!createdAdventureId.value) return
  try {
    const res = await api.startSession(createdAdventureId.value)
    if (res?.game_id) {
      emit('close')
      router.push({ name: 'game', params: { id: res.game_id } })
    }
  } catch (err: any) {
    console.error('Failed to start session:', err)
    router.push({ name: 'portal' })
  }
}

function handleOpenEditor() {
  if (!createdAdventureId.value) return
  emit('close')
  router.push({ name: 'adventure-editor', params: { adventureId: createdAdventureId.value } })
}

function handleStayInConstruct() {
  emit('close')
}

const onKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && props.open && viewState.value !== 'progress') {
    emit('close')
  }
}

onMounted(() => window.addEventListener('keydown', onKeyDown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  stopPolling()
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[140] bg-black/80 backdrop-blur-md flex items-center justify-center p-2.5 sm:p-4 md:p-6 overflow-y-auto"
        @click.self="viewState !== 'progress' && emit('close')"
      >
        <div
          class="w-full max-w-3xl bg-slate-900/95 border border-cyan-500/30 rounded-2xl sm:rounded-3xl shadow-[0_0_50px_rgba(6,182,212,0.15)] overflow-hidden flex flex-col my-auto transition-all animate-modal-pop h-[92dvh] sm:h-auto sm:max-h-[90vh]"
        >
          <!-- MODAL HEADER -->
          <div class="px-4 sm:px-6 py-3.5 sm:py-4 border-b border-white/10 bg-slate-950/70 flex items-center justify-between relative shrink-0">
            <div class="flex items-center gap-2.5 sm:gap-3 min-w-0">
              <div class="w-9 h-9 sm:w-10 sm:h-10 rounded-xl sm:rounded-2xl bg-gradient-to-br from-cyan-500/20 to-emerald-500/20 border border-cyan-500/40 flex items-center justify-center shadow-lg shadow-cyan-500/10 shrink-0">
                <Wand2 class="w-4 h-4 sm:w-5 sm:h-5 text-cyan-400 animate-pulse" />
              </div>
              <div class="min-w-0">
                <div class="flex items-center gap-1.5 sm:gap-2">
                  <span class="text-[9px] sm:text-[10px] font-black uppercase tracking-[0.2em] text-cyan-400 truncate">
                    The Construct
                  </span>
                  <span class="px-2 py-0.5 rounded-full text-[8px] sm:text-[9px] font-bold bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 uppercase shrink-0">
                    Adventure Generator
                  </span>
                </div>
                <h3 class="text-sm sm:text-lg font-black text-white tracking-tight mt-0.5 truncate">
                  <template v-if="viewState === 'form'">Weave New Adventure</template>
                  <template v-else-if="viewState === 'progress' && isReady">Reality Manifestation Complete!</template>
                  <template v-else-if="viewState === 'progress' && hasError">World Weaving Interrupted</template>
                  <template v-else-if="viewState === 'progress'">Generation Progress: <span class="text-cyan-400">{{ form.title }}</span></template>
                </h3>
              </div>
            </div>

            <div class="flex items-center gap-2 shrink-0">
              <button
                v-if="viewState === 'form'"
                type="button"
                :disabled="isSurprising"
                @click="handleSurpriseMe"
                class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-purple-500/40 bg-purple-950/40 hover:bg-purple-900/50 text-purple-300 hover:text-purple-100 text-xs font-bold transition-all shadow-sm shadow-purple-900/20 active:scale-95 disabled:opacity-50"
                title="Randomly pre-fill the entire dialog using the world-gen LLM"
              >
                <Dices v-if="!isSurprising" class="w-3.5 h-3.5 text-purple-400" />
                <Loader2 v-else class="w-3.5 h-3.5 text-purple-400 animate-spin" />
                <span class="hidden xs:inline">{{ isSurprising ? 'Weaving...' : 'Surprise Me' }}</span>
              </button>

              <button
                v-if="viewState !== 'progress' || isReady || hasError"
                class="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 transition-colors shrink-0 min-w-[36px] min-h-[36px] flex items-center justify-center"
                @click="emit('close')"
                title="Close Dialog"
              >
                <X class="w-5 h-5" />
              </button>
            </div>
          </div>

          <!-- BODY: FORM / CONFIGURATION -->
          <div
            v-if="viewState === 'form'"
            class="p-4 sm:p-6 space-y-4 sm:space-y-5 flex-1 overflow-y-auto custom-scrollbar"
          >
            <!-- Error Banner -->
            <div
              v-if="errorMessage"
              class="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-bold flex items-center gap-2"
            >
              <ShieldAlert class="w-4 h-4 shrink-0" />
              <span>{{ errorMessage }}</span>
            </div>

            <!-- 1. Basic Info (Title & Story Blueprint) -->
            <GeneratorBasicInfo
              v-model:title="form.title"
              v-model:story-idea="form.storyIdea"
            />

            <!-- 2. Style, Tone & Visual Generation Toggles -->
            <GeneratorStyleTone
              v-model:selected-tone-id="form.selected_tone_id"
              v-model:selected-style-id="form.selected_style_id"
              v-model:generate-scene-images="form.generate_scene_images"
              v-model:generate-npc-images="form.generate_npc_images"
              v-model:generate-item-images="form.generate_item_images"
              :display-tones="displayTones"
              :display-styles="displayStyles"
            />

            <!-- 3. NEW: Time Handling & World Pacing -->
            <GeneratorTimeSettings
              v-model:clock-enabled="form.clock_enabled"
              v-model:time-system="form.time_system"
              v-model:day-label="form.day_label"
              v-model:initial-day="form.initial_day"
              v-model:start-time="form.start_time"
              v-model:time-format="form.time_format"
              v-model:pacing-minutes="form.pacing_minutes"
              v-model:max-time-per-turn="form.max_time_per_turn"
              v-model:unit-name="form.unit_name"
              v-model:initial-units="form.initial_units"
              v-model:units-per-turn="form.units_per_turn"
              v-model:max-units-per-turn="form.max_units_per_turn"
            />

            <!-- 4. Advanced Settings (Bounds, Rules, Modules) -->
            <GeneratorAdvancedSettings
              v-model:min-scenes="form.min_scenes"
              v-model:max-scenes="form.max_scenes"
              v-model:min-quests="form.min_quests"
              v-model:max-quests="form.max_quests"
              v-model:quest-generation-enabled="form.quest_generation_enabled"
              v-model:min-containers="form.min_containers"
              v-model:max-containers="form.max_containers"
              v-model:container-generation-enabled="form.container_generation_enabled"
              v-model:min-text-logs="form.min_text_logs"
              v-model:max-text-logs="form.max_text_logs"
              v-model:text-log-generation-enabled="form.text_log_generation_enabled"
              v-model:min-awards="form.min_awards"
              v-model:max-awards="form.max_awards"
              v-model:award-generation-enabled="form.award_generation_enabled"
              v-model:rule-enforcement-mode="form.rule_enforcement_mode"
            />
          </div>

          <!-- BODY: PROGRESS VIEW -->
          <div
            v-else-if="viewState === 'progress'"
            class="flex-1 flex flex-col min-h-0 overflow-hidden"
          >
            <GeneratorProgressStream
              ref="streamComponent"
              :logs="logs"
              :is-loading-logs="isLoadingLogs"
              :is-ready="isReady"
              :has-error="hasError"
              :last-status-index="lastStatusIndex"
              @preview-image="previewImageUrl = $event"
            />

            <!-- Stats Summary card inside scrollable area or at bottom of stream -->
            <div v-if="isReady || hasError" class="p-3 sm:p-4 bg-slate-950/60 border-t border-white/5 overflow-y-auto max-h-48 custom-scrollbar">
              <GeneratorAssetStats
                :asset-stats="assetStats"
                :total-stats="totalStats"
                :is-ready="isReady"
              />
            </div>
          </div>

          <!-- FOOTER: PROGRESS VIEW -->
          <div
            v-if="viewState === 'progress'"
            class="px-4 sm:px-6 py-3.5 sm:py-4 border-t border-white/10 bg-slate-950/90 flex flex-col sm:flex-row gap-3 items-center justify-between shrink-0"
          >
            <!-- Status message -->
            <div class="flex items-center gap-2 text-xs font-bold w-full sm:w-auto">
              <span v-if="isReady" class="text-emerald-400 flex items-center gap-2 font-black uppercase tracking-wider">
                <CheckCircle2 class="w-4 h-4 text-emerald-400 shrink-0" />
                <span class="truncate">Reality Manifestation Complete!</span>
              </span>
              <span v-else-if="hasError" class="text-rose-400 flex items-center gap-2 font-black uppercase tracking-wider min-w-0">
                <ShieldAlert class="w-4 h-4 text-rose-400 shrink-0" />
                <span class="truncate max-w-[280px] sm:max-w-[360px]">{{ errorMessage || 'World generation interrupted.' }}</span>
              </span>
              <span v-else class="text-cyan-400 flex items-center gap-2 w-full min-w-0">
                <span class="w-2.5 h-2.5 border-2 border-cyan-400/20 border-t-cyan-400 rounded-full animate-spin shrink-0"></span>
                <span class="truncate italic text-slate-300 font-medium text-[11px]">{{ currentSaying }}</span>
              </span>
            </div>

            <!-- Action buttons -->
            <div class="flex flex-wrap items-center gap-2 w-full sm:w-auto justify-end">
              <!-- In-progress cancel -->
              <template v-if="!isReady && !hasError">
                <button
                  type="button"
                  @click="cancelActiveGeneration"
                  :disabled="isCancelling"
                  class="w-full sm:w-auto px-4 py-2.5 rounded-xl text-xs font-bold text-rose-400/80 hover:text-rose-300 hover:bg-rose-500/10 transition-colors disabled:opacity-50 text-center"
                >
                  {{ isCancelling ? 'Cancelling...' : 'Cancel Generation' }}
                </button>
              </template>

              <!-- Success actions -->
              <template v-else-if="isReady">
                <button
                  type="button"
                  @click="handlePlayNow"
                  class="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-black text-xs uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/30 transition-all hover:scale-[1.02] active:scale-95"
                >
                  <Play class="w-3.5 h-3.5 fill-current" />
                  <span>Play Adventure</span>
                </button>

                <button
                  type="button"
                  @click="handleOpenEditor"
                  class="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-cyan-600/20 hover:bg-cyan-600/30 border border-cyan-500/40 text-cyan-300 font-bold text-xs flex items-center justify-center gap-1.5 transition-all"
                >
                  <Edit3 class="w-3.5 h-3.5 text-cyan-400" />
                  <span>Open in Editor</span>
                </button>

                <button
                  type="button"
                  @click="handleStayInConstruct"
                  class="w-full sm:w-auto px-4 py-2.5 rounded-xl text-slate-400 hover:text-white transition-colors text-xs font-bold text-center"
                >
                  Stay in The Construct
                </button>
              </template>

              <!-- Error retry/close -->
              <template v-else-if="hasError">
                <button
                  type="button"
                  @click="viewState = 'form'"
                  class="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs uppercase tracking-wider transition-all text-center"
                >
                  Review Parameters & Retry
                </button>
                <button
                  type="button"
                  @click="emit('close')"
                  class="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-slate-700 text-slate-400 hover:text-white transition-colors text-xs font-bold text-center"
                >
                  Close
                </button>
              </template>
            </div>
          </div>

          <!-- FOOTER: FORM VIEW -->
          <div
            v-if="viewState === 'form'"
            class="px-4 sm:px-6 py-3.5 sm:py-4 border-t border-white/10 bg-slate-950/80 flex flex-col-reverse sm:flex-row items-center justify-between gap-2.5 sm:gap-3 shrink-0"
          >
            <button
              type="button"
              @click="emit('close')"
              class="w-full sm:w-auto px-4 py-2.5 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 transition-colors text-xs font-bold text-center"
            >
              Cancel
            </button>

            <div class="flex items-center gap-2.5 w-full sm:w-auto">
              <button
                type="button"
                :disabled="isSurprising"
                @click="handleSurpriseMe"
                class="flex-1 sm:flex-none px-4 py-2.5 sm:py-3 rounded-xl sm:rounded-2xl border border-purple-500/40 bg-purple-950/40 hover:bg-purple-900/50 text-purple-300 hover:text-purple-100 font-bold text-xs sm:text-sm uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg shadow-purple-950/30 transition-all hover:scale-[1.02] active:scale-95 disabled:opacity-50"
                title="Randomly pre-fill the entire dialog using the world-gen LLM"
              >
                <Dices v-if="!isSurprising" class="w-4 h-4 text-purple-400" />
                <Loader2 v-else class="w-4 h-4 text-purple-400 animate-spin" />
                <span>{{ isSurprising ? 'Weaving Surprise...' : 'Surprise Me' }}</span>
              </button>

              <button
                type="button"
                :disabled="isSurprising"
                @click="startGeneration"
                class="flex-1 sm:flex-none px-6 py-2.5 sm:py-3 rounded-xl sm:rounded-2xl bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white font-black text-xs sm:text-sm uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20 transition-all hover:scale-[1.02] active:scale-95 disabled:opacity-50"
              >
                <Sparkles class="w-4 h-4 text-emerald-200 animate-pulse" />
                <span>Weave Reality</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Artwork Lightbox Modal -->
        <GeneratorLightbox
          :image-url="previewImageUrl"
          @close="previewImageUrl = null"
        />
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-fade-enter-active, .modal-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.modal-fade-enter-from, .modal-fade-leave-to {
  opacity: 0;
  transform: scale(0.96);
}

.animate-modal-pop {
  animation: modalPop 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes modalPop {
  from {
    opacity: 0;
    transform: scale(0.94) translateY(8px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.3);
  border-radius: 9999px;
}
</style>
