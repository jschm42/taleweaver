<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Sparkles, Palette, Flame, Layers, ShieldAlert, CheckCircle2, Play, Edit3, X, RefreshCw, Wand2, Image as ImageIcon } from 'lucide-vue-next'
import { api } from '@/composables/useApi'
import { configState } from '@/store/config'
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

// View states: 'form' | 'progress' | 'success' | 'error'
const viewState = ref<'form' | 'progress' | 'success' | 'error'>('form')

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

function formatProgressStatus(status: string): string {
  if (!status) return 'Weaving reality...'
  const lower = status.toLowerCase()
  if (lower.includes('generating world structure')) return 'Forging World Structure & Nodes...'
  if (lower.includes('forging scenes')) return 'Manifesting Scenes & Environments...'
  if (lower.includes('weaving entities')) return 'Breathing Life into Inhabitants & Objects...'
  if (lower.includes('generating visual') || lower.includes('envisioning')) return status
  if (lower.includes('finalizing')) return 'Stabilizing reality threads...'
  if (lower.includes('cancelled')) return 'Generation Cancelled.'
  return status
}

const progressStepIndex = computed(() => {
  const s = (currentStatusText.value || '').toLowerCase()
  if (s.includes('ready') || s.includes('complete')) return 5
  if (s.includes('finalizing') || s.includes('stabilizing')) return 4
  if (s.includes('envisioning') || s.includes('visual')) return 3
  if (s.includes('weaving entities') || s.includes('character') || s.includes('inhabitant')) return 2
  if (s.includes('forging scenes') || s.includes('scene')) return 1
  return 0
})

const progressSteps = [
  { label: 'World Structure' },
  { label: 'Scenes & Exits' },
  { label: 'Inhabitants & Items' },
  { label: 'Visual Visions' },
  { label: 'Reality Stabilized' },
]

async function startGeneration() {
  if (!form.value.title.trim()) {
    errorMessage.value = 'Please provide an adventure title.'
    return
  }

  viewState.value = 'progress'
  currentStatusText.value = 'The Architect is preparing the Construct...'
  errorMessage.value = ''
  isCancelling.value = false

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
    viewState.value = 'error'
  }
}

function startPolling(advId: string) {
  stopPolling()
  pollTimer = window.setInterval(async () => {
    try {
      const data = await api.getAdventureStatus(advId)
      if (data.status) {
        currentStatusText.value = data.status
      }

      if (data.is_ready || data.status === 'Ready') {
        stopPolling()
        viewState.value = 'success'
        emit('completed', advId, form.value.title)
      } else if (data.status === 'Failed' || data.status === 'Cancelled' || data.error) {
        stopPolling()
        errorMessage.value = data.error || (data.status === 'Cancelled' ? 'Generation was cancelled.' : 'World generation encountered a critical flaw.')
        viewState.value = 'error'
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
        >
          <!-- HEADER -->
          <div class="px-6 py-5 border-b border-white/10 bg-slate-950/60 flex items-center justify-between relative">
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
                  <template v-else-if="viewState === 'progress'">Weaving Reality in Progress...</template>
                  <template v-else-if="viewState === 'success'">Reality Manifestation Complete!</template>
                  <template v-else-if="viewState === 'error'">World Weaving Interrupted</template>
                </h3>
              </div>
            </div>

            <button
              v-if="viewState !== 'progress'"
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
          <div v-else-if="viewState === 'progress'" class="p-8 sm:p-12 flex flex-col items-center justify-center text-center space-y-8">
            <!-- Animated Loom Core -->
            <div class="relative w-28 h-28 flex items-center justify-center">
              <div class="absolute inset-0 rounded-full border-2 border-dashed border-cyan-500/40 animate-spin" style="animation-duration: 12s;"></div>
              <div class="absolute inset-2 rounded-full border border-emerald-500/40 animate-spin" style="animation-duration: 8s; animation-direction: reverse;"></div>
              <div class="absolute inset-4 rounded-full bg-cyan-500/10 backdrop-blur-sm animate-pulse"></div>
              <Sparkles class="w-10 h-10 text-cyan-400 relative z-10 animate-bounce" style="animation-duration: 2s;" />
            </div>

            <div class="space-y-2 max-w-lg">
              <span class="text-xs font-black uppercase tracking-[0.2em] text-cyan-400">The Construct is Active</span>
              <h4 class="text-2xl font-black text-white tracking-tight">{{ form.title }}</h4>
              <p class="text-sm font-medium text-slate-300 min-h-[1.5rem] animate-pulse">
                {{ formatProgressStatus(currentStatusText) }}
              </p>
            </div>

            <!-- Step Progress Indicator -->
            <div class="w-full max-w-md bg-slate-950/60 p-4 rounded-2xl border border-white/5 space-y-2.5">
              <div class="grid grid-cols-5 gap-1.5">
                <div
                  v-for="(step, idx) in progressSteps"
                  :key="step.label"
                  :class="[
                    'h-1.5 rounded-full transition-all duration-500',
                    idx <= progressStepIndex ? 'bg-gradient-to-r from-cyan-400 to-emerald-400' : 'bg-slate-800'
                  ]"
                ></div>
              </div>
              <div class="flex justify-between text-[10px] font-bold text-slate-500 uppercase tracking-tight">
                <span>Structure</span>
                <span>Visuals</span>
                <span>Ready</span>
              </div>
            </div>

            <button
              type="button"
              @click="cancelActiveGeneration"
              :disabled="isCancelling"
              class="px-4 py-2 rounded-xl text-xs font-bold text-rose-400/80 hover:text-rose-300 hover:bg-rose-500/10 transition-colors disabled:opacity-50"
            >
              {{ isCancelling ? 'Cancelling...' : 'Cancel World Generation' }}
            </button>
          </div>

          <!-- BODY: SUCCESS VIEW -->
          <div v-else-if="viewState === 'success'" class="p-8 sm:p-12 flex flex-col items-center justify-center text-center space-y-6">
            <div class="w-20 h-20 rounded-3xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center shadow-lg shadow-emerald-500/20 animate-modal-pop">
              <CheckCircle2 class="w-10 h-10 text-emerald-400" />
            </div>

            <div class="space-y-2 max-w-md">
              <span class="text-xs font-black uppercase tracking-[0.2em] text-emerald-400">Creation Successful</span>
              <h4 class="text-2xl font-black text-white tracking-tight">{{ form.title }}</h4>
              <p class="text-xs text-slate-400 leading-relaxed">
                The Architect has stabilized the reality threads. Your new adventure has been added to your chronicle archives.
              </p>
            </div>

            <div class="flex flex-wrap items-center justify-center gap-3 pt-4">
              <button
                type="button"
                @click="handlePlayNow"
                class="px-6 py-3 rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-black text-sm uppercase tracking-wider flex items-center gap-2 shadow-lg shadow-emerald-600/30 transition-all hover:scale-105"
              >
                <Play class="w-4 h-4 fill-current" />
                <span>Play Adventure</span>
              </button>

              <button
                type="button"
                @click="handleOpenEditor"
                class="px-5 py-3 rounded-2xl bg-white/10 hover:bg-white/15 border border-white/10 text-white font-bold text-sm flex items-center gap-2 transition-all"
              >
                <Edit3 class="w-4 h-4 text-cyan-400" />
                <span>Open in Editor</span>
              </button>

              <button
                type="button"
                @click="handleStayInConstruct"
                class="px-4 py-3 rounded-2xl text-slate-400 hover:text-white transition-colors text-xs font-bold"
              >
                Stay in The Construct
              </button>
            </div>
          </div>

          <!-- BODY: ERROR VIEW -->
          <div v-else-if="viewState === 'error'" class="p-8 sm:p-12 flex flex-col items-center justify-center text-center space-y-6">
            <div class="w-20 h-20 rounded-3xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center shadow-lg shadow-rose-500/20">
              <ShieldAlert class="w-10 h-10 text-rose-400" />
            </div>

            <div class="space-y-2 max-w-md">
              <span class="text-xs font-black uppercase tracking-[0.2em] text-rose-400">Generation Flaw</span>
              <h4 class="text-xl font-black text-white">Reality Failed to Materialize</h4>
              <p class="text-xs text-rose-300/80 bg-rose-950/40 p-3 rounded-xl border border-rose-500/20 font-mono">
                {{ errorMessage || 'An unexpected disturbance prevented world generation.' }}
              </p>
            </div>

            <div class="flex items-center gap-3 pt-2">
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
            </div>
          </div>

          <!-- FOOTER: ONLY ON FORM STEP -->
          <div v-if="viewState === 'form'" class="px-6 py-4 border-t border-white/10 bg-slate-950/80 flex items-center justify-between">
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
