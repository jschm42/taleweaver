<script setup lang="ts">
/**
 * MapModal — Renders the world map as an interactive, premium HTML/CSS/SVG overlay.
 *
 * Props:
 *   open        — controls modal visibility
 *   mapData     — the raw graph data (nodes + edges)
 *   nodes       — metadata for tooltips (scene details)
 *
 * Emits: close
 */
import { watch, ref, nextTick, onMounted, computed } from 'vue'
import dagre from 'dagre'
import mapSvg from '@/assets/svg/fantasy-rpg-map.svg'
import type { WorldMapData } from '@/types'

const props = defineProps<{
  open: boolean
  mapData: WorldMapData | null
  nodes: Record<string, any>
  isDebug?: boolean
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const mapContainer = ref<HTMLDivElement | null>(null)

// Tooltip State
const hoveredNodeId = ref<string | null>(null)
const hoveredNode = ref<any | null>(null)
const tooltipPos = ref({ x: 0, y: 0 })

// Exit Tooltip State
const hoveredExit = ref<{
  label: string
  from: string
  to: string
  isLocked: boolean
} | null>(null)
const hoveredExitPos = ref({ x: 0, y: 0 })

// Zoom & Pan State
const zoom = ref(1)
const offset = ref({ x: 0, y: 0 })
const isPanning = ref(false)
const lastMousePos = ref({ x: 0, y: 0 })

const margin = 100
const EXIT_CIRCLE_EDGE_OFFSET = 30

const mysteriousSayings = [
  "The shadows here seem to whisper secrets...",
  "A path into the unknown. Dare you enter?",
  "Something waits in the darkness.",
  "The air grows cold as you look this way.",
  "A mystery yet to be solved.",
  "Beyond this point, the map is blank.",
  "Curiosity killed the cat, but satisfaction brought it back.",
  "What lies ahead? Only one way to find out.",
  "The fog of war hides many things.",
  "A place where legends are born... or forgotten."
]

const mysteriousSaying = computed(() => {
  if (!hoveredNode.value?.isUnknown && hoveredNode.value?.label !== '?') return ''
  const id = hoveredNode.value?.id || 'unknown'
  let hash = 0
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i)
    hash |= 0
  }
  const index = Math.abs(hash) % mysteriousSayings.length
  return mysteriousSayings[index]
})

function resetView() {
  zoom.value = 1
  offset.value = { x: 0, y: 0 }
}

function safeId(raw: string): string {
  if (!raw) return ''
  return raw.replace(/-/g, '_')
            .split('')
            .map(c => /[\p{L}\p{N}_]/u.test(c) ? c : '_')
            .join('')
            .toUpperCase()
}

// Reactive layout structure
const layoutData = ref<{
  nodes: Array<{
    id: string
    label: string
    x: number
    y: number
    width: number
    height: number
    isCurrent: boolean
    isVisited: boolean
    isUnknown: boolean
    imageUrl: string | null
    description: string
  }>
  edges: Array<{
    from: string
    to: string
    points: Array<{ x: number, y: number }>
    label: string
    isLocked: boolean
    exitType: string
    isBidirectional: boolean
  }>
  width: number
  height: number
} | null>(null)

function updateLayout() {
  if (!props.mapData) {
    layoutData.value = null
    return
  }

  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 64, edgesep: 40, ranksep: 110 })
  g.setDefaultEdgeLabel(() => ({}))

  const visitedIdsList = Object.keys(props.mapData.nodes).sort()
  const firstId = visitedIdsList[0]
  const visitedIds = new Set(visitedIdsList)
  const currentId = props.mapData.current_scene_id
  if (currentId) visitedIds.add(currentId)

  // 1. Set Nodes in graph
  visitedIds.forEach(id => {
    // 160x120 premium card size
    g.setNode(id, { width: 160, height: 120 })
  })

  // 2. Set Edges
  props.mapData.edges.forEach(edge => {
    const fromId = safeId(edge.from)
    const toId = safeId(edge.to)
    if (!g.hasNode(fromId) || !g.hasNode(toId)) return
    g.setEdge(fromId, toId, {
      label: edge.label || '',
      isLocked: edge.is_locked || false,
      exitType: edge.exit_type || 'one_way'
    })
  })

  dagre.layout(g)

  const graphInfo = g.graph()

  const nodes = g.nodes().map(id => {
    const node = g.node(id)
    const sessionNode = props.mapData!.nodes[id]
    const isUnknown = !!sessionNode?.is_unknown
    const isCurrent = id === currentId
    const isVisited = !!sessionNode && !isUnknown
    const dbNode = props.nodes[id] || {}

    return {
      id,
      label: isUnknown ? '?' : (sessionNode?.label || dbNode.label || id),
      x: node.x,
      y: node.y,
      width: node.width,
      height: node.height,
      isCurrent,
      isVisited,
      isUnknown,
      imageUrl: isUnknown ? null : (sessionNode?.image_url || dbNode.image_url || null),
      description: isUnknown ? '' : (sessionNode?.description || dbNode.description || '')
    }
  })

  const edges = g.edges().map(e => {
    const edge = g.edge(e)
    const rawEdge = props.mapData!.edges.find(re => 
      (safeId(re.from) === e.v && safeId(re.to) === e.w) ||
      (safeId(re.from) === e.w && safeId(re.to) === e.v)
    ) || {}
    const exitType = edge.exitType || rawEdge.exit_type || 'one_way'
    return {
      from: e.v,
      to: e.w,
      points: edge.points || [],
      label: edge.label || rawEdge.label || '',
      isLocked: edge.isLocked || rawEdge.is_locked || false,
      exitType,
      isBidirectional: exitType === 'bidirectional'
    }
  })

  layoutData.value = {
    nodes,
    edges,
    width: graphInfo.width || 800,
    height: graphInfo.height || 600
  }
}

// Compute exit circles positions at the ends of paths
const exitCircles = computed(() => {
  if (!layoutData.value) return []
  const circles: Array<{
    id: string
    x: number
    y: number
    from: string
    to: string
    label: string
    isLocked: boolean
    exitType: string
  }> = []

  layoutData.value.edges.forEach((edge, edgeIdx) => {
    const points = edge.points
    if (!points || points.length < 2) return

    // Circle at the end of the edge (pointing to 'to' scene)
    const endPoint = points[points.length - 1]
    const beforeEndPoint = points[points.length - 2]
    const endCirclePoint = movePointToward(endPoint, beforeEndPoint, EXIT_CIRCLE_EDGE_OFFSET)
    const fromNode = layoutData.value!.nodes.find(n => n.id === edge.from)
    const toNode = layoutData.value!.nodes.find(n => n.id === edge.to)
    circles.push({
      id: `exit-end-${edgeIdx}`,
      x: endCirclePoint.x + margin,
      y: endCirclePoint.y + margin,
      from: fromNode?.label || edge.from,
      to: toNode?.label || edge.to,
      label: edge.label || `Exit to ${toNode?.label || edge.to}`,
      isLocked: edge.isLocked,
      exitType: edge.exitType
    })

    // If bidirectional, also add a circle at the start of the edge (pointing back to 'from' scene)
    if (edge.isBidirectional) {
      const startPoint = points[0]
      const afterStartPoint = points[1]
      const startCirclePoint = movePointToward(startPoint, afterStartPoint, EXIT_CIRCLE_EDGE_OFFSET)
      circles.push({
        id: `exit-start-${edgeIdx}`,
        x: startCirclePoint.x + margin,
        y: startCirclePoint.y + margin,
        from: toNode?.label || edge.to,
        to: fromNode?.label || edge.from,
        label: edge.label || `Exit to ${fromNode?.label || edge.from}`,
        isLocked: edge.isLocked,
        exitType: edge.exitType
      })
    }
  })

  return circles
})

function movePointToward(
  anchor: { x: number; y: number },
  toward: { x: number; y: number } | undefined,
  distance: number
) {
  if (!toward || distance <= 0) return anchor
  const dx = toward.x - anchor.x
  const dy = toward.y - anchor.y
  const length = Math.hypot(dx, dy)
  if (!Number.isFinite(length) || length <= 0.0001) return anchor
  const step = Math.min(distance, length - 0.5)
  if (step <= 0) return anchor
  return {
    x: anchor.x + (dx / length) * step,
    y: anchor.y + (dy / length) * step
  }
}

function getEdgePath(points: Array<{ x: number, y: number }>) {
  if (!points || points.length === 0) return ''
  return `M ${points[0].x + margin} ${points[0].y + margin} ` +
         points.slice(1).map(p => `L ${p.x + margin} ${p.y + margin}`).join(' ')
}

// Mouse controls for viewport panning and zooming
function handleMouseMove(e: MouseEvent) {
  if (isPanning.value) {
    offset.value.x += e.clientX - lastMousePos.value.x
    offset.value.y += e.clientY - lastMousePos.value.y
    lastMousePos.value = { x: e.clientX, y: e.clientY }
  }
}

function handleMouseDown(e: MouseEvent) {
  if (e.button === 0) {
    isPanning.value = true
    lastMousePos.value = { x: e.clientX, y: e.clientY }
  }
}

function handleMouseUp() {
  isPanning.value = false
}

function handleWheel(e: WheelEvent) {
  e.preventDefault()
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  zoom.value = Math.max(0.2, Math.min(3, zoom.value * delta))
}

// Handlers for node tooltips
function handleNodeMouseEnter(node: any, event: MouseEvent) {
  hoveredNodeId.value = node.id
  hoveredNode.value = node
  tooltipPos.value = { x: event.clientX, y: event.clientY }
}

function handleNodeMouseLeave() {
  hoveredNodeId.value = null
  hoveredNode.value = null
}

function handleNodeMouseMove(event: MouseEvent) {
  tooltipPos.value = { x: event.clientX, y: event.clientY }
}

// Handlers for exit tooltips
function handleExitMouseEnter(exit: any, event: MouseEvent) {
  hoveredExit.value = {
    label: exit.label,
    from: exit.from,
    to: exit.to,
    isLocked: exit.isLocked
  }
  hoveredExitPos.value = { x: event.clientX, y: event.clientY }
}

function handleExitMouseLeave() {
  hoveredExit.value = null
}

function handleExitMouseMove(event: MouseEvent) {
  hoveredExitPos.value = { x: event.clientX, y: event.clientY }
}

watch(() => [props.open, props.mapData], () => {
  if (props.open) {
    updateLayout()
  }
})

onMounted(() => {
  if (props.open) {
    updateLayout()
  }
})
</script>

<template>
  <!-- Backdrop -->
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <!-- Overlay -->
        <div
          class="absolute inset-0 bg-black/75 backdrop-blur-sm"
          @click="emit('close')"
        />

        <!-- Modal panel -->
        <div class="relative z-10 w-full max-w-5xl h-[80vh] bg-slate-900 border border-slate-700 rounded-3xl shadow-2xl flex flex-col overflow-hidden animate-modal-in">
          <!-- Header -->
          <div class="flex items-center justify-between px-8 py-5 border-b border-slate-800 shrink-0">
            <div class="flex items-center gap-3">
              <i class="ra ra-map text-2xl text-emerald-500"></i>
              <div>
                <h2 class="text-xl font-bold text-white">World Map</h2>
                <p class="text-xs text-slate-400 mt-0.5">Tactical Sketch of your journey</p>
              </div>
            </div>
            <div class="flex items-center gap-4">
              <!-- Legend -->
              <div class="hidden sm:flex items-center gap-4 text-xxs text-slate-400">
                <span class="flex items-center gap-1.5">
                  <span class="inline-block w-3 h-3 rounded-md bg-emerald-950 border border-emerald-500 shadow-sm shadow-emerald-500/50"></span> Current Location
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="inline-block w-3 h-3 rounded-md bg-slate-900 border border-slate-700"></span> Visited
                </span>
                <span class="flex items-center gap-1.5">
                  <!-- One-way arrow symbol -->
                  <svg width="22" height="10" viewBox="0 0 22 10" class="inline-block">
                    <line x1="1" y1="5" x2="16" y2="5" stroke="#f97316" stroke-width="2"/>
                    <polygon points="14,1 21,5 14,9" fill="#f97316"/>
                  </svg>
                  One-way
                </span>
                <span class="flex items-center gap-1.5">
                  <!-- Bidirectional line symbol -->
                  <svg width="22" height="10" viewBox="0 0 22 10" class="inline-block">
                    <circle cx="2" cy="5" r="2.5" fill="#ffd97d"/>
                    <line x1="4" y1="5" x2="18" y2="5" stroke="#ffd97d" stroke-width="2"/>
                    <circle cx="20" cy="5" r="2.5" fill="#ffd97d"/>
                  </svg>
                  Two-way
                </span>
              </div>
              
              <!-- Map Controls -->
              <div class="flex items-center bg-slate-800/50 rounded-full px-1.5 py-1 border border-slate-700/50 gap-1">
                <button 
                  @click="zoom = Math.max(0.2, zoom - 0.1)" 
                  class="p-1.5 rounded-full text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                  title="Zoom Out"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
                  </svg>
                </button>
                <span class="text-xxs font-mono text-slate-500 min-w-[3rem] text-center">{{ Math.round(zoom * 100) }}%</span>
                <button 
                  @click="zoom = Math.min(3, zoom + 0.1)" 
                  class="p-1.5 rounded-full text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                  title="Zoom In"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                  </svg>
                </button>
                <div class="w-px h-4 bg-slate-700 mx-1"></div>
                <button 
                  @click="resetView" 
                  class="p-1.5 rounded-full text-slate-400 hover:text-emerald-400 hover:bg-slate-700 transition-colors"
                  title="Reset View"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </button>
              </div>

              <button
                @click="emit('close')"
                class="p-2 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                title="Close"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          <!-- Map Container -->
          <div class="flex-grow overflow-auto p-6 relative bg-slate-950 bg-radial-gradient" ref="mapContainer">
            <!-- Empty state -->
            <div
              v-if="!mapData"
              class="absolute inset-0 flex flex-col items-center justify-center text-slate-600"
            >
              <i class="ra ra-compass text-6xl mb-4 opacity-50"></i>
              <p class="text-lg font-medium">No map data yet</p>
              <p class="text-sm mt-1">Start your adventure to reveal the world.</p>
            </div>

            <!-- Redesigned view layer -->
            <div
              v-else
              class="w-full h-full flex items-center justify-center relative z-10 select-none overflow-hidden"
              @wheel="handleWheel"
              @mousedown="handleMouseDown"
              @mousemove="handleMouseMove"
              @mouseup="handleMouseUp"
              @mouseleave="handleMouseUp"
            >
              <!-- Viewport container that gets translated/zoomed -->
              <div 
                class="relative origin-center will-change-transform cursor-grab active:cursor-grabbing"
                :style="{ 
                  width: (layoutData?.width || 800) + margin * 2 + 'px',
                  height: (layoutData?.height || 600) + margin * 2 + 'px',
                  transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
                  transformOrigin: 'center center'
                }"
              >
                <!-- SVG overlay for connections/edges -->
                <svg 
                  class="absolute inset-0 pointer-events-none z-0"
                  :width="(layoutData?.width || 800) + margin * 2"
                  :height="(layoutData?.height || 600) + margin * 2"
                >
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

                  <!-- Draw SVG edge paths -->
                  <g v-if="layoutData">
                    <path
                      v-for="(edge, idx) in layoutData.edges"
                      :key="idx"
                      :d="getEdgePath(edge.points)"
                      :stroke="edge.isBidirectional ? '#ffd97d' : '#f97316'"
                      :stroke-width="edge.isLocked ? 2 : 2.5"
                      :stroke-dasharray="edge.isLocked ? '6,5' : 'none'"
                      fill="none"
                      class="transition-opacity duration-300"
                      :class="{ 'opacity-50': edge.isLocked }"
                      :marker-end="edge.isBidirectional ? 'url(#dot-bidir)' : 'url(#arrow-oneway)'"
                      :marker-start="edge.isBidirectional ? 'url(#dot-bidir)' : 'none'"
                    />
                  </g>
                </svg>

                <!-- Node HTML Cards -->
                <div v-if="layoutData" class="absolute inset-0 pointer-events-none z-10">
                  <div
                    v-for="node in layoutData.nodes"
                    :key="node.id"
                    class="absolute pointer-events-auto cursor-pointer group"
                    :style="{
                      left: (node.x - node.width / 2 + margin) + 'px',
                      top: (node.y - node.height / 2 + margin) + 'px',
                      width: node.width + 'px',
                      height: node.height + 'px'
                    }"
                    @mouseenter="handleNodeMouseEnter(node, $event)"
                    @mouseleave="handleNodeMouseLeave"
                    @mousemove="handleNodeMouseMove($event)"
                  >
                    <!-- Modern card showing scene thumbnail -->
                    <div 
                      class="w-full h-full rounded-2xl border bg-slate-900 overflow-hidden flex flex-col transition-all duration-300 shadow-lg group-hover:scale-105 group-hover:shadow-2xl"
                      :class="[
                        node.isCurrent 
                          ? 'border-emerald-500 shadow-emerald-950/50 shadow-md ring-2 ring-emerald-500/30' 
                          : node.isUnknown 
                            ? 'border-slate-800 bg-slate-950/80 border-dashed' 
                            : 'border-slate-700 hover:border-amber-500/50'
                      ]"
                    >
                      <!-- Thumbnail area -->
                      <div class="flex-grow relative bg-slate-950 overflow-hidden">
                        <div v-if="node.isUnknown" class="w-full h-full flex items-center justify-center bg-black/60">
                          <span class="text-4xl font-extrabold text-slate-750 group-hover:scale-110 group-hover:text-slate-650 transition-all duration-300">?</span>
                        </div>
                        <template v-else>
                          <img 
                            v-if="node.imageUrl" 
                            :src="node.imageUrl" 
                            class="w-full h-full object-cover transition-transform duration-505 group-hover:scale-110" 
                          />
                          <div 
                            v-else 
                            class="w-full h-full flex items-center justify-center bg-slate-850 text-slate-600"
                          >
                            <i class="ra ra-compass text-3xl opacity-40"></i>
                          </div>
                          <div class="absolute inset-0 bg-gradient-to-t from-slate-900/90 via-slate-900/20 to-transparent"></div>
                          
                          <!-- Map Pin Badge for Current Location -->
                          <span 
                            v-if="node.isCurrent" 
                            class="absolute top-2 right-2 bg-emerald-500 text-black text-[9px] font-black uppercase px-2 py-0.5 rounded-full flex items-center gap-1 shadow-md animate-pulse z-20"
                          >
                            <span class="w-1.5 h-1.5 rounded-full bg-black animate-ping"></span> Here
                          </span>
                        </template>
                      </div>

                      <!-- Text label bar -->
                      <div 
                        class="h-10 px-3 flex items-center justify-between shrink-0 bg-slate-900/95 border-t border-slate-800"
                        :class="{ 'bg-emerald-950/30 border-emerald-900/40': node.isCurrent }"
                      >
                        <span 
                          class="text-[11px] font-bold truncate tracking-wide"
                          :class="[
                            node.isCurrent 
                              ? 'text-emerald-400' 
                              : node.isUnknown 
                                ? 'text-slate-500 italic' 
                                : 'text-slate-200'
                          ]"
                        >
                          {{ node.label }}
                        </span>
                        <span v-if="!node.isUnknown && !node.isCurrent" class="text-[9px] text-slate-500 uppercase font-bold">Visited</span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Exit Interactive Circles at ends of paths -->
                <div v-if="layoutData" class="absolute inset-0 pointer-events-none z-20">
                  <div 
                    v-for="exit in exitCircles"
                    :key="exit.id"
                    class="absolute pointer-events-auto"
                    :style="{
                      left: (exit.x - 12) + 'px',
                      top: (exit.y - 12) + 'px',
                      width: '24px',
                      height: '24px'
                    }"
                    @mouseenter="handleExitMouseEnter(exit, $event)"
                    @mouseleave="handleExitMouseLeave"
                    @mousemove="handleExitMouseMove($event)"
                  >
                    <button 
                      class="w-full h-full rounded-full border flex items-center justify-center transition-all duration-300 shadow-md transform hover:scale-125"
                      :class="[
                        exit.isLocked
                          ? 'bg-amber-950 border-amber-500 text-amber-400 hover:bg-amber-900'
                          : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-emerald-500 hover:text-emerald-400'
                      ]"
                    >
                      <svg v-if="exit.isLocked" xmlns="http://www.w3.org/2050/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                      </svg>
                      <span v-else class="text-[7px] font-black uppercase font-mono">exit</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Background SVG Overlay -->
            <div 
              class="absolute inset-0 pointer-events-none opacity-[0.06] z-0"
              :style="{ 
                backgroundImage: `url(${mapSvg})`,
                backgroundSize: '85% auto',
                backgroundPosition: 'center',
                backgroundRepeat: 'no-repeat'
              }"
            ></div>

            <!-- Gradient Glow -->
            <div class="absolute inset-0 bg-gradient-to-tr from-emerald-500/5 via-transparent to-amber-500/5 pointer-events-none z-0"></div>

            <!-- HOVER TOOLTIP -->
            <Teleport to="body">
              <Transition name="tooltip">
                <div 
                  v-if="hoveredNode" 
                  class="fixed z-[100] pointer-events-none transition-all duration-75"
                  :style="{ left: (tooltipPos.x + 20) + 'px', top: (tooltipPos.y - 40) + 'px' }"
                >
                  <div class="w-72 bg-slate-900/95 border border-slate-700 rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] backdrop-blur-xl overflow-hidden flex flex-col animate-tooltip-in">
                    <!-- Unknown Node Content -->
                    <div v-if="hoveredNode.isUnknown || hoveredNode.label === '?'" class="p-8 bg-black flex flex-col items-center text-center">
                      <div class="w-16 h-16 rounded-full border-2 border-slate-800 flex items-center justify-center mb-4 animate-pulse">
                        <span class="text-4xl font-black text-slate-600">?</span>
                      </div>
                      <h3 class="text-lg font-bold text-white mb-2 uppercase tracking-widest">Terra Incognita</h3>
                      <p class="text-sm text-slate-400 italic leading-relaxed">
                        "{{ mysteriousSaying }}"
                      </p>
                    </div>

                    <!-- Known Node Content -->
                    <template v-else>
                      <!-- Image Area -->
                      <div v-if="hoveredNode.imageUrl" class="h-40 w-full relative">
                        <img :src="hoveredNode.imageUrl" class="absolute inset-0 w-full h-full object-cover" />
                        <div class="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent"></div>
                      </div>

                      <!-- Content -->
                      <div class="p-5 bg-slate-900">
                        <div class="flex items-center justify-between mb-2">
                          <span class="text-sm font-bold text-white uppercase tracking-wider">{{ hoveredNode.label || hoveredNode.id }}</span>
                          <div class="flex gap-1.5">
                            <span class="text-xxs px-1.5 py-0.5 rounded border border-emerald-500/30 text-emerald-400 font-mono uppercase">
                              Room
                            </span>
                          </div>
                        </div>
                        <p class="text-xs text-slate-400 leading-relaxed italic line-clamp-4">
                          {{ (hoveredNode.description && hoveredNode.description.trim()) ? hoveredNode.description : 'Explore closer to learn more about this area...' }}
                        </p>
                      </div>
                    </template>
                  </div>
                </div>
              </Transition>
            </Teleport>

            <!-- EXIT HOVER TOOLTIP -->
            <Teleport to="body">
              <Transition name="tooltip">
                <div 
                  v-if="hoveredExit" 
                  class="fixed z-[110] pointer-events-none transition-all duration-75"
                  :style="{ left: (hoveredExitPos.x + 20) + 'px', top: (hoveredExitPos.y - 40) + 'px' }"
                >
                  <div class="w-64 bg-slate-900/95 border border-slate-700 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] backdrop-blur-xl overflow-hidden flex flex-col p-4 animate-tooltip-in">
                    <div class="flex items-center justify-between mb-2 pb-2 border-b border-slate-800">
                      <span class="text-xs font-black uppercase text-slate-400 tracking-wider">Exit Connection</span>
                      <span 
                        class="text-[9px] px-2 py-0.5 rounded-full font-black uppercase tracking-tight"
                        :class="hoveredExit.isLocked ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'"
                      >
                        {{ hoveredExit.isLocked ? 'Locked' : 'Unlocked' }}
                      </span>
                    </div>
                    <p class="text-xs font-bold text-white mb-1 uppercase tracking-tight">{{ hoveredExit.label }}</p>
                    <div class="text-[10px] text-slate-400 mt-1 flex items-center gap-1.5">
                      <span>{{ hoveredExit.from }}</span>
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                      </svg>
                      <span class="text-white">{{ hoveredExit.to }}</span>
                    </div>
                    <p v-if="hoveredExit.isLocked" class="text-[10px] text-amber-400 mt-2 italic">
                      <i class="ra ra-key mr-1"></i> Check room options to find a way to unlock this exit.
                    </p>
                  </div>
                </div>
              </Transition>
            </Teleport>
          </div>

          <!-- Footer hint -->
          <div class="px-8 py-3 border-t border-slate-800 text-xs text-slate-600 flex justify-between items-center shrink-0">
            <div class="flex gap-4">
              <span><i class="ra ra-plain-dagger mr-1"></i> Drag to pan</span>
              <span><i class="ra ra-scroll-unfurled mr-1"></i> Scroll to zoom</span>
            </div>
            <span>Tip: hover over rooms and exit circles for details • rendered dynamically</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.bg-radial-gradient {
  background: radial-gradient(circle at center, #0f172a 0%, #020617 100%);
}

.will-change-transform {
  will-change: transform;
}

/* Tooltip Animations */
.tooltip-enter-active, .tooltip-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.tooltip-enter-from, .tooltip-leave-to { opacity: 0; transform: scale(0.96) translateY(4px); }

.animate-tooltip-in {
  animation: toolTipIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes toolTipIn {
  from { opacity: 0; transform: translateY(6px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.animate-modal-in {
  animation: modalIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes modalIn {
  from {
    opacity: 0;
    transform: scale(0.97) translateY(8px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

svg {
  filter: drop-shadow(0 0 8px rgba(0,0,0,0.5));
}
</style>
