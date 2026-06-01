<script setup lang="ts">
/**
 * MapTab — Renders the adventure template scenes as an interactive world map.
 * Reuses Dagre for graph layouts and SVG/HTML rendering for visual excellence.
 */
import { watch, ref, nextTick, onMounted, computed } from 'vue'
import dagre from 'dagre'
import mapSvg from '@/assets/svg/fantasy-rpg-map.svg'
import { visualService } from '@/services/visualService'

const props = defineProps<{
  debugData: any
  editorScenes: any[]
  visualsCacheVersion?: number
}>()

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

const startSceneId = computed(() => {
  const adventureStart = props.debugData?.adventure?.start_scene_id || props.debugData?.adventure?.scene_id
  if (typeof adventureStart === 'string' && adventureStart.trim()) {
    return safeId(adventureStart)
  }
  const firstSceneId = props.editorScenes[0]?.id
  return typeof firstSceneId === 'string' && firstSceneId.trim() ? safeId(firstSceneId) : ''
})

// Zoom & Pan State
const zoom = ref(1)
const offset = ref({ x: 0, y: 0 })
const isPanning = ref(false)
const lastMousePos = ref({ x: 0, y: 0 })

const margin = 100

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
    isStart: boolean
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
  if (!props.editorScenes || props.editorScenes.length === 0) {
    layoutData.value = null
    return
  }

  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 80, edgesep: 40, ranksep: 140 })
  g.setDefaultEdgeLabel(() => ({}))

  // 1. Add all scenes as nodes
  props.editorScenes.forEach(scene => {
    const id = safeId(scene.id)
    g.setNode(id, { width: 160, height: 120 })
  })

  // 2. Add edges (exits)
  const exits = props.debugData?.exits || []
  exits.forEach((edge: any) => {
    const fromId = safeId(edge.from_scene_id)
    const toId = safeId(edge.to_scene_id)
    if (!g.hasNode(fromId) || !g.hasNode(toId)) return
    
    g.setEdge(fromId, toId, {
      label: edge.label || '',
      isLocked: !!edge.is_locked,
      exitType: edge.exit_type || 'one_way'
    })
  })

  dagre.layout(g)

  const graphInfo = g.graph()

  const nodes = g.nodes().map(id => {
    const node = g.node(id)
    const originalScene = props.editorScenes.find(s => safeId(s.id) === id) || {}
    const isStart = startSceneId.value === id

    return {
      id,
      label: originalScene.label || originalScene.name || id,
      x: node.x,
      y: node.y,
      width: node.width,
      height: node.height,
      isStart,
      imageUrl: originalScene.image_url || null,
      description: originalScene.description || ''
    }
  })

  const edges = g.edges().map(e => {
    const edge = g.edge(e)
    const rawExit = (props.debugData?.exits || []).find((re: any) => 
      (safeId(re.from_scene_id) === e.v && safeId(re.to_scene_id) === e.w) ||
      (safeId(re.from_scene_id) === e.w && safeId(re.to_scene_id) === e.v)
    ) || {}
    const exitType = edge.exitType || rawExit.exit_type || 'one_way'
    return {
      from: e.v,
      to: e.w,
      points: edge.points || [],
      label: edge.label || rawExit.label || '',
      isLocked: edge.isLocked || !!rawExit.is_locked,
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
    const toNode = layoutData.value!.nodes.find(n => n.id === edge.to)
    circles.push({
      id: `exit-end-${edgeIdx}`,
      x: endPoint.x + margin,
      y: endPoint.y + margin,
      from: edge.from,
      to: toNode?.label || edge.to,
      label: edge.label || `Exit to ${toNode?.label || edge.to}`,
      isLocked: edge.isLocked,
      exitType: edge.exitType
    })

    // If bidirectional, also add a circle at the start of the edge (pointing back to 'from' scene)
    if (edge.isBidirectional) {
      const startPoint = points[0]
      const fromNode = layoutData.value!.nodes.find(n => n.id === edge.from)
      circles.push({
        id: `exit-start-${edgeIdx}`,
        x: startPoint.x + margin,
        y: startPoint.y + margin,
        from: edge.to,
        to: fromNode?.label || edge.from,
        label: edge.label || `Exit to ${fromNode?.label || edge.from}`,
        isLocked: edge.isLocked,
        exitType: edge.exitType
      })
    }
  })

  return circles
})

function getEdgePath(points: Array<{ x: number, y: number }>) {
  if (!points || points.length === 0) return ''
  return `M ${points[0].x + margin} ${points[0].y + margin} ` +
         points.slice(1).map(p => `L ${p.x + margin} ${p.y + margin}`).join(' ')
}

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

function buildImageUrl(path?: string | null) {
  return visualService.buildImageUrl(path, props.visualsCacheVersion || 0)
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

watch(() => [props.editorScenes, props.debugData], () => {
  updateLayout()
}, { deep: true })

onMounted(() => {
  updateLayout()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header with controls -->
    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-slate-900/40 p-4 border border-white/5 rounded-2xl backdrop-blur-md">
      <div>
        <h2 class="text-lg font-bold text-white flex items-center gap-2">
          <i class="ra ra-map text-emerald-500"></i>
          World Map View
        </h2>
        <p class="text-xxs text-slate-400 uppercase tracking-widest mt-1">Interactive layout of scenes and connections</p>
      </div>

      <!-- Controls -->
      <div class="flex items-center bg-slate-800/50 rounded-full px-3 py-1.5 border border-slate-700/50 gap-2">
        <button 
          @click="zoom = Math.max(0.2, zoom - 0.1)" 
          class="p-1 rounded-full text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
          title="Zoom Out"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
          </svg>
        </button>
        <span class="text-xxs font-mono text-slate-300 min-w-[2.5rem] text-center">{{ Math.round(zoom * 100) }}%</span>
        <button 
          @click="zoom = Math.min(3, zoom + 0.1)" 
          class="p-1 rounded-full text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
          title="Zoom In"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
        </button>
        <div class="w-px h-4 bg-slate-700 mx-1"></div>
        <button 
          @click="resetView" 
          class="p-1 rounded-full text-slate-400 hover:text-emerald-400 hover:bg-slate-700 transition-colors"
          title="Reset View"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Map Canvas Window -->
    <div class="relative h-[65vh] bg-slate-950 border border-white/5 rounded-3xl overflow-hidden flex flex-col shadow-2xl bg-radial-gradient" ref="mapContainer">
      
      <!-- Empty state if no scenes -->
      <div
        v-if="!editorScenes.length"
        class="absolute inset-0 flex flex-col items-center justify-center text-slate-600 z-10"
      >
        <i class="ra ra-compass text-6xl mb-4 opacity-50"></i>
        <p class="text-lg font-medium">No scenes defined yet</p>
        <p class="text-sm mt-1">Add scenes in the Scenes tab to generate the map.</p>
      </div>

      <!-- Map Render HTML layer -->
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
              <marker 
                id="arrow-end" 
                viewBox="0 0 10 10" 
                refX="8" 
                refY="5" 
                markerWidth="6" 
                markerHeight="6" 
                orient="auto"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#ffd97d" />
              </marker>
              <marker 
                id="arrow-start" 
                viewBox="0 0 10 10" 
                refX="2" 
                refY="5" 
                markerWidth="6" 
                markerHeight="6" 
                orient="auto"
              >
                <path d="M 10 1 L 0 5 L 10 9 z" fill="#ffd97d" />
              </marker>
            </defs>

            <!-- Draw SVG edge paths -->
            <g v-if="layoutData">
              <path
                v-for="(edge, idx) in layoutData.edges"
                :key="idx"
                :d="getEdgePath(edge.points)"
                stroke="#ffd97d"
                :stroke-width="edge.isLocked ? 2 : 2.5"
                :stroke-dasharray="edge.isLocked ? '6,6' : 'none'"
                fill="none"
                class="transition-opacity duration-300"
                :class="{ 'opacity-60': edge.isLocked }"
                marker-end="url(#arrow-end)"
                :marker-start="edge.isBidirectional ? 'url(#arrow-start)' : 'none'"
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
              <!-- Modern node card with scene thumbnail -->
              <div 
                class="w-full h-full rounded-2xl border bg-slate-900 overflow-hidden flex flex-col transition-all duration-300 shadow-lg group-hover:scale-105 group-hover:shadow-2xl"
                :class="[
                  node.isStart 
                    ? 'border-emerald-500 shadow-emerald-950/50 shadow-md ring-2 ring-emerald-500/30' 
                    : 'border-slate-700 hover:border-amber-500/50'
                ]"
              >
                <!-- Thumbnail area -->
                <div class="flex-grow relative bg-slate-950 overflow-hidden">
                  <img 
                    v-if="node.imageUrl" 
                    :src="buildImageUrl(node.imageUrl)" 
                    class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" 
                  />
                  <div 
                    v-else 
                    class="w-full h-full flex items-center justify-center bg-slate-850 text-slate-650"
                  >
                    <i class="ra ra-compass text-3xl opacity-40"></i>
                  </div>
                  <div class="absolute inset-0 bg-gradient-to-t from-slate-900/90 via-slate-900/20 to-transparent"></div>
                  
                  <!-- Start scene indicator badge -->
                  <span 
                    v-if="node.isStart" 
                    class="absolute top-2 right-2 bg-emerald-500 text-black text-[9px] font-black uppercase px-2 py-0.5 rounded-full flex items-center gap-1 shadow-md z-20"
                  >
                    <span class="w-1.5 h-1.5 rounded-full bg-black"></span> Start
                  </span>
                </div>

                <!-- Text label bar -->
                <div 
                  class="h-10 px-3 flex items-center justify-between shrink-0 bg-slate-900/95 border-t border-slate-800"
                  :class="{ 'bg-emerald-950/30 border-emerald-900/40': node.isStart }"
                >
                  <span 
                    class="text-[11px] font-bold truncate tracking-wide"
                    :class="[
                      node.isStart 
                        ? 'text-emerald-400' 
                        : 'text-slate-200'
                    ]"
                  >
                    {{ node.label }}
                  </span>
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
                <svg v-if="exit.isLocked" xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
        class="absolute inset-0 pointer-events-none opacity-[0.04] z-0"
        :style="{ 
          backgroundImage: `url(${mapSvg})`,
          backgroundSize: '75% auto',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat'
        }"
      ></div>

      <!-- Gradient Glow -->
      <div class="absolute inset-0 bg-gradient-to-tr from-emerald-500/5 via-transparent to-amber-500/5 pointer-events-none z-0"></div>

      <!-- Bottom instruction & Legend overlays -->
      <div class="absolute bottom-4 left-4 right-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 pointer-events-none z-20">
        <div class="flex gap-4 text-xxs text-slate-400 bg-slate-900/80 px-4 py-2 border border-white/5 rounded-xl backdrop-blur-md">
          <span class="flex items-center gap-1.5">
            <span class="inline-block w-2.5 h-2.5 rounded bg-emerald-950 border border-emerald-500"></span> Start Scene
          </span>
          <span class="flex items-center gap-1.5">
            <span class="inline-block w-2.5 h-2.5 rounded bg-slate-900 border border-slate-700"></span> Regular Scene
          </span>
          <span class="flex items-center gap-1.5">
            <span class="inline-block w-2.5 h-1 border-t-2 border-dashed border-[#ffd97d]/50"></span> Locked Exit
          </span>
        </div>

        <div class="text-[10px] text-slate-500 bg-slate-900/60 px-3 py-1.5 border border-white/5 rounded-lg backdrop-blur-sm uppercase tracking-wider">
          Drag to pan • Scroll to zoom • Hover room or exit for details
        </div>
      </div>

      <!-- Tooltip -->
      <Teleport to="body">
        <Transition name="tooltip">
          <div 
            v-if="hoveredNode" 
            class="fixed z-[100] pointer-events-none transition-all duration-75"
            :style="{ left: (tooltipPos.x + 20) + 'px', top: (tooltipPos.y - 40) + 'px' }"
          >
            <div class="w-72 bg-slate-900/95 border border-slate-700 rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] backdrop-blur-xl overflow-hidden flex flex-col animate-tooltip-in">
              <!-- Scene Image -->
              <div v-if="hoveredNode.imageUrl" class="h-40 w-full relative">
                <img :src="buildImageUrl(hoveredNode.imageUrl)" class="absolute inset-0 w-full h-full object-cover" />
                <div class="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent"></div>
              </div>

              <!-- Content -->
              <div class="p-5 bg-slate-900">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-sm font-bold text-white uppercase tracking-wider">{{ hoveredNode.label || hoveredNode.name || hoveredNode.id }}</span>
                  <span class="text-xxs px-1.5 py-0.5 rounded border border-emerald-500/30 text-emerald-400 font-mono uppercase">
                    Scene
                  </span>
                </div>
                <p class="text-xs text-slate-400 leading-relaxed italic line-clamp-4">
                  {{ (hoveredNode.description && hoveredNode.description.trim()) ? hoveredNode.description : 'No description provided.' }}
                </p>
              </div>
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
            </div>
          </div>
        </Transition>
      </Teleport>
    </div>
  </div>
</template>

<style scoped>
.bg-radial-gradient {
  background: radial-gradient(circle at center, #0f172a 0%, #020617 100%);
}

.tooltip-enter-active, .tooltip-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.tooltip-enter-from, .tooltip-leave-to { opacity: 0; transform: scale(0.96) translateY(4px); }

.animate-tooltip-in {
  animation: toolTipIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes toolTipIn {
  from { opacity: 0; transform: translateY(6px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

svg {
  filter: drop-shadow(0 0 8px rgba(0,0,0,0.5));
}
</style>
