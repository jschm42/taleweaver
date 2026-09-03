<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Sparkles,
  Palette,
  Flame,
  Layers,
  ShieldAlert,
  CheckCircle2,
  Play,
  Edit3,
  X,
  Wand2,
  Image as ImageIcon,
  Brain,
  ChevronDown,
  ChevronUp,
  BarChart3,
  ZoomIn,
} from 'lucide-vue-next'
import { api, GENERATION_SAYINGS } from '@/composables/useApi'
import type { CatalogTile } from '@/types'

const props = defineProps<{
  open: boolean
  proposal?: any | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'completed', adventureId: string, title: string): void
}>()

const router = useRouter()

// View states: 'form' | 'progress'
const viewState = ref<'form' | 'progress'>('form')

interface LogEntry {
  timestamp: string
  type: 'status' | 'thinking' | 'image_generation'
  content: string
  image_url?: string
}

const logs = ref<LogEntry[]>([])
const isLoadingLogs = ref(true)
const isExpandedMap = ref<Record<string, boolean>>({})
const chatContainer = ref<HTMLDivElement | null>(null)
const previewImageUrl = ref<string | null>(null)

const isReady = ref(false)
const hasError = ref(false)

const currentSaying = ref(GENERATION_SAYINGS[Math.floor(Math.random() * GENERATION_SAYINGS.length)])
let sayingTimer: number | null = null

function updateSaying() {
  const randomIndex = Math.floor(Math.random() * GENERATION_SAYINGS.length)
  currentSaying.value = GENERATION_SAYINGS[randomIndex]
}

function toggleExpand(timestamp: string) {
  isExpandedMap.value[timestamp] = !isExpandedMap.value[timestamp]
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

const assetStats = computed(() => {
  const stats = {
    cover: { generated: 0, reused: 0 },
    protagonist: { generated: 0, reused: 0 },
    scene: { generated: 0, reused: 0 },
    npc: { generated: 0, reused: 0 },
    item: { generated: 0, reused: 0 },
  }

  const detectAssetType = (text: string): keyof typeof stats | null => {
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
      let assetType: keyof typeof stats | null = null
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
})

const showAdvancedOptions = ref(false)
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

  // Selected tone
  if (typeof p.selected_tone === 'string') {
    form.value.selected_tone_id = p.selected_tone
  } else if (p.selected_tone?.id || p.selected_tone?.name) {
    form.value.selected_tone_id = p.selected_tone.id || p.selected_tone.name
  }

  // Selected style
  if (Array.isArray(p.selected_image_styles) && p.selected_image_styles.length > 0) {
    const s = p.selected_image_styles[0]
    form.value.selected_style_id = typeof s === 'string' ? s : (s?.id || s?.name || '')
  } else if (typeof p.selected_style === 'string') {
    form.value.selected_style_id = p.selected_style
  }

  if (p.generate_scene_images !== undefined) form.value.generate_scene_images = !!p.generate_scene_images
  if (p.generate_npc_images !== undefined) form.value.generate_npc_images = !!p.generate_npc_images
  if (p.generate_item_images !== undefined) form.value.generate_item_images = !!p.generate_item_images

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

async function fetchLogs(advId: string) {
  try {
    const data = await api.getAdventureGenerationLogs(advId)
    const prevCount = logs.value.length
    logs.value = data.logs || []
    if (logs.value.length !== prevCount) {
      await nextTick()
      if (chatContainer.value) {
        chatContainer.value.scrollTop = chatContainer.value.scrollHeight
      }
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

  const payload: any = {
    ...form.value,
    id: crypto.randomUUID(),
    title: (form.value.title.trim() || 'A New Reality').slice(0, 50),
    original_prompt: form.value.storyIdea.trim(),
    selected_image_styles: form.value.selected_style_id ? [fullStyleObj] : [],
    selected_tone: form.value.selected_tone_id ? fullToneObj : null,
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
        class="fixed inset-0 z-[140] bg-black/80 backdrop-blur-md flex items-center justify-center p-3 sm:p-6 overflow-y-auto"
        @click.self="viewState !== 'progress' && emit('close')"
      >
        <div
          class="w-full max-w-3xl bg-slate-900/95 border border-cyan-500/30 rounded-3xl shadow-[0_0_50px_rgba(6,182,212,0.15)] overflow-hidden flex flex-col my-auto transition-all animate-modal-pop"
          :class="[viewState === 'progress' ? 'h-[82vh]' : 'max-h-[90vh]']"
        >
          <!-- HEADER -->
          <div class="px-6 py-5 border-b border-white/10 bg-slate-950/60 flex items-center justify-between relative shrink-0">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-emerald-500/20 border border-cyan-500/40 flex items-center justify-center shadow-lg shadow-cyan-500/10">
                <Wand2 class="w-5 h-5 text-cyan-400 animate-pulse" />
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <span class="text-[10px] font-black uppercase tracking-[0.25em] text-cyan-400">The Construct • Reality Loom</span>
                  <span class="px-2 py-0.5 rounded-full text-[9px] font-bold bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 uppercase">
                    Adventure Generator
                  </span>
                </div>
                <h3 class="text-lg sm:text-xl font-black text-white tracking-tight mt-0.5">
                  <template v-if="viewState === 'form'">Weave New Adventure</template>
                  <template v-else-if="viewState === 'progress' && isReady">Reality Manifestation Complete!</template>
                  <template v-else-if="viewState === 'progress' && hasError">World Weaving Interrupted</template>
                  <template v-else-if="viewState === 'progress'">Generation Progress: <span class="text-cyan-400">{{ form.title }}</span></template>
                </h3>
              </div>
            </div>

            <button
              v-if="viewState !== 'progress' || isReady || hasError"
              class="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
              @click="emit('close')"
            >
              <X class="w-5 h-5" />
            </button>
          </div>

          <!-- BODY: FORM / CONFIGURATION -->
          <div v-if="viewState === 'form'" class="p-6 space-y-6 max-h-[70vh] overflow-y-auto custom-scrollbar">
            <!-- Title & Prompt -->
            <div class="space-y-4 bg-slate-950/40 p-5 rounded-2xl border border-white/5">
              <div>
                <label class="block text-xs font-black uppercase tracking-widest text-slate-300 mb-1.5 flex items-center gap-2">
                  <span>Adventure Title</span>
                  <span class="text-cyan-400">*</span>
                </label>
                <input
                  v-model="form.title"
                  type="text"
                  maxlength="50"
                  placeholder="e.g., Orbital Void: Protocol Omega"
                  class="w-full px-4 py-3 bg-slate-900/90 border border-slate-700/80 rounded-xl text-white font-bold placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20 transition-all text-sm"
                />
              </div>

              <div>
                <label class="block text-xs font-black uppercase tracking-widest text-slate-300 mb-1.5 flex items-center justify-between">
                  <span>Story Blueprint & World Vision</span>
                </label>
                <textarea
                  v-model="form.storyIdea"
                  rows="3"
                  placeholder="Describe the atmosphere, mystery, factions, and world setting..."
                  class="w-full px-4 py-3 bg-slate-900/90 border border-slate-700/80 rounded-xl text-white text-xs sm:text-sm placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20 transition-all resize-none custom-scrollbar"
                ></textarea>
              </div>
            </div>

            <!-- TONE & STYLE -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <!-- Tone Selector -->
              <div class="bg-slate-950/40 p-4 rounded-2xl border border-white/5 space-y-3">
                <div class="flex items-center justify-between">
                  <span class="text-xs font-black uppercase tracking-widest text-slate-300 flex items-center gap-2">
                    <Flame class="w-3.5 h-3.5 text-amber-400" /> Tone
                  </span>
                  <span class="text-[10px] text-slate-500 uppercase font-bold">{{ form.selected_tone_id || 'Select' }}</span>
                </div>
                <div class="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto custom-scrollbar pr-1">
                  <button
                    v-for="t in displayTones"
                    :key="t.id"
                    type="button"
                    @click="form.selected_tone_id = t.id"
                    :class="[
                      'px-2.5 py-1 rounded-lg text-xs font-bold transition-all',
                      form.selected_tone_id === t.id
                        ? 'bg-amber-500/20 border border-amber-500/60 text-amber-300 shadow-sm shadow-amber-500/20'
                        : 'bg-white/5 border border-white/5 text-slate-400 hover:text-white hover:bg-white/10'
                    ]"
                  >
                    {{ t.name }}
                  </button>
                </div>
              </div>

              <!-- Style Selector -->
              <div class="bg-slate-950/40 p-4 rounded-2xl border border-white/5 space-y-3">
                <div class="flex items-center justify-between">
                  <span class="text-xs font-black uppercase tracking-widest text-slate-300 flex items-center gap-2">
                    <Palette class="w-3.5 h-3.5 text-violet-400" /> Visual Style
                  </span>
                  <span class="text-[10px] text-slate-500 uppercase font-bold">{{ form.selected_style_id || 'Select' }}</span>
                </div>
                <div class="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto custom-scrollbar pr-1">
                  <button
                    v-for="s in displayStyles"
                    :key="s.id"
                    type="button"
                    @click="form.selected_style_id = s.id"
                    :class="[
                      'px-2.5 py-1 rounded-lg text-xs font-bold transition-all capitalize',
                      form.selected_style_id === s.id
                        ? 'bg-violet-500/20 border border-violet-500/60 text-violet-300 shadow-sm shadow-violet-500/20'
                        : 'bg-white/5 border border-white/5 text-slate-400 hover:text-white hover:bg-white/10'
                    ]"
                  >
                    {{ s.name }}
                  </button>
                </div>
              </div>
            </div>

            <!-- VISUAL GENERATION TOGGLES -->
            <div class="bg-slate-950/40 p-4 rounded-2xl border border-white/5 space-y-3">
              <span class="text-xs font-black uppercase tracking-widest text-slate-300 flex items-center gap-2">
                <ImageIcon class="w-3.5 h-3.5 text-emerald-400" /> AI Visual Manifestation
              </span>
              <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <button
                  type="button"
                  @click="form.generate_scene_images = !form.generate_scene_images"
                  :class="[
                    'p-3 rounded-xl border flex items-center justify-between transition-all text-left',
                    form.generate_scene_images
                      ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                      : 'bg-white/5 border-white/5 text-slate-500'
                  ]"
                >
                  <span class="text-xs font-bold">Scene Illustrations</span>
                  <div :class="['w-2 h-2 rounded-full', form.generate_scene_images ? 'bg-emerald-400 shadow-sm shadow-emerald-400' : 'bg-slate-700']"></div>
                </button>

                <button
                  type="button"
                  @click="form.generate_npc_images = !form.generate_npc_images"
                  :class="[
                    'p-3 rounded-xl border flex items-center justify-between transition-all text-left',
                    form.generate_npc_images
                      ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                      : 'bg-white/5 border-white/5 text-slate-500'
                  ]"
                >
                  <span class="text-xs font-bold">NPC Portraits</span>
                  <div :class="['w-2 h-2 rounded-full', form.generate_npc_images ? 'bg-emerald-400 shadow-sm shadow-emerald-400' : 'bg-slate-700']"></div>
                </button>

                <button
                  type="button"
                  @click="form.generate_item_images = !form.generate_item_images"
                  :class="[
                    'p-3 rounded-xl border flex items-center justify-between transition-all text-left',
                    form.generate_item_images
                      ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                      : 'bg-white/5 border-white/5 text-slate-500'
                  ]"
                >
                  <span class="text-xs font-bold">Item Icons</span>
                  <div :class="['w-2 h-2 rounded-full', form.generate_item_images ? 'bg-emerald-400 shadow-sm shadow-emerald-400' : 'bg-slate-700']"></div>
                </button>
              </div>
            </div>

            <!-- ADVANCED GENERATION TOGGLE -->
            <div class="space-y-3">
              <button
                type="button"
                @click="showAdvancedOptions = !showAdvancedOptions"
                class="text-xs font-bold text-slate-400 hover:text-cyan-400 flex items-center gap-1.5 transition-colors"
              >
                <Layers class="w-3.5 h-3.5" />
                <span>{{ showAdvancedOptions ? 'Hide Advanced World Settings' : 'Show Advanced World Settings (Scenes, Quests, Items, Rules)' }}</span>
              </button>

              <div v-if="showAdvancedOptions" class="p-4 bg-slate-950/50 border border-white/5 rounded-2xl space-y-4">
                <!-- Scene Count -->
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div>
                    <label class="block text-[10px] font-black uppercase text-slate-400 mb-1">Min Scenes</label>
                    <input
                      v-model.number="form.min_scenes"
                      type="number"
                      min="1"
                      max="15"
                      class="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-xs font-bold"
                    />
                  </div>
                  <div>
                    <label class="block text-[10px] font-black uppercase text-slate-400 mb-1">Max Scenes</label>
                    <input
                      v-model.number="form.max_scenes"
                      type="number"
                      min="1"
                      max="20"
                      class="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-xs font-bold"
                    />
                  </div>
                  <div>
                    <label class="block text-[10px] font-black uppercase text-slate-400 mb-1">Min Quests</label>
                    <input
                      v-model.number="form.min_quests"
                      type="number"
                      min="0"
                      max="10"
                      class="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-xs font-bold"
                    />
                  </div>
                  <div>
                    <label class="block text-[10px] font-black uppercase text-slate-400 mb-1">Max Quests</label>
                    <input
                      v-model.number="form.max_quests"
                      type="number"
                      min="0"
                      max="10"
                      class="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-xs font-bold"
                    />
                  </div>
                </div>

                <!-- Mechanics toggles -->
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2">
                  <label class="flex items-center gap-2 text-xs font-semibold text-slate-300 cursor-pointer">
                    <input type="checkbox" v-model="form.quest_generation_enabled" class="rounded bg-slate-800 border-slate-700 text-cyan-500" />
                    Quests
                  </label>
                  <label class="flex items-center gap-2 text-xs font-semibold text-slate-300 cursor-pointer">
                    <input type="checkbox" v-model="form.container_generation_enabled" class="rounded bg-slate-800 border-slate-700 text-cyan-500" />
                    Containers
                  </label>
                  <label class="flex items-center gap-2 text-xs font-semibold text-slate-300 cursor-pointer">
                    <input type="checkbox" v-model="form.text_log_generation_enabled" class="rounded bg-slate-800 border-slate-700 text-cyan-500" />
                    Lore / Logs
                  </label>
                  <label class="flex items-center gap-2 text-xs font-semibold text-slate-300 cursor-pointer">
                    <input type="checkbox" v-model="form.award_generation_enabled" class="rounded bg-slate-800 border-slate-700 text-cyan-500" />
                    Awards
                  </label>
                </div>
              </div>
            </div>
          </div>

          <!-- BODY: PROGRESS VIEW -->
          <div
            v-else-if="viewState === 'progress'"
            ref="chatContainer"
            class="flex-1 overflow-y-auto p-6 flex flex-col gap-4 bg-[#04080f]/50 scroll-smooth custom-scrollbar"
          >
            <!-- Loading indicator -->
            <div v-if="isLoadingLogs && logs.length === 0" class="flex-1 flex flex-col items-center justify-center gap-3 py-12">
              <div class="w-10 h-10 border-2 border-cyan-500/10 border-t-cyan-400 rounded-full animate-spin"></div>
              <span class="text-xs text-cyan-400 font-bold uppercase tracking-widest animate-pulse">Contacting The Reality Loom...</span>
            </div>

            <div v-else-if="logs.length === 0" class="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs py-12">
              No logs recorded yet. World generation starting...
            </div>

            <!-- Log Entries Stream -->
            <div v-else class="flex flex-col gap-4">
              <div
                v-for="(log, index) in logs"
                :key="log.timestamp"
                class="flex flex-col"
              >
                <!-- 1. Status Update -->
                <div v-if="log.type === 'status'" class="flex justify-center my-1.5">
                  <div class="px-4 py-1.5 rounded-full bg-slate-900/90 border border-white/10 text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2 shadow-sm">
                    <span
                      v-if="index === lastStatusIndex && !isReady && !hasError"
                      class="relative flex h-1.5 w-1.5 shrink-0"
                    >
                      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                      <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-cyan-500"></span>
                    </span>
                    {{ log.content }}
                  </div>
                </div>

                <!-- 2. Thinking Log -->
                <div v-else-if="log.type === 'thinking'" class="flex justify-center w-full max-w-[90%] self-center my-1 animate-fade-in">
                  <div class="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 flex flex-col gap-2 w-full items-center">
                    <button
                      type="button"
                      class="flex items-center justify-center gap-2 text-xs font-black text-amber-400 uppercase tracking-widest select-none cursor-pointer w-full hover:text-amber-300 transition-colors"
                      @click="toggleExpand(log.timestamp)"
                    >
                      <Brain class="w-4 h-4 shrink-0" />
                      <span>LLM Thinking / Reasoning Process</span>
                      <component :is="isExpandedMap[log.timestamp] ? ChevronUp : ChevronDown" class="w-4 h-4" />
                    </button>
                    <div
                      v-if="isExpandedMap[log.timestamp]"
                      class="text-xs text-amber-300/80 leading-relaxed font-mono whitespace-pre-wrap mt-2 p-3.5 bg-black/60 rounded-xl border border-amber-500/10 w-full text-left custom-scrollbar"
                    >
                      {{ log.content }}
                    </div>
                  </div>
                </div>

                <!-- 3. Image Generation / Reused Log -->
                <div v-else-if="log.type === 'image_generation'" class="flex justify-center w-full max-w-[90%] self-center my-1 animate-fade-in">
                  <div class="rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-4 flex flex-col gap-3 items-center w-full">
                    <div class="flex items-center justify-center gap-2 text-xs font-black text-cyan-400 uppercase tracking-widest">
                      <ImageIcon class="w-4 h-4 shrink-0" />
                      <span>{{ log.content.includes('Reused source asset') ? 'Visual Asset Reused' : 'Envisioned Asset Generated' }}</span>
                    </div>
                    <p class="text-xs text-slate-300 italic bg-black/40 p-2.5 rounded-xl border border-white/5 leading-relaxed self-stretch text-center">
                      "{{ log.content }}"
                    </p>
                    <div
                      v-if="log.image_url"
                      class="relative group w-64 h-64 overflow-hidden rounded-xl border border-cyan-500/30 bg-[#030712] flex items-center justify-center cursor-pointer shadow-lg hover:border-cyan-400/60 transition-all"
                      @click="previewImageUrl = log.image_url"
                      title="Click to view full image"
                    >
                      <img
                        :src="log.image_url"
                        alt="Visual Asset"
                        class="max-w-full max-h-full object-contain p-1 transition-transform duration-500 group-hover:scale-105"
                      />
                      <div class="absolute inset-0 bg-cyan-500/0 group-hover:bg-cyan-500/10 transition-colors flex items-end justify-end p-2">
                        <span class="text-[10px] font-bold text-cyan-300 bg-black/70 px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                          <ZoomIn class="w-3 h-3" /> Zoom
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Statistics Summary (shown when generation is complete or errored) -->
              <div v-if="isReady || hasError" class="mt-6 p-5 rounded-2xl border border-cyan-500/20 bg-cyan-500/5 backdrop-blur-md flex flex-col gap-4 self-center w-full max-w-[90%] shadow-[0_0_20px_rgba(6,182,212,0.05)] animate-fade-in">
                <div class="flex items-center justify-between border-b border-white/10 pb-3">
                  <div class="flex items-center gap-2">
                    <BarChart3 class="w-4 h-4 text-cyan-400 shrink-0" />
                    <h4 class="text-xs font-black text-white uppercase tracking-widest">Generation Summary</h4>
                  </div>
                  <span
                    class="text-[10px] font-black uppercase tracking-widest px-2.5 py-0.5 rounded border"
                    :class="isReady ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' : 'bg-rose-500/20 text-rose-300 border-rose-500/30'"
                  >
                    {{ isReady ? 'Success' : 'Failed / Cancelled' }}
                  </span>
                </div>

                <div class="grid grid-cols-2 sm:grid-cols-5 gap-3">
                  <!-- Cover Stat -->
                  <div class="flex flex-col items-center p-3 rounded-xl bg-black/40 border border-white/5 text-center">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Cover</span>
                    <div class="flex flex-col gap-1 w-full text-[9px] font-black">
                      <div class="flex justify-between px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400">
                        <span>Created</span>
                        <span>{{ assetStats.cover.generated }}</span>
                      </div>
                      <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
                        <span>Reused</span>
                        <span>{{ assetStats.cover.reused }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- Protagonist Stat -->
                  <div class="flex flex-col items-center p-3 rounded-xl bg-black/40 border border-white/5 text-center">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Hero</span>
                    <div class="flex flex-col gap-1 w-full text-[9px] font-black">
                      <div class="flex justify-between px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400">
                        <span>Created</span>
                        <span>{{ assetStats.protagonist.generated }}</span>
                      </div>
                      <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
                        <span>Reused</span>
                        <span>{{ assetStats.protagonist.reused }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- Scenes Stat -->
                  <div class="flex flex-col items-center p-3 rounded-xl bg-black/40 border border-white/5 text-center">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Scenes</span>
                    <div class="flex flex-col gap-1 w-full text-[9px] font-black">
                      <div class="flex justify-between px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400">
                        <span>Created</span>
                        <span>{{ assetStats.scene.generated }}</span>
                      </div>
                      <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
                        <span>Reused</span>
                        <span>{{ assetStats.scene.reused }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- NPCs Stat -->
                  <div class="flex flex-col items-center p-3 rounded-xl bg-black/40 border border-white/5 text-center">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">NPCs</span>
                    <div class="flex flex-col gap-1 w-full text-[9px] font-black">
                      <div class="flex justify-between px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400">
                        <span>Created</span>
                        <span>{{ assetStats.npc.generated }}</span>
                      </div>
                      <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
                        <span>Reused</span>
                        <span>{{ assetStats.npc.reused }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- Items Stat -->
                  <div class="flex flex-col items-center p-3 rounded-xl bg-black/40 border border-white/5 text-center">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Items</span>
                    <div class="flex flex-col gap-1 w-full text-[9px] font-black">
                      <div class="flex justify-between px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400">
                        <span>Created</span>
                        <span>{{ assetStats.item.generated }}</span>
                      </div>
                      <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
                        <span>Reused</span>
                        <span>{{ assetStats.item.reused }}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div class="flex justify-between items-center text-[10px] font-bold text-slate-400 uppercase tracking-widest border-t border-white/10 pt-3">
                  <div class="flex items-center gap-4">
                    <span>Total Created: <span class="text-cyan-400 font-black">{{ totalStats.generated }}</span></span>
                    <span>Total Reused: <span class="text-purple-400 font-black">{{ totalStats.reused }}</span></span>
                  </div>
                  <div class="text-slate-400">
                    Total Assets: <span class="text-white font-black">{{ totalStats.generated + totalStats.reused }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- FOOTER: PROGRESS VIEW -->
          <div v-if="viewState === 'progress'" class="px-6 py-4 border-t border-white/10 bg-slate-950/90 flex flex-wrap gap-3 items-center justify-between shrink-0">
            <div class="flex items-center gap-2 text-xs font-bold">
              <span v-if="isReady" class="text-emerald-400 flex items-center gap-2 font-black uppercase tracking-wider">
                <CheckCircle2 class="w-4 h-4 text-emerald-400" /> Reality Manifestation Complete!
              </span>
              <span v-else-if="hasError" class="text-rose-400 flex items-center gap-2 font-black uppercase tracking-wider">
                <ShieldAlert class="w-4 h-4 text-rose-400" />
                <span class="max-w-[400px] truncate">{{ errorMessage || 'World generation interrupted.' }}</span>
              </span>
              <span v-else class="text-cyan-400 flex items-center gap-2 max-w-[480px]">
                <span class="w-2.5 h-2.5 border-2 border-cyan-400/20 border-t-cyan-400 rounded-full animate-spin shrink-0"></span>
                <span class="line-clamp-1 italic text-slate-300 font-medium text-[11px]">{{ currentSaying }}</span>
              </span>
            </div>

            <!-- Action buttons -->
            <div class="flex items-center gap-2">
              <template v-if="!isReady && !hasError">
                <button
                  type="button"
                  @click="cancelActiveGeneration"
                  :disabled="isCancelling"
                  class="px-4 py-2 rounded-xl text-xs font-bold text-rose-400/80 hover:text-rose-300 hover:bg-rose-500/10 transition-colors disabled:opacity-50"
                >
                  {{ isCancelling ? 'Cancelling...' : 'Cancel Generation' }}
                </button>
              </template>

              <template v-else-if="isReady">
                <button
                  type="button"
                  @click="handlePlayNow"
                  class="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-black text-xs uppercase tracking-wider flex items-center gap-2 shadow-lg shadow-emerald-600/30 transition-all hover:scale-105"
                >
                  <Play class="w-3.5 h-3.5 fill-current" />
                  <span>Play Adventure</span>
                </button>

                <button
                  type="button"
                  @click="handleOpenEditor"
                  class="px-4 py-2.5 rounded-xl bg-cyan-600/20 hover:bg-cyan-600/30 border border-cyan-500/40 text-cyan-300 font-bold text-xs flex items-center gap-1.5 transition-all"
                >
                  <Edit3 class="w-3.5 h-3.5 text-cyan-400" />
                  <span>Open in Editor</span>
                </button>

                <button
                  type="button"
                  @click="handleStayInConstruct"
                  class="px-4 py-2.5 rounded-xl text-slate-400 hover:text-white transition-colors text-xs font-bold"
                >
                  Stay in The Construct
                </button>
              </template>

              <template v-else-if="hasError">
                <button
                  type="button"
                  @click="viewState = 'form'"
                  class="px-5 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs uppercase tracking-wider transition-all"
                >
                  Review Parameters & Retry
                </button>
                <button
                  type="button"
                  @click="emit('close')"
                  class="px-4 py-2.5 rounded-xl border border-slate-700 text-slate-400 hover:text-white transition-colors text-xs font-bold"
                >
                  Close
                </button>
              </template>
            </div>
          </div>

          <!-- FOOTER: ONLY ON FORM STEP -->
          <div v-if="viewState === 'form'" class="px-6 py-4 border-t border-white/10 bg-slate-950/80 flex items-center justify-between shrink-0">
            <button
              type="button"
              @click="emit('close')"
              class="px-4 py-2.5 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 transition-colors text-xs font-bold"
            >
              Cancel
            </button>

            <button
              type="button"
              @click="startGeneration"
              class="px-6 py-3 rounded-2xl bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white font-black text-xs sm:text-sm uppercase tracking-wider flex items-center gap-2 shadow-lg shadow-emerald-500/20 transition-all hover:scale-105 active:scale-95"
            >
              <Sparkles class="w-4 h-4 text-emerald-200 animate-pulse" />
              <span>Weave Reality (Generate)</span>
            </button>
          </div>
        </div>

        <!-- Artwork Lightbox Modal -->
        <div
          v-if="previewImageUrl"
          class="fixed inset-0 z-[200] bg-black/90 backdrop-blur-md flex items-center justify-center p-4 cursor-pointer animate-fade-in"
          @click="previewImageUrl = null"
        >
          <div class="relative max-w-3xl max-h-[85vh] p-2 bg-slate-900 border border-cyan-500/30 rounded-2xl shadow-2xl flex flex-col items-center">
            <button
              class="absolute top-4 right-4 p-2 rounded-xl bg-black/60 text-white hover:bg-white/20 transition-colors z-10"
              @click.stop="previewImageUrl = null"
            >
              <X class="w-5 h-5" />
            </button>
            <img
              :src="previewImageUrl"
              alt="Enlarged Artwork"
              class="max-w-full max-h-[80vh] object-contain rounded-xl"
            />
          </div>
        </div>
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
    transform: scale(0.92) translateY(10px);
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
