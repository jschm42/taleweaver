<script setup lang="ts">
/**
 * DebugModal — Unified In-Game Debug Panel
 *
 * Bundles all session debugging tools into a single cohesive interface:
 * 1. NPCs Overview: All NPCs with real-time stats, health bars, locations, and actions (heal, kill, unhide, drop).
 * 2. World Map: Complete DAGRE layout unmasked by fog-of-war, with NPC indicators/icons on every node where NPCs reside.
 * 3. Items Table: Full matrix of all items across player inventory, scenes, containers, and NPCs with states & locations.
 * 4. Diagnostics: Session runtime, exit locks, quick command triggers, and raw JSON tree.
 */
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import dagre from 'dagre'
import { getImageUrl, getItemIcon, getTypeColor } from '@/utils/game_icons'
import {
  Users,
  Map as MapIcon,
  Package,
  Terminal,
  X,
  Search,
  Heart,
  Zap,
  Flame,
  Shield,
  Eye,
  EyeOff,
  Crosshair,
  RotateCcw,
  Sparkles,
  Lock,
  Unlock,
  Maximize2,
  ZoomIn,
  ZoomOut,
  Compass,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  Trash2,
  Trophy,
  Swords,
  Layers,
} from 'lucide-vue-next'

const props = defineProps<{
  open: boolean
  data: any
  mapData?: any
  nodes?: Record<string, any>
  executeCommand?: (cmd: string) => Promise<void>
}>()

const emit = defineEmits<{
  close: []
  executeCommand: [cmd: string]
}>()

// --- Active Tab State ---
type DebugTab = 'npcs' | 'map' | 'items' | 'diagnostics'
const activeTab = ref<DebugTab>('npcs')

// --- Data Extraction & Fallbacks ---
const sessionDebug = computed(() => props.data?.fullWorld || null)
const sheet = computed(() => props.data?.sheet || null)
const currentSceneId = computed(() => sessionDebug.value?.session?.current_scene_id || sheet.value?.scene_id || '')

// --- Quick Command Execution Helper ---
const commandBusy = ref(false)
const commandSuccessMsg = ref<string | null>(null)
const customCommandInput = ref('')

async function runCmd(cmd: string) {
  if (commandBusy.value) return
  commandBusy.value = true
  commandSuccessMsg.value = null
  try {
    if (props.executeCommand) {
      await props.executeCommand(cmd)
    } else {
      emit('executeCommand', cmd)
    }
    commandSuccessMsg.value = `Executed: ${cmd}`
    setTimeout(() => {
      commandSuccessMsg.value = null
    }, 4000)
  } catch (err: any) {
    console.error('Debug command failed:', err)
  } finally {
    commandBusy.value = false
  }
}

// -------------------------------------------------------------
// TAB 1: NPCs OVERVIEW
// -------------------------------------------------------------
const npcSearchQuery = ref('')
const npcFilterSceneOnly = ref(false)
const npcFilterAliveOnly = ref(false)
const npcFilterHiddenOnly = ref(false)

const allNpcs = computed<any[]>(() => {
  if (Array.isArray(sessionDebug.value?.npcs) && sessionDebug.value.npcs.length) {
    return sessionDebug.value.npcs
  }
  // Fallback from raw entities / blueprint
  const bpNpcs = sessionDebug.value?.blueprint?.npcs || []
  if (bpNpcs.length) {
    const overrides = sessionDebug.value?.runtime?.entity_overrides || {}
    return bpNpcs.map((n: any) => {
      const over = overrides[n.id] || {}
      const hp = over.hp != null ? over.hp : n.hp != null ? n.hp : 100
      const maxHp = over.max_hp != null ? over.max_hp : n.max_hp != null ? n.max_hp : 100
      const isDefeated = boolVal(over.is_defeated)
      return {
        id: n.id,
        name: n.name || n.id,
        description: n.description || '',
        role: n.role || 'NPC',
        image_url: n.image_url,
        current_scene_id: over.current_scene_id || n.current_scene_id || n.start_scene_id || 'UNKNOWN',
        current_scene_name: over.current_scene_id || n.start_scene_id || 'Unknown Location',
        start_scene_id: n.start_scene_id,
        hp,
        max_hp: maxHp,
        stamina: over.stamina != null ? over.stamina : 50,
        max_stamina: 50,
        mana: over.mana != null ? over.mana : 50,
        max_mana: 50,
        is_alive: !isDefeated && hp > 0,
        is_defeated: isDefeated,
        is_hidden: boolVal(over.is_hidden ?? n.is_hidden),
        is_hostile: boolVal(over.is_hostile ?? n.is_hostile),
        inventory: over.inventory || n.inventory || [],
        is_in_current_scene: (over.current_scene_id || n.start_scene_id) === currentSceneId.value,
        stats: { strength: 10, dexterity: 10, intelligence: 10, wisdom: 10, charisma: 10, armor_class: 10 },
      }
    })
  }
  return []
})

const filteredNpcs = computed(() => {
  const q = npcSearchQuery.value.trim().toLowerCase()
  return allNpcs.value.filter((npc) => {
    if (npcFilterSceneOnly.value && npc.current_scene_id !== currentSceneId.value) return false
    if (npcFilterAliveOnly.value && !npc.is_alive) return false
    if (npcFilterHiddenOnly.value && !npc.is_hidden) return false
    if (!q) return true
    return (
      npc.name?.toLowerCase().includes(q) ||
      npc.id?.toLowerCase().includes(q) ||
      npc.current_scene_name?.toLowerCase().includes(q) ||
      npc.current_scene_id?.toLowerCase().includes(q)
    )
  })
})

function boolVal(val: any): boolean {
  return val === true || val === 'true' || val === 1
}

// -------------------------------------------------------------
// TAB 2: WORLD MAP WITH NPC NODES
// -------------------------------------------------------------
const mapContainer = ref<HTMLDivElement | null>(null)
const zoom = ref(1)
const offset = ref({ x: 0, y: 0 })
const isPanning = ref(false)
const lastMousePos = ref({ x: 0, y: 0 })
const hoveredNode = ref<any | null>(null)
const selectedNode = ref<any | null>(null)
const margin = 80

const sceneNpcsMap = computed<Record<string, any[]>>(() => {
  if (sessionDebug.value?.scene_npcs) {
    return sessionDebug.value.scene_npcs
  }
  // Build from allNpcs
  const map: Record<string, any[]> = {}
  allNpcs.value.forEach((npc) => {
    const sId = safeId(npc.current_scene_id || npc.start_scene_id || '')
    if (!sId) return
    if (!map[sId]) map[sId] = []
    map[sId].push(npc)
  })
  return map
})

function safeId(raw: string): string {
  if (!raw) return ''
  return raw.replace(/-/g, '_').toUpperCase()
}

const mapLayoutData = ref<{
  nodes: Array<{
    id: string
    rawId: string
    label: string
    x: number
    y: number
    width: number
    height: number
    isCurrent: boolean
    imageUrl: string | null
    description: string
    npcs: any[]
  }>
  edges: Array<{
    from: string
    to: string
    points: Array<{ x: number; y: number }>
    label: string
    isLocked: boolean
  }>
  width: number
  height: number
} | null>(null)

function updateMapLayout() {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 70, edgesep: 40, ranksep: 120 })
  g.setDefaultEdgeLabel(() => ({}))

  // Collect scenes from sessionDebug map, nodes, or blueprint
  const rawNodes: Record<string, any> =
    sessionDebug.value?.map?.nodes ||
    props.nodes ||
    props.mapData?.nodes ||
    {}

  const blueprintScenes = sessionDebug.value?.blueprint?.scenes || []
  blueprintScenes.forEach((s: any) => {
    if (!rawNodes[s.id]) {
      rawNodes[s.id] = { id: s.id, label: s.label || s.name || s.id, description: s.description, image_url: s.image_url }
    }
  })

  const sceneKeys = Object.keys(rawNodes)
  if (!sceneKeys.length) {
    mapLayoutData.value = null
    return
  }

  // 1. Add nodes (200x120 card size)
  sceneKeys.forEach((id) => {
    g.setNode(safeId(id), { width: 200, height: 120 })
  })

  // 2. Add edges
  const rawEdges: any[] =
    sessionDebug.value?.map?.exits ||
    sessionDebug.value?.blueprint?.exits ||
    props.mapData?.edges ||
    []

  rawEdges.forEach((e: any) => {
    const from = safeId(e.from_scene_id || e.from)
    const to = safeId(e.to_scene_id || e.to)
    if (g.hasNode(from) && g.hasNode(to)) {
      g.setEdge(from, to, {
        label: e.label || '',
        isLocked: !!e.is_locked,
      })
    }
  })

  dagre.layout(g)
  const graphInfo = g.graph()

  const currentSafe = safeId(currentSceneId.value)
  const npcsLookup = sceneNpcsMap.value

  const nodes = g.nodes().map((sid) => {
    const n = g.node(sid)
    const origKey = sceneKeys.find((k) => safeId(k) === sid) || sid
    const orig = rawNodes[origKey] || {}
    const npcsAtNode = npcsLookup[sid] || npcsLookup[origKey] || []

    return {
      id: sid,
      rawId: origKey,
      label: orig.label || orig.name || origKey,
      x: n.x,
      y: n.y,
      width: n.width,
      height: n.height,
      isCurrent: sid === currentSafe,
      imageUrl: orig.image_url || null,
      description: orig.description || '',
      npcs: npcsAtNode,
    }
  })

  const edges = g.edges().map((e) => {
    const edge = g.edge(e)
    return {
      from: e.v,
      to: e.w,
      points: edge.points || [],
      label: edge.label || '',
      isLocked: !!edge.isLocked,
    }
  })

  mapLayoutData.value = {
    nodes,
    edges,
    width: graphInfo.width || 800,
    height: graphInfo.height || 600,
  }

  nextTick(() => {
    centerOnCurrentScene()
  })
}

function centerOnCurrentScene() {
  if (!mapLayoutData.value || !mapContainer.value) return
  const currentSafe = safeId(currentSceneId.value)
  const target = mapLayoutData.value.nodes.find((n) => n.id === currentSafe) || mapLayoutData.value.nodes[0]
  if (!target) return

  const rect = mapContainer.value.getBoundingClientRect()
  const targetX = target.x + margin
  const targetY = target.y + margin

  offset.value = {
    x: rect.width / 2 - targetX * zoom.value,
    y: rect.height / 2 - targetY * zoom.value,
  }
}

function resetMapView() {
  zoom.value = 1
  centerOnCurrentScene()
}

function startPan(e: MouseEvent) {
  if (e.button !== 0) return
  isPanning.value = true
  lastMousePos.value = { x: e.clientX, y: e.clientY }
}

function onPan(e: MouseEvent) {
  if (!isPanning.value) return
  const dx = e.clientX - lastMousePos.value.x
  const dy = e.clientY - lastMousePos.value.y
  offset.value.x += dx
  offset.value.y += dy
  lastMousePos.value = { x: e.clientX, y: e.clientY }
}

function endPan() {
  isPanning.value = false
}

function onWheel(e: WheelEvent) {
  e.preventDefault()
  const factor = e.deltaY < 0 ? 1.15 : 0.85
  const newZoom = Math.min(Math.max(zoom.value * factor, 0.4), 2.5)
  zoom.value = newZoom
}

// -------------------------------------------------------------
// TAB 3: ITEMS MATRIX TABLE
// -------------------------------------------------------------
const itemSearchQuery = ref('')
const itemLocationFilter = ref<string>('all')
const itemTypeFilter = ref<string>('all')
const itemVisibilityFilter = ref<'all' | 'visible' | 'hidden'>('all')

const allItems = computed<any[]>(() => {
  if (Array.isArray(sessionDebug.value?.items) && sessionDebug.value.items.length) {
    return sessionDebug.value.items
  }
  // Fallback: avatar inventory + entities
  const items: any[] = []
  const inv = sheet.value?.inventory || []
  inv.forEach((itm: any) => {
    if (typeof itm === 'object' && itm) {
      items.push({
        id: itm.id || itm.name,
        name: itm.name || 'Unnamed Item',
        description: itm.description || '',
        item_type: itm.item_type || 'PICKABLE',
        slot: itm.slot,
        image_url: itm.image_url,
        location_type: 'avatar',
        location_name: `Hero (${sheet.value?.name || 'You'})`,
        is_hidden: false,
        is_portable: true,
      })
    }
  })
  const ents = props.data?.entities || []
  ents.forEach((e: any) => {
    if (e.entity_type !== 'NPC') {
      items.push({
        id: e.id,
        name: e.name || e.id,
        description: e.description || '',
        item_type: e.item_type || 'OBJECT',
        slot: e.slot,
        image_url: e.image_url,
        location_type: 'scene',
        location_name: `Scene: ${sheet.value?.current_scene || 'Current Scene'}`,
        is_hidden: !!e.is_hidden,
        is_portable: e.is_portable !== false,
      })
    }
  })
  return items
})

const filteredItems = computed(() => {
  const q = itemSearchQuery.value.trim().toLowerCase()
  return allItems.value.filter((itm) => {
    if (itemLocationFilter.value !== 'all' && itm.location_type !== itemLocationFilter.value) {
      return false
    }
    if (itemTypeFilter.value !== 'all' && String(itm.item_type || '').toUpperCase() !== itemTypeFilter.value) {
      return false
    }
    if (itemVisibilityFilter.value === 'visible' && itm.is_hidden) return false
    if (itemVisibilityFilter.value === 'hidden' && !itm.is_hidden) return false
    if (!q) return true
    return (
      itm.name?.toLowerCase().includes(q) ||
      itm.id?.toLowerCase().includes(q) ||
      itm.description?.toLowerCase().includes(q) ||
      itm.location_name?.toLowerCase().includes(q)
    )
  })
})

// -------------------------------------------------------------
// TAB 4: DIAGNOSTICS & RAW
// -------------------------------------------------------------
const rawSearch = ref('')
const copySuccess = ref(false)

const rawJsonString = computed(() => {
  const target = sessionDebug.value || props.data || {}
  return JSON.stringify(target, null, 2)
})

async function copyRawJson() {
  try {
    await navigator.clipboard.writeText(rawJsonString.value)
    copySuccess.value = true
    setTimeout(() => {
      copySuccess.value = false
    }, 2500)
  } catch (err) {
    console.error('Failed to copy JSON:', err)
  }
}

// Watchers & LifeCycle
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      nextTick(() => {
        updateMapLayout()
      })
    }
  }
)

watch(activeTab, (tab) => {
  if (tab === 'map') {
    nextTick(() => {
      updateMapLayout()
    })
  }
})

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.open) {
    emit('close')
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[100] bg-slate-950/90 backdrop-blur-xl flex items-center justify-center p-2 sm:p-4 md:p-6"
        @click.self="emit('close')"
      >
        <div class="w-full max-w-7xl h-[92vh] flex flex-col bg-slate-900/95 border border-cyan-500/30 rounded-3xl shadow-[0_0_80px_rgba(6,182,212,0.2)] overflow-hidden animate-modal-in">
          <!-- TOP HEADER BAR -->
          <header class="flex items-center justify-between px-6 py-4 border-b border-slate-800/90 bg-slate-950/80 shrink-0">
            <div class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-inner shadow-cyan-500/20">
                <Terminal class="w-5 h-5" />
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <h3 class="text-base sm:text-lg font-black text-white uppercase tracking-wider">Unified Debug Inspector</h3>
                  <span class="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-widest bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 animate-pulse">
                    Active
                  </span>
                </div>
                <div class="text-[11px] text-slate-400 font-mono flex items-center gap-3 mt-0.5">
                  <span>Session: <strong class="text-slate-300">{{ sessionDebug?.session?.id || sheet?.session_id || 'Active' }}</strong></span>
                  <span>•</span>
                  <span>Scene: <strong class="text-cyan-400">{{ sessionDebug?.session?.current_scene_name || sheet?.current_scene || 'Current' }}</strong></span>
                  <span>•</span>
                  <span>Time: <strong class="text-amber-400">{{ sessionDebug?.session?.in_game_time ?? sheet?.in_game_time ?? 0 }}m</strong></span>
                </div>
              </div>
            </div>

            <!-- TAB SELECTOR IN HEADER -->
            <div class="hidden md:flex items-center gap-1.5 bg-slate-950/70 p-1 rounded-2xl border border-slate-800">
              <button
                type="button"
                @click="activeTab = 'npcs'"
                class="flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all cursor-pointer"
                :class="activeTab === 'npcs' ? 'bg-cyan-500 text-slate-950 shadow-md font-black' : 'text-slate-400 hover:text-slate-200'"
              >
                <Users class="w-4 h-4" />
                <span>NPCs ({{ allNpcs.length }})</span>
              </button>
              <button
                type="button"
                @click="activeTab = 'map'"
                class="flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all cursor-pointer"
                :class="activeTab === 'map' ? 'bg-cyan-500 text-slate-950 shadow-md font-black' : 'text-slate-400 hover:text-slate-200'"
              >
                <MapIcon class="w-4 h-4" />
                <span>World Map</span>
              </button>
              <button
                type="button"
                @click="activeTab = 'items'"
                class="flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all cursor-pointer"
                :class="activeTab === 'items' ? 'bg-cyan-500 text-slate-950 shadow-md font-black' : 'text-slate-400 hover:text-slate-200'"
              >
                <Package class="w-4 h-4" />
                <span>Items ({{ allItems.length }})</span>
              </button>
              <button
                type="button"
                @click="activeTab = 'diagnostics'"
                class="flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all cursor-pointer"
                :class="activeTab === 'diagnostics' ? 'bg-cyan-500 text-slate-950 shadow-md font-black' : 'text-slate-400 hover:text-slate-200'"
              >
                <Terminal class="w-4 h-4" />
                <span>Diagnostics</span>
              </button>
            </div>

            <!-- Close Button -->
            <button
              type="button"
              class="p-2 rounded-full bg-slate-800/80 hover:bg-red-600 text-slate-400 hover:text-white transition-all border border-slate-700/60 cursor-pointer"
              @click="emit('close')"
              title="Close Debug Panel (ESC)"
            >
              <X class="w-5 h-5" />
            </button>
          </header>

          <!-- MOBILE TAB SELECTOR BAR -->
          <div class="md:hidden flex items-center justify-around bg-slate-950 border-b border-slate-800 p-2 shrink-0">
            <button
              type="button"
              @click="activeTab = 'npcs'"
              class="flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-bold uppercase"
              :class="activeTab === 'npcs' ? 'bg-cyan-500 text-slate-950' : 'text-slate-400'"
            >
              <Users class="w-3.5 h-3.5" /> NPCs
            </button>
            <button
              type="button"
              @click="activeTab = 'map'"
              class="flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-bold uppercase"
              :class="activeTab === 'map' ? 'bg-cyan-500 text-slate-950' : 'text-slate-400'"
            >
              <MapIcon class="w-3.5 h-3.5" /> Map
            </button>
            <button
              type="button"
              @click="activeTab = 'items'"
              class="flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-bold uppercase"
              :class="activeTab === 'items' ? 'bg-cyan-500 text-slate-950' : 'text-slate-400'"
            >
              <Package class="w-3.5 h-3.5" /> Items
            </button>
            <button
              type="button"
              @click="activeTab = 'diagnostics'"
              class="flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-bold uppercase"
              :class="activeTab === 'diagnostics' ? 'bg-cyan-500 text-slate-950' : 'text-slate-400'"
            >
              <Terminal class="w-3.5 h-3.5" /> Diag
            </button>
          </div>

          <!-- SUCCESS TOAST IF COMMAND EXECUTED -->
          <div v-if="commandSuccessMsg" class="px-6 py-2 bg-cyan-500/10 border-b border-cyan-500/30 text-cyan-300 text-xs font-mono flex items-center justify-between animate-fade-in shrink-0">
            <span>{{ commandSuccessMsg }}</span>
            <button type="button" @click="commandSuccessMsg = null" class="text-cyan-400 hover:text-white">✕</button>
          </div>

          <!-- TAB CONTENT AREA -->
          <main class="flex-grow min-h-0 overflow-hidden relative flex flex-col bg-slate-950/40">
            <!-- ========================================================= -->
            <!-- TAB 1: ALL NPCS OVERVIEW -->
            <!-- ========================================================= -->
            <section v-if="activeTab === 'npcs'" class="flex-1 flex flex-col min-h-0 p-4 sm:p-6 overflow-hidden">
              <!-- Filter Bar -->
              <div class="flex flex-wrap items-center justify-between gap-3 mb-4 shrink-0 bg-slate-900/80 p-3.5 rounded-2xl border border-slate-800">
                <div class="relative flex-1 min-w-[200px] max-w-md">
                  <Search class="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    v-model="npcSearchQuery"
                    type="text"
                    placeholder="Search NPCs by name, ID, or location..."
                    class="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl pl-9 pr-4 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                  />
                </div>

                <div class="flex items-center gap-2 flex-wrap text-xs">
                  <button
                    type="button"
                    @click="npcFilterSceneOnly = !npcFilterSceneOnly"
                    class="px-3 py-1.5 rounded-xl border font-bold uppercase tracking-wider transition-all cursor-pointer"
                    :class="npcFilterSceneOnly ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50' : 'border-slate-700 text-slate-400 hover:text-slate-200'"
                  >
                    Current Scene Only
                  </button>
                  <button
                    type="button"
                    @click="npcFilterAliveOnly = !npcFilterAliveOnly"
                    class="px-3 py-1.5 rounded-xl border font-bold uppercase tracking-wider transition-all cursor-pointer"
                    :class="npcFilterAliveOnly ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50' : 'border-slate-700 text-slate-400 hover:text-slate-200'"
                  >
                    Alive Only
                  </button>
                  <button
                    type="button"
                    @click="npcFilterHiddenOnly = !npcFilterHiddenOnly"
                    class="px-3 py-1.5 rounded-xl border font-bold uppercase tracking-wider transition-all cursor-pointer"
                    :class="npcFilterHiddenOnly ? 'bg-amber-500/20 text-amber-300 border-amber-500/50' : 'border-slate-700 text-slate-400 hover:text-slate-200'"
                  >
                    Hidden Only
                  </button>
                  <button
                    type="button"
                    @click="runCmd('/debug unhide all')"
                    class="px-3 py-1.5 rounded-xl border border-purple-500/40 bg-purple-500/10 text-purple-300 hover:bg-purple-500/20 font-bold uppercase tracking-wider transition-all cursor-pointer"
                    title="Make all hidden NPCs visible"
                  >
                    Unhide All
                  </button>
                </div>
              </div>

              <!-- NPC Cards Grid -->
              <div class="flex-1 overflow-y-auto custom-scrollbar pr-1 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div
                  v-for="npc in filteredNpcs"
                  :key="npc.id"
                  class="rounded-2xl border bg-slate-900/90 p-4 flex flex-col justify-between gap-3.5 transition-all shadow-lg"
                  :class="[
                    npc.is_in_current_scene ? 'border-cyan-500/50 ring-1 ring-cyan-500/30' : 'border-slate-800',
                    !npc.is_alive ? 'opacity-60 grayscale-[0.4]' : ''
                  ]"
                >
                  <!-- Top: Avatar & Title -->
                  <div class="flex items-start gap-3">
                    <div class="relative w-14 h-14 rounded-xl overflow-hidden bg-slate-950 border border-slate-700/80 shrink-0">
                      <img
                        v-if="npc.image_url"
                        :src="getImageUrl(npc.image_url)"
                        class="w-full h-full object-cover object-center"
                        :alt="npc.name"
                      />
                      <div v-else class="w-full h-full flex items-center justify-center text-slate-600">
                        <Users class="w-6 h-6" />
                      </div>
                      <span
                        v-if="npc.is_in_current_scene"
                        class="absolute bottom-0 inset-x-0 bg-cyan-500 text-slate-950 text-[8px] font-black uppercase text-center tracking-tighter"
                      >
                        Here
                      </span>
                    </div>

                    <div class="flex-1 min-w-0">
                      <div class="flex items-center justify-between gap-2">
                        <h4 class="text-sm font-black text-white truncate">{{ npc.name }}</h4>
                        <span
                          class="px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider shrink-0"
                          :class="npc.is_alive ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-red-500/20 text-red-300 border border-red-500/30'"
                        >
                          {{ npc.is_alive ? 'Alive' : 'Defeated' }}
                        </span>
                      </div>
                      <div class="text-[10px] text-slate-400 font-mono truncate mt-0.5">ID: {{ npc.id }}</div>

                      <!-- Location Badge -->
                      <div class="mt-1.5 flex items-center gap-1.5 text-[11px]">
                        <Compass class="w-3 h-3 text-cyan-400 shrink-0" />
                        <span class="text-slate-300 font-semibold truncate">{{ npc.current_scene_name || npc.current_scene_id }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- Middle: Stats & Bars -->
                  <div class="space-y-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                    <!-- Health Bar -->
                    <div>
                      <div class="flex items-center justify-between text-[11px] mb-1 font-mono">
                        <span class="flex items-center gap-1 text-red-400 font-bold">
                          <Heart class="w-3 h-3 fill-red-400" /> HP
                        </span>
                        <span class="text-slate-300 font-bold">{{ npc.hp }} / {{ npc.max_hp }}</span>
                      </div>
                      <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          class="h-full transition-all duration-300"
                          :class="npc.hp > (npc.max_hp * 0.5) ? 'bg-emerald-500' : npc.hp > (npc.max_hp * 0.2) ? 'bg-amber-500' : 'bg-red-500'"
                          :style="{ width: `${Math.min(100, Math.max(0, (npc.hp / (npc.max_hp || 100)) * 100))}%` }"
                        ></div>
                      </div>
                    </div>

                    <!-- Stamina & Mana mini bars if available -->
                    <div class="grid grid-cols-2 gap-2 text-[10px] font-mono text-slate-400">
                      <div>
                        <span>STA: {{ npc.stamina }}</span>
                      </div>
                      <div class="text-right">
                        <span>MANA: {{ npc.mana }}</span>
                      </div>
                    </div>

                    <!-- Attributes -->
                    <div v-if="npc.stats" class="grid grid-cols-3 gap-1 text-[10px] font-mono text-slate-400 pt-1 border-t border-slate-800/60">
                      <div>STR: <strong class="text-slate-200">{{ npc.stats.strength }}</strong></div>
                      <div>DEX: <strong class="text-slate-200">{{ npc.stats.dexterity }}</strong></div>
                      <div>AC: <strong class="text-slate-200">{{ npc.stats.armor_class }}</strong></div>
                    </div>
                  </div>

                  <!-- Inventory items if any -->
                  <div v-if="npc.inventory?.length" class="space-y-1">
                    <div class="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1">
                      <Package class="w-3 h-3 text-cyan-400" />
                      <span>Carrying ({{ npc.inventory.length }})</span>
                    </div>
                    <div class="flex flex-wrap gap-1 max-h-16 overflow-y-auto custom-scrollbar">
                      <span
                        v-for="(itm, iIdx) in npc.inventory"
                        :key="iIdx"
                        class="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-[10px] text-slate-300 truncate max-w-[140px]"
                        :title="itm.description || itm.name"
                      >
                        {{ itm.name || itm.id }}
                      </span>
                    </div>
                  </div>

                  <!-- Bottom: Action Buttons -->
                  <div class="flex items-center gap-1.5 pt-2 border-t border-slate-800/80">
                    <button
                      type="button"
                      @click="runCmd(`/debug heal ${npc.name}`)"
                      class="flex-1 py-1 px-2 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-[10px] font-bold uppercase tracking-wider transition-all cursor-pointer"
                      title="Heal NPC to full health"
                    >
                      Heal
                    </button>
                    <button
                      type="button"
                      @click="runCmd(`/debug kill ${npc.name}`)"
                      class="flex-1 py-1 px-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-300 text-[10px] font-bold uppercase tracking-wider transition-all cursor-pointer"
                      title="Instantly defeat this NPC"
                    >
                      Kill
                    </button>
                    <button
                      v-if="npc.is_hidden"
                      type="button"
                      @click="runCmd(`/debug unhide ${npc.id}`)"
                      class="py-1 px-2 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 text-[10px] font-bold uppercase tracking-wider transition-all cursor-pointer"
                      title="Make visible in scene"
                    >
                      Unhide
                    </button>
                  </div>
                </div>

                <div v-if="!filteredNpcs.length" class="col-span-full py-16 text-center text-slate-500 font-semibold">
                  No NPCs match the active search or filters.
                </div>
              </div>
            </section>

            <!-- ========================================================= -->
            <!-- TAB 2: WORLD MAP WITH NPC ICONS ON NODES -->
            <!-- ========================================================= -->
            <section v-else-if="activeTab === 'map'" class="flex-1 flex flex-col min-h-0 relative overflow-hidden">
              <!-- Map Top Bar: Controls -->
              <div class="absolute top-4 left-4 z-30 flex items-center gap-2 bg-slate-900/90 backdrop-blur-md p-1.5 rounded-2xl border border-slate-700/80 shadow-xl">
                <button
                  type="button"
                  @click="zoom = Math.min(zoom * 1.2, 2.5)"
                  class="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-all cursor-pointer"
                  title="Zoom In"
                >
                  <ZoomIn class="w-4 h-4" />
                </button>
                <button
                  type="button"
                  @click="zoom = Math.max(zoom * 0.8, 0.4)"
                  class="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-all cursor-pointer"
                  title="Zoom Out"
                >
                  <ZoomOut class="w-4 h-4" />
                </button>
                <button
                  type="button"
                  @click="resetMapView"
                  class="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-all cursor-pointer"
                  title="Center & Reset View"
                >
                  <Maximize2 class="w-4 h-4" />
                </button>
                <div class="h-4 w-px bg-slate-700 mx-1"></div>
                <button
                  type="button"
                  @click="runCmd('/debug reveal_map')"
                  class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-300 text-xs font-bold uppercase tracking-wider transition-all cursor-pointer"
                  title="Reveal all in-game locations"
                >
                  <Eye class="w-3.5 h-3.5" />
                  <span>Reveal All Map</span>
                </button>
              </div>

              <!-- Map Legend Overlay -->
              <div class="absolute bottom-4 left-4 z-30 flex items-center gap-3 bg-slate-900/90 backdrop-blur-md px-3.5 py-2 rounded-2xl border border-slate-800 text-xs text-slate-400 font-mono shadow-xl">
                <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-amber-400 ring-2 ring-amber-400/40"></span> Hero Position</span>
                <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-cyan-400"></span> NPC(s) Present</span>
                <span class="flex items-center gap-1.5"><Lock class="w-3 h-3 text-red-400" /> Locked Passage</span>
              </div>

              <!-- Selected Node Detail Popover -->
              <div
                v-if="selectedNode"
                class="absolute top-4 right-4 z-30 w-80 bg-slate-900/95 backdrop-blur-xl border border-cyan-500/40 rounded-2xl p-4 shadow-2xl animate-fade-in text-slate-200"
              >
                <div class="flex items-start justify-between gap-2 mb-2">
                  <div>
                    <h4 class="text-sm font-black text-white">{{ selectedNode.label }}</h4>
                    <div class="text-[10px] text-slate-400 font-mono">{{ selectedNode.rawId }}</div>
                  </div>
                  <button type="button" @click="selectedNode = null" class="text-slate-400 hover:text-white">✕</button>
                </div>

                <p v-if="selectedNode.description" class="text-xs text-slate-300 mb-3 leading-relaxed max-h-24 overflow-y-auto custom-scrollbar">
                  {{ selectedNode.description }}
                </p>

                <!-- NPCs Present at this node -->
                <div class="border-t border-slate-800 pt-2.5">
                  <div class="text-[10px] font-black uppercase tracking-wider text-cyan-400 flex items-center gap-1 mb-2">
                    <Users class="w-3.5 h-3.5" />
                    <span>Inhabitants Here ({{ selectedNode.npcs?.length || 0 }})</span>
                  </div>

                  <div v-if="selectedNode.npcs?.length" class="space-y-2 max-h-40 overflow-y-auto custom-scrollbar">
                    <div
                      v-for="npc in selectedNode.npcs"
                      :key="npc.id"
                      class="flex items-center justify-between gap-2 p-2 rounded-xl bg-slate-950 border border-slate-800 text-xs"
                    >
                      <div class="flex items-center gap-2 min-w-0">
                        <div class="w-6 h-6 rounded-lg bg-slate-800 overflow-hidden shrink-0">
                          <img v-if="npc.image_url" :src="getImageUrl(npc.image_url)" class="w-full h-full object-cover" />
                          <Users v-else class="w-4 h-4 m-1 text-slate-400" />
                        </div>
                        <span class="font-bold text-white truncate">{{ npc.name }}</span>
                      </div>
                      <span class="text-[10px] font-mono text-emerald-400 shrink-0">{{ npc.hp }}/{{ npc.max_hp }} HP</span>
                    </div>
                  </div>
                  <div v-else class="text-xs text-slate-500 italic">No NPCs currently at this location.</div>
                </div>
              </div>

              <!-- DAGRE SVG & HTML GRAPH CANVAS -->
              <div
                ref="mapContainer"
                class="w-full h-full cursor-grab active:cursor-grabbing select-none overflow-hidden relative"
                @mousedown="startPan"
                @mousemove="onPan"
                @mouseup="endPan"
                @mouseleave="endPan"
                @wheel="onWheel"
              >
                <div
                  class="absolute origin-top-left transition-transform duration-75"
                  :style="{
                    transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
                    width: `${(mapLayoutData?.width || 800) + margin * 2}px`,
                    height: `${(mapLayoutData?.height || 600) + margin * 2}px`,
                  }"
                >
                  <!-- SVG EDGES LAYER -->
                  <svg
                    class="absolute inset-0 pointer-events-none"
                    :width="(mapLayoutData?.width || 800) + margin * 2"
                    :height="(mapLayoutData?.height || 600) + margin * 2"
                  >
                    <defs>
                      <marker
                        id="debug-arrow"
                        viewBox="0 0 10 10"
                        refX="16"
                        refY="5"
                        markerWidth="6"
                        markerHeight="6"
                        orient="auto-start-reverse"
                      >
                        <path d="M 0 0 L 10 5 L 0 10 z" fill="#06b6d4" />
                      </marker>
                      <marker
                        id="debug-arrow-locked"
                        viewBox="0 0 10 10"
                        refX="16"
                        refY="5"
                        markerWidth="6"
                        markerHeight="6"
                        orient="auto-start-reverse"
                      >
                        <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                      </marker>
                    </defs>

                    <g v-if="mapLayoutData">
                      <g v-for="(edge, eIdx) in mapLayoutData.edges" :key="eIdx">
                        <path
                          v-if="edge.points.length >= 2"
                          :d="`M ${edge.points.map(p => `${p.x + margin},${p.y + margin}`).join(' L ')}`"
                          fill="none"
                          :stroke="edge.isLocked ? '#ef4444' : '#0891b2'"
                          :stroke-width="edge.isLocked ? 2 : 2.5"
                          :stroke-dasharray="edge.isLocked ? '4 3' : 'none'"
                          :marker-end="edge.isLocked ? 'url(#debug-arrow-locked)' : 'url(#debug-arrow)'"
                          class="opacity-75"
                        />
                      </g>
                    </g>
                  </svg>

                  <!-- HTML NODES LAYER -->
                  <div v-if="mapLayoutData" class="absolute inset-0 pointer-events-auto">
                    <div
                      v-for="node in mapLayoutData.nodes"
                      :key="node.id"
                      class="absolute rounded-2xl p-3 flex flex-col justify-between transition-all duration-200 cursor-pointer shadow-xl border select-none group"
                      :class="[
                        node.isCurrent
                          ? 'bg-slate-900/95 border-amber-400 ring-2 ring-amber-400/40 shadow-amber-500/20'
                          : selectedNode?.id === node.id
                            ? 'bg-slate-900/95 border-cyan-400 ring-2 ring-cyan-400/40'
                            : 'bg-slate-900/80 hover:bg-slate-900 border-slate-800 hover:border-slate-700'
                      ]"
                      :style="{
                        left: `${node.x + margin - node.width / 2}px`,
                        top: `${node.y + margin - node.height / 2}px`,
                        width: `${node.width}px`,
                        height: `${node.height}px`,
                      }"
                      @click="selectedNode = node"
                    >
                      <!-- CRITICAL: NPC Indicator Badge on Node -->
                      <div
                        v-if="node.npcs?.length"
                        class="absolute -top-3 -right-3 z-30 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-cyan-500 text-slate-950 font-black text-[11px] shadow-lg shadow-cyan-500/50 border-2 border-white animate-bounce"
                        title="NPCs Present at this Scene"
                      >
                        <Users class="w-3.5 h-3.5" />
                        <span>{{ node.npcs.length }}</span>
                      </div>

                      <!-- Hero Current Location Badge -->
                      <div
                        v-if="node.isCurrent"
                        class="absolute -top-3 left-3 z-30 px-2 py-0.5 rounded-full bg-amber-400 text-slate-950 font-black text-[9px] uppercase tracking-wider shadow-md"
                      >
                        You Here
                      </div>

                      <!-- Node Content -->
                      <div class="flex items-center gap-2 min-w-0">
                        <div class="w-10 h-10 rounded-xl overflow-hidden bg-slate-950 border border-slate-700 shrink-0">
                          <img v-if="node.imageUrl" :src="getImageUrl(node.imageUrl)" class="w-full h-full object-cover" />
                          <MapIcon v-else class="w-5 h-5 m-2.5 text-slate-500" />
                        </div>
                        <div class="flex-1 min-w-0">
                          <h5 class="text-xs font-black text-white truncate leading-tight">{{ node.label }}</h5>
                          <div class="text-[9px] font-mono text-slate-400 truncate mt-0.5">{{ node.rawId }}</div>
                        </div>
                      </div>

                      <!-- Node Footer: NPC avatars preview if present -->
                      <div class="flex items-center justify-between text-[10px] text-slate-400 border-t border-slate-800/60 pt-1.5">
                        <span class="truncate text-[9px] font-mono text-slate-500">{{ node.npcs.length ? `${node.npcs.length} NPC(s)` : 'Empty' }}</span>
                        <div v-if="node.npcs?.length" class="flex -space-x-1.5 overflow-hidden">
                          <div
                            v-for="(nNpc, nnIdx) in node.npcs.slice(0, 3)"
                            :key="nnIdx"
                            class="w-4 h-4 rounded-full border border-slate-900 overflow-hidden bg-slate-800"
                            :title="nNpc.name"
                          >
                            <img v-if="nNpc.image_url" :src="getImageUrl(nNpc.image_url)" class="w-full h-full object-cover" />
                            <span v-else class="text-[7px] text-cyan-300 font-bold block text-center">N</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <!-- ========================================================= -->
            <!-- TAB 3: ITEMS MATRIX TABLE -->
            <!-- ========================================================= -->
            <section v-else-if="activeTab === 'items'" class="flex-1 flex flex-col min-h-0 p-4 sm:p-6 overflow-hidden">
              <!-- Search & Filter Controls -->
              <div class="flex flex-wrap items-center justify-between gap-3 mb-4 shrink-0 bg-slate-900/80 p-3.5 rounded-2xl border border-slate-800">
                <div class="relative flex-1 min-w-[200px] max-w-md">
                  <Search class="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    v-model="itemSearchQuery"
                    type="text"
                    placeholder="Search items by name, ID, or location..."
                    class="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl pl-9 pr-4 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                  />
                </div>

                <div class="flex items-center gap-2 flex-wrap text-xs">
                  <!-- Location Filter -->
                  <select
                    v-model="itemLocationFilter"
                    class="bg-slate-950 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-slate-300 font-bold uppercase tracking-wider focus:outline-none focus:border-cyan-400"
                  >
                    <option value="all">All Locations</option>
                    <option value="avatar">Hero Inventory</option>
                    <option value="scene">In Scene</option>
                    <option value="container">Inside Container</option>
                    <option value="npc">Carried by NPC</option>
                  </select>

                  <!-- Type Filter -->
                  <select
                    v-model="itemTypeFilter"
                    class="bg-slate-950 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-slate-300 font-bold uppercase tracking-wider focus:outline-none focus:border-cyan-400"
                  >
                    <option value="all">All Types</option>
                    <option value="WEAPON">Weapons</option>
                    <option value="ARMOR">Armor</option>
                    <option value="CONSUMABLE">Consumables</option>
                    <option value="CONTAINER">Containers</option>
                    <option value="SWITCH">Switches</option>
                    <option value="READABLE">Readables</option>
                    <option value="PICKABLE">Pickable Items</option>
                  </select>

                  <!-- Visibility Filter -->
                  <div class="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
                    <button
                      type="button"
                      @click="itemVisibilityFilter = 'all'"
                      class="px-2.5 py-1 rounded-lg font-bold text-[10px] uppercase transition-all"
                      :class="itemVisibilityFilter === 'all' ? 'bg-cyan-500 text-slate-950' : 'text-slate-400'"
                    >
                      All
                    </button>
                    <button
                      type="button"
                      @click="itemVisibilityFilter = 'visible'"
                      class="px-2.5 py-1 rounded-lg font-bold text-[10px] uppercase transition-all"
                      :class="itemVisibilityFilter === 'visible' ? 'bg-cyan-500 text-slate-950' : 'text-slate-400'"
                    >
                      Visible
                    </button>
                    <button
                      type="button"
                      @click="itemVisibilityFilter = 'hidden'"
                      class="px-2.5 py-1 rounded-lg font-bold text-[10px] uppercase transition-all"
                      :class="itemVisibilityFilter === 'hidden' ? 'bg-cyan-500 text-slate-950' : 'text-slate-400'"
                    >
                      Hidden
                    </button>
                  </div>
                </div>
              </div>

              <!-- Items Table -->
              <div class="flex-1 overflow-auto custom-scrollbar border border-slate-800 rounded-2xl bg-slate-900/60 shadow-inner">
                <table class="w-full text-left border-collapse text-xs">
                  <thead class="bg-slate-950/90 text-slate-400 font-mono text-[11px] uppercase tracking-wider sticky top-0 z-10 border-b border-slate-800">
                    <tr>
                      <th class="py-3 px-4">Item</th>
                      <th class="py-3 px-4">Key / ID</th>
                      <th class="py-3 px-4">Type</th>
                      <th class="py-3 px-4">Location</th>
                      <th class="py-3 px-4">States</th>
                      <th class="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-slate-800/60">
                    <tr
                      v-for="(item, itmIdx) in filteredItems"
                      :key="itmIdx"
                      class="hover:bg-slate-800/40 transition-colors group"
                    >
                      <!-- Item Icon & Name -->
                      <td class="py-3 px-4">
                        <div class="flex items-center gap-3">
                          <div class="w-8 h-8 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-center shrink-0 overflow-hidden text-cyan-400">
                            <img v-if="item.image_url" :src="getImageUrl(item.image_url)" class="w-full h-full object-cover" />
                            <i v-else :class="[getItemIcon(item.name, item.item_type), 'text-sm']"></i>
                          </div>
                          <div>
                            <div class="font-bold text-white group-hover:text-cyan-300 transition-colors">{{ item.name }}</div>
                            <div v-if="item.description" class="text-[10px] text-slate-400 truncate max-w-xs">{{ item.description }}</div>
                          </div>
                        </div>
                      </td>

                      <!-- ID -->
                      <td class="py-3 px-4 font-mono text-[11px] text-slate-400">
                        <span class="bg-slate-950/80 px-2 py-0.5 rounded border border-slate-800">{{ item.id }}</span>
                      </td>

                      <!-- Type -->
                      <td class="py-3 px-4">
                        <span class="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-slate-950 border border-slate-800 text-slate-300">
                          {{ item.item_type || 'ITEM' }}
                        </span>
                      </td>

                      <!-- Location -->
                      <td class="py-3 px-4 font-medium">
                        <span
                          class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold"
                          :class="[
                            item.location_type === 'avatar' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' :
                            item.location_type === 'container' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' :
                            item.location_type === 'npc' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40' :
                            'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                          ]"
                        >
                          <Compass class="w-3 h-3" />
                          {{ item.location_name }}
                        </span>
                      </td>

                      <!-- States -->
                      <td class="py-3 px-4">
                        <div class="flex items-center gap-1.5 flex-wrap">
                          <!-- Hidden State -->
                          <span
                            class="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider"
                            :class="item.is_hidden ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-emerald-500/10 text-emerald-400'"
                          >
                            {{ item.is_hidden ? 'Hidden' : 'Visible' }}
                          </span>
                          <!-- Lock State -->
                          <span
                            v-if="item.is_locked !== undefined"
                            class="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider"
                            :class="item.is_locked ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-slate-800 text-slate-400'"
                          >
                            {{ item.is_locked ? 'Locked' : 'Unlocked' }}
                          </span>
                          <!-- Switch State -->
                          <span
                            v-if="item.switch_state"
                            class="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                          >
                            {{ item.switch_state }}
                          </span>
                        </div>
                      </td>

                      <!-- Actions -->
                      <td class="py-3 px-4 text-right">
                        <div class="flex items-center justify-end gap-1.5">
                          <button
                            v-if="item.is_hidden"
                            type="button"
                            @click="runCmd(`/debug unhide ${item.id}`)"
                            class="px-2 py-1 rounded bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 font-bold uppercase text-[10px] transition-all cursor-pointer"
                            title="Unhide this item"
                          >
                            Unhide
                          </button>
                          <button
                            v-if="item.location_type === 'avatar'"
                            type="button"
                            @click="runCmd(`/debug delete_item ${item.id}`)"
                            class="px-2 py-1 rounded bg-red-500/20 hover:bg-red-500/30 text-red-300 font-bold uppercase text-[10px] transition-all cursor-pointer"
                            title="Delete from Hero inventory"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>

                <div v-if="!filteredItems.length" class="py-16 text-center text-slate-500 font-semibold">
                  No items match the active filters.
                </div>
              </div>
            </section>

            <!-- ========================================================= -->
            <!-- TAB 4: DIAGNOSTICS & RAW JSON INSPECTOR -->
            <!-- ========================================================= -->
            <section v-else-if="activeTab === 'diagnostics'" class="flex-1 flex flex-col min-h-0 p-4 sm:p-6 overflow-y-auto custom-scrollbar space-y-6">
              <!-- Quick Action Triggers Grid -->
              <div class="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
                <h4 class="text-xs font-black uppercase tracking-[0.2em] text-cyan-400 mb-3 flex items-center gap-2">
                  <Flame class="w-4 h-4 text-amber-400" />
                  <span>Instant Debug Commands</span>
                </h4>
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  <button
                    type="button"
                    @click="runCmd('/debug reveal_map')"
                    class="p-2.5 rounded-xl bg-slate-950 hover:bg-cyan-500/10 border border-slate-800 hover:border-cyan-500/40 text-slate-300 hover:text-cyan-300 text-xs font-bold transition-all text-left flex items-center gap-2 cursor-pointer"
                  >
                    <Eye class="w-4 h-4 text-cyan-400" />
                    <span>Reveal All Map</span>
                  </button>
                  <button
                    type="button"
                    @click="runCmd('/debug walkthrough')"
                    class="p-2.5 rounded-xl bg-slate-950 hover:bg-amber-500/10 border border-slate-800 hover:border-amber-500/40 text-slate-300 hover:text-amber-300 text-xs font-bold transition-all text-left flex items-center gap-2 cursor-pointer"
                  >
                    <Sparkles class="w-4 h-4 text-amber-400" />
                    <span>Free Walkthrough</span>
                  </button>
                  <button
                    type="button"
                    @click="runCmd('/debug unhide all')"
                    class="p-2.5 rounded-xl bg-slate-950 hover:bg-purple-500/10 border border-slate-800 hover:border-purple-500/40 text-slate-300 hover:text-purple-300 text-xs font-bold transition-all text-left flex items-center gap-2 cursor-pointer"
                  >
                    <Unlock class="w-4 h-4 text-purple-400" />
                    <span>Unhide All</span>
                  </button>
                  <button
                    type="button"
                    @click="runCmd('/debug npc drop_items')"
                    class="p-2.5 rounded-xl bg-slate-950 hover:bg-emerald-500/10 border border-slate-800 hover:border-emerald-500/40 text-slate-300 hover:text-emerald-300 text-xs font-bold transition-all text-left flex items-center gap-2 cursor-pointer"
                  >
                    <Package class="w-4 h-4 text-emerald-400" />
                    <span>NPC Drop Items</span>
                  </button>
                  <button
                    type="button"
                    @click="runCmd('/debug awards')"
                    class="p-2.5 rounded-xl bg-slate-950 hover:bg-amber-500/10 border border-slate-800 hover:border-amber-500/40 text-slate-300 hover:text-amber-300 text-xs font-bold transition-all text-left flex items-center gap-2 cursor-pointer"
                  >
                    <Trophy class="w-4 h-4 text-amber-400" />
                    <span>Claim Awards</span>
                  </button>
                  <button
                    type="button"
                    @click="runCmd('/debug win_fight')"
                    class="p-2.5 rounded-xl bg-slate-950 hover:bg-emerald-500/10 border border-slate-800 hover:border-emerald-500/40 text-slate-300 hover:text-emerald-300 text-xs font-bold transition-all text-left flex items-center gap-2 cursor-pointer"
                  >
                    <Swords class="w-4 h-4 text-emerald-400" />
                    <span>Win Combat</span>
                  </button>
                  <button
                    type="button"
                    @click="runCmd('/debug exp 500')"
                    class="p-2.5 rounded-xl bg-slate-950 hover:bg-cyan-500/10 border border-slate-800 hover:border-cyan-500/40 text-slate-300 hover:text-cyan-300 text-xs font-bold transition-all text-left flex items-center gap-2 cursor-pointer"
                  >
                    <Zap class="w-4 h-4 text-cyan-400" />
                    <span>+500 Hero XP</span>
                  </button>
                  <button
                    type="button"
                    @click="runCmd('/debug log on')"
                    class="p-2.5 rounded-xl bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-300 text-xs font-bold transition-all text-left flex items-center gap-2 cursor-pointer"
                  >
                    <Terminal class="w-4 h-4 text-slate-400" />
                    <span>Toggle Logs</span>
                  </button>
                </div>

                <!-- Custom Command Line Input -->
                <div class="mt-3.5 flex items-center gap-2">
                  <div class="relative flex-1">
                    <input
                      v-model="customCommandInput"
                      type="text"
                      placeholder="Type any debug command, e.g. /debug heal or /debug session..."
                      class="w-full bg-slate-950 border border-slate-700/80 rounded-xl px-4 py-2 text-xs font-mono text-cyan-300 placeholder-slate-600 focus:outline-none focus:border-cyan-400"
                      @keydown.enter="customCommandInput.trim() && runCmd(customCommandInput.trim())"
                    />
                  </div>
                  <button
                    type="button"
                    @click="customCommandInput.trim() && runCmd(customCommandInput.trim())"
                    class="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-black uppercase text-xs tracking-wider transition-all cursor-pointer shadow-md"
                  >
                    Send
                  </button>
                </div>
              </div>

              <!-- Raw State JSON Tree -->
              <div class="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
                <div class="flex items-center justify-between gap-3 mb-3">
                  <h4 class="text-xs font-black uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-2">
                    <Layers class="w-4 h-4" />
                    <span>Session Runtime JSON</span>
                  </h4>
                  <button
                    type="button"
                    @click="copyRawJson"
                    class="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-slate-950 border border-slate-700 hover:border-cyan-400 text-slate-300 hover:text-cyan-300 text-xs font-bold transition-all cursor-pointer"
                  >
                    <Check v-if="copySuccess" class="w-3.5 h-3.5 text-emerald-400" />
                    <Copy v-else class="w-3.5 h-3.5" />
                    <span>{{ copySuccess ? 'Copied!' : 'Copy JSON' }}</span>
                  </button>
                </div>
                <pre class="p-4 rounded-xl bg-black/60 border border-slate-800/80 text-cyan-300/90 font-mono text-xs overflow-x-auto max-h-96 custom-scrollbar whitespace-pre-wrap break-all leading-relaxed">{{ rawJsonString }}</pre>
              </div>
            </section>
          </main>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.25s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@keyframes modalIn {
  from { opacity: 0; transform: scale(0.98) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
.animate-modal-in { animation: modalIn 0.25s cubic-bezier(0.16, 1, 0.3, 1); }

.custom-scrollbar::-webkit-scrollbar { width: 5px; height: 5px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(6, 182, 212, 0.2); border-radius: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(6, 182, 212, 0.4); }
</style>
