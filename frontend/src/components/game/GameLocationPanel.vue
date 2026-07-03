<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown, ChevronRight, Compass, List, DoorClosed, DoorClosedLocked, Search } from 'lucide-vue-next'
import dagre from 'dagre'
import { getItemIcon, getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'

interface SceneHoverPayload {
  id: string
  name: string
  description: string
  image_url?: string | null
  entity_type: string
  is_locked?: boolean
}

const props = defineProps<{
  sceneId?: string | null
  sceneName?: string | null
  sceneDescription?: string | null
  sceneImage?: string | null
  showImage: (path?: string | null) => boolean
  isDebug?: boolean
  sceneExits: any[]
  mapData: any
  nodes: Record<string, any>
  isActionInputBlocked: boolean
  exitTraversalBusy: string
  exitUnlockBusy: boolean
}>()

const emit = defineEmits<{
  traverse: [exit: any]
  hover: [payload: any, event: MouseEvent]
  move: [event: MouseEvent]
  leave: []
  imageError: [path: string]
}>()

const hoverPayload = computed<SceneHoverPayload>(() => ({
  id: props.sceneId || '',
  name: props.sceneName || 'Current Scene',
  description: props.sceneDescription || 'The current location of your adventure.',
  image_url: props.sceneImage,
  entity_type: 'SCENE'
}))

const isOpen = ref(true)
const exitViewMode = ref<'cards' | 'radar'>('cards')

// Minimap zoom levels
const zoomLevel = ref(2) // Default is level 2 (0.35)

const cycleZoom = () => {
  zoomLevel.value = zoomLevel.value === 3 ? 1 : zoomLevel.value + 1
}

const currentScale = computed(() => {
  if (zoomLevel.value === 1) return 0.45
  if (zoomLevel.value === 2) return 0.35
  return 0.25
})

const zoomText = computed(() => {
  if (zoomLevel.value === 1) return 'Zoom: In'
  if (zoomLevel.value === 2) return 'Zoom: Mid'
  return 'Zoom: Out'
})

// Minimap layout logic
const margin = 100

const safeId = (raw: string): string => {
  if (!raw) return ''
  return raw.replace(/-/g, '_')
            .split('')
            .map(c => /[\p{L}\p{N}_]/u.test(c) ? c : '_')
            .join('')
            .toUpperCase()
}

const minimapLayout = computed(() => {
  if (!props.mapData || !props.mapData.nodes) return null

  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 64, edgesep: 40, ranksep: 110 })
  g.setDefaultEdgeLabel(() => ({}))

  const visitedIdsList = Object.keys(props.mapData.nodes).sort()
  const visitedIds = new Set(visitedIdsList)
  const currentId = props.mapData.current_scene_id
  if (currentId) visitedIds.add(currentId)

  // 1. Set Nodes in graph using safeId!
  visitedIds.forEach(id => {
    g.setNode(safeId(id), { width: 160, height: 120 })
  })

  // 2. Set Edges using safeId!
  const rawEdges = Array.isArray(props.mapData.edges) ? props.mapData.edges : []
  rawEdges.forEach(edge => {
    const fromId = safeId(edge.from)
    const toId = safeId(edge.to)
    if (!g.hasNode(fromId) || !g.hasNode(toId)) return
    g.setEdge(fromId, toId, {
      label: edge.label || '',
      isLocked: edge.is_locked || false,
      exitType: edge.exit_type || 'one_way'
    })
  })

  try {
    dagre.layout(g)
  } catch (e) {
    console.error("Dagre layout failed on minimap", e)
    return null
  }

  const graphInfo = g.graph()

  const mappedNodes = g.nodes().map(id => {
    const node = g.node(id)
    const sessionNodeKey = Object.keys(props.mapData.nodes).find(k => safeId(k) === id)
    const sessionNode = sessionNodeKey ? props.mapData.nodes[sessionNodeKey] : null
    const isUnknown = !!sessionNode?.is_unknown
    const isCurrent = id === safeId(currentId)
    const dbNode = props.nodes[id] || props.nodes[sessionNodeKey || ''] || {}

    return {
      id,
      label: isUnknown ? '?' : (sessionNode?.label || dbNode.label || id),
      x: node.x,
      y: node.y,
      width: node.width,
      height: node.height,
      isCurrent,
      isVisited: !!sessionNode && !isUnknown,
      isUnknown,
      imageUrl: isUnknown ? null : (sessionNode?.image_url || dbNode.image_url || null)
    }
  })

  const mappedEdges = g.edges().map(e => {
    const edge = g.edge(e)
    const rawEdge = rawEdges.find(re => 
      (safeId(re.from) === e.v && safeId(re.to) === e.w) ||
      (safeId(re.from) === e.w && safeId(re.to) === e.v)
    ) || {}
    const exitType = edge.exitType || rawEdge.exit_type || 'one_way'
    return {
      from: e.v,
      to: e.w,
      points: edge.points || [],
      isLocked: edge.isLocked || rawEdge.is_locked || false,
      exitType,
      isBidirectional: exitType === 'bidirectional'
    }
  })

  return {
    nodes: mappedNodes,
    edges: mappedEdges,
    width: graphInfo.width || 800,
    height: graphInfo.height || 600
  }
})

const getEdgePath = (points: Array<{ x: number, y: number }>) => {
  if (!points || points.length === 0) return ''
  return `M ${points[0].x + margin} ${points[0].y + margin} ` +
         points.slice(1).map(p => `L ${p.x + margin} ${p.y + margin}`).join(' ')
}

const truncateText = (text: string, len: number) => {
  if (!text) return ''
  return text.length > len ? text.slice(0, len) + '...' : text
}

const isNodeClickable = (node: any) => {
  if (node.isCurrent) return false
  return props.sceneExits.some((ex: any) => {
    const toIdNormalized = safeId(ex.to)
    const fromIdNormalized = safeId(ex.from)
    if (ex.direction === 'forward' && toIdNormalized === safeId(node.id)) {
      return true
    }
    if (ex.direction === 'backward' && fromIdNormalized === safeId(node.id)) {
      return true
    }
    return false
  })
}

const handleMinimapNodeClick = (node: any) => {
  if (node.isCurrent) return
  const exit = props.sceneExits.find((ex: any) => {
    const toIdNormalized = safeId(ex.to)
    const fromIdNormalized = safeId(ex.from)
    if (ex.direction === 'forward' && toIdNormalized === safeId(node.id)) {
      return true
    }
    if (ex.direction === 'backward' && fromIdNormalized === safeId(node.id)) {
      return true
    }
    return false
  })
  if (exit) {
    emit('traverse', exit)
  }
}

const minimapTransform = computed(() => {
  if (!minimapLayout.value) return ''
  const currentId = props.mapData?.current_scene_id
  const node = currentId
    ? minimapLayout.value.nodes.find(n => String(n.id).toUpperCase() === safeId(currentId))
    : minimapLayout.value.nodes[0]
  if (!node) return ''

  const H = 190
  const scale = currentScale.value

  const nodeCenterY = node.y + margin

  // Left-align current node's card: left edge at 20px from container boundary
  const cardLeftX = node.x - node.width / 2 + margin
  const tx = 20 - cardLeftX * scale
  const ty = H / 2 - nodeCenterY * scale

  return `translate(${tx}, ${ty}) scale(${scale})`
})

// Exit card helpers
const isExitLocked = (exit: any): boolean => {
  if (!exit) return false
  return Boolean(exit.is_locked)
}

const exitDisplayName = (exit: any): string => {
  if (!exit) return 'Exit'
  const raw = String(exit.label || '').trim()
  if (!raw) return 'Exit'
  const arrowMatch = raw.match(/^(.+?)\s*(?:->|→)\s*.+$/)
  if (arrowMatch) return arrowMatch[1].trim()
  return raw
}
</script>

<template>
  <div class="mb-8">
    <div class="flex items-center justify-between w-full mb-4 select-none">
      <button
        @click="isOpen = !isOpen"
        class="flex items-center gap-1.5 text-left focus:outline-none cursor-pointer"
      >
        <ChevronDown v-if="isOpen" class="w-3.5 h-3.5 text-slate-500 transition-all shrink-0" />
        <ChevronRight v-else class="w-3.5 h-3.5 text-slate-500 transition-all shrink-0" />
        <i class="ra ra-mountain-cave text-indigo-500"></i>
        <h3 class="text-xs font-bold uppercase tracking-[0.2em] text-indigo-500/80">Location</h3>
      </button>
      <button
        v-if="sceneExits.length > 0"
        @click.stop="exitViewMode = exitViewMode === 'cards' ? 'radar' : 'cards'"
        class="text-slate-400 hover:text-cyan-400 p-1 rounded hover:bg-slate-800/50 transition-colors flex items-center justify-center"
        :title="exitViewMode === 'cards' ? 'Show Minimap' : 'Show RPG Cards'"
      >
        <Compass v-if="exitViewMode === 'cards'" class="w-4 h-4" />
        <List v-else class="w-4 h-4" />
      </button>
    </div>
    <transition name="expand">
      <div v-show="isOpen" class="overflow-hidden">
        <!-- Scene Card (Hidden in Minimap Mode) -->
        <div
          v-if="exitViewMode === 'cards'"
          class="relative group cursor-help overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 transition-all hover:border-indigo-500/50"
          @mouseenter="emit('hover', hoverPayload, $event)"
          @mousemove="emit('move', $event)"
          @mouseleave="emit('leave')"
          @click="emit('hover', hoverPayload, $event)"
        >
          <div class="aspect-video w-full relative overflow-hidden bg-slate-900 flex items-center justify-center">
            <img
              v-if="sceneImage && showImage(sceneImage)"
              :src="getImageUrl(sceneImage, { thumbnail: true })"
              class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
              @error="(e) => {
                const target = e.target as HTMLImageElement
                if (target.src.includes('_thumb')) {
                  target.src = getOriginalImageUrl(sceneImage)
                } else {
                  emit('imageError', sceneImage!)
                }
              }"
            />
            <div v-else class="w-full h-full flex items-center justify-center bg-slate-800">
              <i :class="['ra text-7xl opacity-20', getItemIcon('SCENE'), 'text-indigo-400']"></i>
            </div>
            <div class="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-slate-950 to-transparent">
              <div class="flex items-center justify-between gap-2">
                <span class="text-xs font-bold text-white uppercase tracking-wider truncate block overflow-hidden shadow-sm">{{ sceneName || 'Unknown' }}</span>
                <span v-if="isDebug && sceneId" class="text-[10px] font-mono text-indigo-300 opacity-60">ID: {{ sceneId }}</span>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Exits/Minimap Container -->
        <div v-if="sceneExits.length > 0" :class="{ 'mt-4': exitViewMode === 'cards' }">
          <!-- RPG Cards View -->
          <div v-if="exitViewMode === 'cards'" class="grid grid-cols-2 gap-2">
            <div
              v-for="ex in sceneExits"
              :key="ex.id"
              role="button"
              tabindex="0"
              :aria-disabled="isActionInputBlocked || exitTraversalBusy === ex.id || exitUnlockBusy"
              :class="[
                'relative border rounded-xl group transition-all duration-300 p-2 flex items-center justify-between gap-2 text-left select-none outline-none focus:ring-2 focus:ring-cyan-500/50 backdrop-blur-md',
                (isActionInputBlocked || exitTraversalBusy === ex.id || exitUnlockBusy)
                  ? 'opacity-50 cursor-not-allowed pointer-events-none'
                  : 'cursor-pointer',
                isExitLocked(ex)
                  ? 'bg-rose-950/15 border-rose-900/30 hover:border-rose-500/60 hover:bg-rose-900/25 shadow-lg shadow-rose-950/10'
                  : 'bg-slate-950/30 border-slate-800/40 hover:border-cyan-500/50 hover:bg-slate-900/40 shadow-lg shadow-black/20'
              ]"
              @click.stop="emit('traverse', ex)"
              @keydown.enter="emit('traverse', ex)"
              @keydown.space.prevent="emit('traverse', ex)"
              @mouseenter="emit('hover', { id: ex.id, name: ex.label, description: ex.description || '', lock_description: ex.lock_description || '', entity_type: 'EXIT', is_locked: isExitLocked(ex) }, $event)"
              @mousemove="emit('move', $event)"
              @mouseleave="emit('leave')"
            >
              <!-- Left side: Door icon wrapper -->
              <div class="w-6 h-6 flex items-center justify-center shrink-0 transition-colors"
                   :class="isExitLocked(ex) ? 'text-rose-400' : 'text-cyan-400'">
                <DoorClosedLocked v-if="isExitLocked(ex)" class="w-5 h-5" />
                <DoorClosed v-else class="w-5 h-5" />
              </div>

              <!-- Center: name -->
              <span :class="['flex-grow text-[10.5px] font-bold truncate leading-tight select-none transition-colors',
                isExitLocked(ex) ? 'text-rose-200 group-hover:text-rose-100' : 'text-slate-100 group-hover:text-cyan-300']">
                {{ exitDisplayName(ex) }}
              </span>

            </div>
          </div>

          <!-- Mini Map View -->
          <div v-else class="relative border border-slate-800/40 bg-slate-950/20 backdrop-blur-md rounded-2xl flex items-center justify-center shadow-inner overflow-hidden h-[190px] w-full">
            <svg v-if="minimapLayout" class="w-full h-full select-none" viewBox="0 0 240 190">
              <defs>
                <!-- One-way arrowhead: bold single tip -->
                <marker
                  id="arrow-oneway"
                  viewBox="0 0 12 12"
                  refX="10"
                  refY="6"
                  markerWidth="7"
                  markerHeight="7"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 11 6 L 0 11 Z" fill="#f97316" />
                </marker>

                <!-- Bidirectional: small dot at both ends -->
                <marker
                  id="dot-bidir"
                  viewBox="0 0 10 10"
                  refX="5"
                  refY="5"
                  markerWidth="5"
                  markerHeight="5"
                  orient="auto"
                >
                  <circle cx="5" cy="5" r="3.5" fill="#ffd97d" />
                </marker>
              </defs>

              <g :transform="minimapTransform">
                <!-- Edges -->
                <path
                  v-for="(edge, idx) in minimapLayout.edges"
                  :key="idx"
                  :d="getEdgePath(edge.points)"
                  :stroke="edge.isBidirectional ? '#ffd97d' : '#f97316'"
                  :stroke-width="edge.isLocked ? 3 : 4"
                  :stroke-dasharray="edge.isLocked ? '8,6' : 'none'"
                  fill="none"
                  class="transition-opacity duration-300"
                  :class="{ 'opacity-50': edge.isLocked }"
                  :marker-end="edge.isBidirectional ? 'url(#dot-bidir)' : 'url(#arrow-oneway)'"
                  :marker-start="edge.isBidirectional ? 'url(#dot-bidir)' : 'none'"
                />

                <!-- Nodes -->
                <g
                  v-for="node in minimapLayout.nodes"
                  :key="node.id"
                  :transform="`translate(${node.x - node.width / 2 + margin}, ${node.y - node.height / 2 + margin})`"
                  :class="isNodeClickable(node) ? 'cursor-pointer hover:opacity-90' : 'cursor-default'"
                  @click.stop="handleMinimapNodeClick(node)"
                  @mouseenter="emit('hover', { id: node.id, name: node.label, description: node.isUnknown ? 'Terra Incognita' : (node.isCurrent ? 'Current scene' : (isNodeClickable(node) ? 'Click to travel' : '')), entity_type: 'SCENE' }, $event)"
                  @mousemove="emit('move', $event)"
                  @mouseleave="emit('leave')"
                >
                  <!-- Clip path for node thumbnail -->
                  <clipPath :id="'minimap-clip-' + node.id">
                    <rect x="1" y="1" :width="node.width - 2" :height="node.height - 30" rx="11" />
                  </clipPath>

                  <!-- Card Body -->
                  <rect
                    x="0"
                    y="0"
                    :width="node.width"
                    :height="node.height"
                    rx="12"
                    :class="[
                      'transition-all duration-300',
                      node.isCurrent 
                        ? 'fill-slate-900 stroke-emerald-500 stroke-[4]' 
                        : node.isUnknown 
                          ? 'fill-slate-950/85 stroke-slate-800 stroke-[2.5] stroke-dasharray-[6_4]' 
                          : 'fill-slate-900 stroke-slate-700 stroke-[3]'
                    ]"
                  />

                  <!-- Image / Placeholder -->
                  <g v-if="!node.isUnknown">
                    <image
                      v-if="node.imageUrl"
                      :href="getImageUrl(node.imageUrl, { thumbnail: true })"
                      x="0"
                      y="0"
                      :width="node.width"
                      :height="node.height - 30"
                      preserveAspectRatio="xMidYMid slice"
                      :clip-path="`url(#minimap-clip-${node.id})`"
                    />
                    <rect
                      v-else
                      x="0"
                      y="0"
                      :width="node.width"
                      :height="node.height - 30"
                      class="fill-slate-800/60"
                      :clip-path="`url(#minimap-clip-${node.id})`"
                    />
                    <g v-if="!node.imageUrl" :transform="`translate(${node.width / 2}, ${(node.height - 30) / 2})`" class="opacity-25 text-slate-400">
                      <circle cx="0" cy="0" r="16" class="fill-slate-700" />
                      <path d="M-6,-6 L6,-6 L6,6 L-6,6 Z" class="fill-none stroke-white stroke-[1.5]" />
                    </g>
                  </g>
                  <g v-else>
                    <rect
                      x="0"
                      y="0"
                      :width="node.width"
                      :height="node.height - 30"
                      class="fill-slate-950/50"
                      :clip-path="`url(#minimap-clip-${node.id})`"
                    />
                    <text
                      :x="node.width / 2"
                      :y="(node.height - 30) / 2 + 10"
                      text-anchor="middle"
                      class="fill-slate-650 text-3xl font-black select-none"
                    >
                      ?
                    </text>
                  </g>

                  <!-- Divider Line -->
                  <line
                    x1="0"
                    :y1="node.height - 30"
                    :x2="node.width"
                    :y2="node.height - 30"
                    class="stroke-slate-800 stroke-[2]"
                  />

                  <!-- Label -->
                  <text
                    x="10"
                    :y="node.height - 10"
                    class="text-[12px] font-bold select-none text-slate-200"
                    :class="[
                      node.isCurrent 
                        ? 'fill-emerald-400 font-extrabold' 
                        : node.isUnknown 
                          ? 'fill-slate-500 italic' 
                          : 'fill-slate-200'
                    ]"
                  >
                    {{ truncateText(node.label, 16) }}
                  </text>
                </g>
              </g>
            </svg>
            <div v-else class="text-slate-500 text-xs">Loading Minimap...</div>

            <!-- Zoom Button in the corner -->
            <button
              v-if="minimapLayout"
              @click.stop="cycleZoom"
              class="absolute bottom-2 right-2 bg-slate-900/90 hover:bg-slate-800 border border-slate-700/50 rounded-lg px-2 py-1 text-[10px] font-bold text-slate-300 hover:text-white transition-colors backdrop-blur-md select-none cursor-pointer flex items-center gap-1 shadow-md"
            >
              <Search class="w-3.5 h-3.5 text-slate-400" />
              <span>{{ zoomText }}</span>
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
/* Collapsible expansion animation */
.expand-enter-active,
.expand-leave-active {
  transition: max-height 0.3s ease-out, opacity 0.3s ease-out;
  max-height: 500px;
}
.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
