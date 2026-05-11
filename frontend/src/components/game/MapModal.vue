<script setup lang="ts">
/**
 * MapModal — Renders the world map as an interactive, hand-drawn sketch using Rough.js.
 *
 * Props:
 *   open        — controls modal visibility
 *   mapData     — the raw graph data (nodes + edges)
 *   nodes       — metadata for tooltips (scene details)
 *
 * Emits: close
 */
import { watch, ref, nextTick, onMounted, onBeforeUnmount } from 'vue'
import rough from 'roughjs'
import dagre from 'dagre'
import mapSvg from '@/assets/svg/fantasy-rpg-map.svg'
import type { WorldMapData, MapNode } from '@/types'

const props = defineProps<{
  open: boolean
  mapData: WorldMapData | null
  nodes: Record<string, any>
  isDebug?: boolean
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const mapContainer = ref<HTMLDivElement | null>(null)
const renderError = ref<string | null>(null)

// Tooltip State
const hoveredNodeId = ref<string | null>(null)
const hoveredNode = ref<any | null>(null)
const tooltipPos = ref({ x: 0, y: 0 })

// Node positions for hit testing
const nodeBounds = ref<Record<string, { x: number, y: number, w: number, h: number }>>({})
// Edge midpoints for hit testing
const edgeMidpoints = ref<Array<{ from: string, to: string, x: number, y: number, label: string }>>([])
const hoveredEdge = ref<{ label: string, x: number, y: number } | null>(null)

// Zoom & Pan State
const zoom = ref(1)
const offset = ref({ x: 0, y: 0 })
const isPanning = ref(false)
const lastMousePos = ref({ x: 0, y: 0 })

function resetView() {
  zoom.value = 1
  offset.value = { x: 0, y: 0 }
}

/**
 * Normalizes an ID to match the backend safe_id logic.
 */
function safeId(raw: string): string {
  if (!raw) return ''
  // Python's isalnum() includes unicode letters/numbers.
  // We use \p{L} (any letter) and \p{N} (any number) with the 'u' flag.
  return raw.replace(/-/g, '_')
            .split('')
            .map(c => /[\p{L}\p{N}_]/u.test(c) ? c : '_')
            .join('')
            .toUpperCase()
}

/**
 * Uses Dagre to calculate a clean layout for the directed graph.
 */
function calculateLayout() {
  if (!props.mapData) return null

  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 60, edgesep: 20, ranksep: 120, ranker: 'network-simplex' })
  g.setDefaultEdgeLabel(() => ({}))

  // 1. Determine which nodes to show
  const visitedIdsList = Object.keys(props.mapData.nodes).sort()
  const firstId = visitedIdsList[0] 
  
  const visitedIds = new Set(visitedIdsList)
  const discoveredIds = new Set<string>()
  
  // Ensure current scene is always treated as visited/shown
  const currentId = props.mapData.current_scene_id
  if (currentId) visitedIds.add(currentId)

  // Find nodes that are connected to visited nodes (discovered nodes)
  props.mapData.edges.forEach(edge => {
    const fromId = safeId(edge.from)
    const toId = safeId(edge.to)
    if (visitedIds.has(fromId) || visitedIds.has(toId)) {
      if (visitedIds.has(fromId)) discoveredIds.add(toId)
      if (visitedIds.has(toId)) discoveredIds.add(fromId)
    }
  })

  // 2. Add nodes to graph
  // Show visited nodes (override template if needed)
  visitedIds.forEach(id => {
    const node = props.nodes[id] || props.mapData!.nodes[id]
    const isStart = id === firstId
    g.setNode(id, { 
      label: node?.label || id, 
      width: 160, 
      height: 70,
      rank: isStart ? 0 : undefined
    })
  })

  // Show discovered (but not visited) nodes
  discoveredIds.forEach(id => {
    if (!visitedIds.has(id)) {
      // Try to find label in props.nodes (template metadata)
      const metadata = props.nodes[id]
      g.setNode(id, { label: metadata?.label || id, width: 160, height: 70 })
    }
  })

  // 3. Add edges (Normalize IDs!)
  const processedEdges = new Set<string>()
  const mergedEdges: Array<{ from: string, to: string, isBidirectional: boolean, labels: string[] }> = []

  props.mapData.edges.forEach(edge => {
    const fromId = safeId(edge.from)
    const toId = safeId(edge.to)
    
    // Skip if nodes don't exist
    if (!g.hasNode(fromId) || !g.hasNode(toId)) return

    const forwardKey = `${fromId}->${toId}`
    const reverseKey = `${toId}->${fromId}`

    // Check if we already merged the reverse of this edge
    const existing = mergedEdges.find(me => me.from === toId && me.to === fromId)
    if (existing) {
      existing.isBidirectional = true
      if (edge.label && !existing.labels.includes(edge.label)) {
        existing.labels.push(edge.label)
      }
    } else {
      mergedEdges.push({
        from: fromId,
        to: toId,
        isBidirectional: false,
        labels: edge.label ? [edge.label] : []
      })
    }
  })

  // Add the merged edges to Dagre
  mergedEdges.forEach(me => {
    g.setEdge(me.from, me.to, { isBidirectional: me.isBidirectional, labels: me.labels })
  })

  dagre.layout(g)
  return g
}

/**
 * Renders the sketchy map using Rough.js on a Canvas.
 */
async function renderMap() {
  if (!props.open || !canvasRef.value || !props.mapData) return

  const canvas = canvasRef.value
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const g = calculateLayout()
  if (!g) return

  const rc = rough.canvas(canvas)
  
  // Reset hit testing data
  nodeBounds.value = {}
  edgeMidpoints.value = []

  // Determine canvas size based on graph size
  const graphInfo = g.graph()
  const margin = 100
  const width = (graphInfo.width || 800) + margin * 2
  const height = (graphInfo.height || 600) + margin * 2
  
  canvas.width = width
  canvas.height = height
  
  ctx.clearRect(0, 0, width, height)

  // Sketching settings
  const nodeOptions = {
    roughness: 1.5,
    stroke: '#8b6914',
    strokeWidth: 2,
    fill: '#3d1f00',
    fillStyle: 'hachure' as const,
    fillWeight: 1.5,
    hachureAngle: 60,
    hachureGap: 4
  }

  const unvisitedNodeOptions = {
    ...nodeOptions,
    stroke: '#5c4b2a',
    fill: 'transparent',
    strokeDasharray: [5, 5],
    roughness: 1.0,
    fillStyle: 'none' as const
  }

  const discoveredNodeOptions = {
    ...unvisitedNodeOptions,
    stroke: '#8b7a5e',
    fill: 'transparent',
    fillStyle: 'none' as const
  }

  const currentNodeOptions = {
    ...nodeOptions,
    stroke: '#c9a84c',
    strokeWidth: 3,
    fill: '#1a5c2a',
    roughness: 2,
    fillWeight: 3
  }

  const edgeOptions = {
    roughness: 0.3,
    stroke: '#ffd97d',
    strokeWidth: 1.5
  }

  const lockedEdgeOptions = {
    ...edgeOptions,
    strokeDasharray: [5, 5],
    opacity: 0.5
  }

  // 1. Draw Edges
  g.edges().forEach(e => {
    const edge = g.edge(e)
    const points = edge.points
    if (points && points.length > 1) {
      const flatPoints: [number, number][] = points.map(p => [p.x + margin, p.y + margin])
      
      const rawEdge = props.mapData!.edges.find(re => safeId(re.from) === e.v && safeId(re.to) === e.w)
      const options = rawEdge?.is_locked ? lockedEdgeOptions : edgeOptions
      const isBidirectional = edge.isBidirectional
      
      const simplified = flatPoints.length > 4 
        ? [flatPoints[0], flatPoints[Math.floor(flatPoints.length/2)], flatPoints[flatPoints.length-1]]
        : flatPoints
      rc.curve(simplified, options)

      // Arrow head at THE END (Always)
      if (flatPoints.length >= 2) {
        drawArrowHead(rc, flatPoints[flatPoints.length - 2], flatPoints[flatPoints.length - 1], options)
      }

      // Arrow head at THE START (If bidirectional)
      if (isBidirectional && flatPoints.length >= 2) {
        drawArrowHead(rc, flatPoints[1], flatPoints[0], options)
      }

      // Store midpoint for hover detection
      const label = edge.labels?.join(' / ') || rawEdge?.label
      if (label) {
        const midIdx = Math.floor(points.length / 2)
        const midPoint = points[midIdx]
        edgeMidpoints.value.push({
          from: e.v,
          to: e.w,
          x: midPoint.x + margin,
          y: midPoint.y + margin,
          label: label
        })
      }
    }
  })

  // 2. Draw Nodes
  g.nodes().forEach(id => {
    const node = g.node(id)
    const isCurrent = id === props.mapData?.current_scene_id
    const x = node.x - node.width / 2 + margin
    const y = node.y - node.height / 2 + margin
    const w = node.width
    const h = node.height

    nodeBounds.value[id] = { x, y, w, h }

    const nodeData = props.mapData?.nodes[id]
    const isVisited = !!nodeData
    const options = isCurrent ? currentNodeOptions : (isVisited ? nodeOptions : discoveredNodeOptions)
    
    rc.rectangle(x, y, w, h, options)

    // Text Label
    ctx.font = isCurrent ? 'bold 15px Acme, sans-serif' : '14px Acme, sans-serif'
    ctx.fillStyle = isVisited ? '#f5e6c8' : '#8b7a5e'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    const label = isCurrent ? `${node.label} 📍` : node.label
    
    const words = label.split(' ')
    if (words.length > 3 && label.length > 20) {
      const mid = Math.floor(words.length / 2)
      const line1 = words.slice(0, mid).join(' ')
      const line2 = words.slice(mid).join(' ')
      ctx.fillText(line1, node.x + margin, node.y + margin - 10)
      ctx.fillText(line2, node.x + margin, node.y + margin + 10)
    } else {
      ctx.fillText(label, node.x + margin, node.y + margin)
    }
  })
}

/**
 * Helper to draw a sketchy arrow head pointing from p1 to p2.
 */
function drawArrowHead(rc: any, p1: [number, number], p2: [number, number], options: any) {
  const angle = Math.atan2(p2[1] - p1[1], p2[0] - p1[0])
  const headLen = 12
  const h1x = p2[0] - headLen * Math.cos(angle - Math.PI / 6)
  const h1y = p2[1] - headLen * Math.sin(angle - Math.PI / 6)
  const h2x = p2[0] - headLen * Math.cos(angle + Math.PI / 6)
  const h2y = p2[1] - headLen * Math.sin(angle + Math.PI / 6)
  
  rc.polygon([[p2[0], p2[1]], [h1x, h1y], [h2x, h2y]], {
    ...options,
    fill: options.stroke,
    fillStyle: 'solid',
    roughness: 0.2
  })
}

/**
 * Hit testing for interactivity.
 */
function handleMouseMove(e: MouseEvent) {
  if (!canvasRef.value) return
  
  // Update Panning
  if (isPanning.value) {
    offset.value.x += e.clientX - lastMousePos.value.x
    offset.value.y += e.clientY - lastMousePos.value.y
    lastMousePos.value = { x: e.clientX, y: e.clientY }
    return
  }
  lastMousePos.value = { x: e.clientX, y: e.clientY }

  const rect = canvasRef.value.getBoundingClientRect()
  
  // Map screen coordinates to untransformed canvas coordinates
  // We need to account for CSS scale (zoom) and translation (offset)
  const x = (e.clientX - rect.left) / zoom.value
  const y = (e.clientY - rect.top) / zoom.value

  let foundNodeId: string | null = null
  for (const [id, bounds] of Object.entries(nodeBounds.value)) {
    if (x >= bounds.x && x <= bounds.x + bounds.w && y >= bounds.y && y <= bounds.y + bounds.h) {
      foundNodeId = id
      break
    }
  }


  // Also check for edges if no node is found
  let foundEdge = null
  if (!foundNodeId) {
    for (const em of edgeMidpoints.value) {
      const dist = Math.sqrt(Math.pow(x - em.x, 2) + Math.pow(y - em.y, 2))
      if (dist < 30) { // Distance threshold for edges
        foundEdge = { label: em.label, x: e.clientX, y: e.clientY }
        break
      }
    }
  }
  hoveredEdge.value = foundEdge

  if (foundNodeId !== hoveredNodeId.value) {
    hoveredNodeId.value = foundNodeId
    if (foundNodeId) {
      const nodeData = props.mapData?.nodes[foundNodeId]
      const originalId = nodeData?.id || foundNodeId
      hoveredNode.value = props.nodes[originalId] || nodeData
      tooltipPos.value = { x: e.clientX, y: e.clientY }
    } else {
      hoveredNode.value = null
    }
  } else if (foundNodeId) {
    tooltipPos.value = { x: e.clientX, y: e.clientY }
  }
}

function handleMouseDown(e: MouseEvent) {
  if (e.button === 0) { // Left click for pan
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
  const newZoom = Math.max(0.2, Math.min(3, zoom.value * delta))
  
  // Simple zoom towards mouse could be added here, 
  // but center zoom is easier for now.
  zoom.value = newZoom
}

watch(() => [props.open, props.mapData], async () => {
  if (props.open) {
    await nextTick()
    renderMap()
  }
})

onMounted(() => {
  if (props.open) {
    renderMap()
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
                <p class="text-xs text-slate-400 mt-0.5">Sketch of your journey</p>
              </div>
            </div>
            <div class="flex items-center gap-4">
              <!-- Legend -->
              <div class="hidden sm:flex items-center gap-4 text-xxs text-slate-400">
                <span class="flex items-center gap-1.5">
                  <span class="inline-block w-3 h-3 rounded bg-emerald-700 border border-emerald-500"></span> Current Location
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="inline-block w-3 h-3 rounded bg-[#3d1f00] border border-[#8b6914]"></span> Visited
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

            <!-- Rough output -->
            <div
              v-else
              class="w-full h-full flex items-center justify-center relative z-10"
              @wheel="handleWheel"
              @mousedown="handleMouseDown"
              @mousemove="handleMouseMove"
              @mouseup="handleMouseUp"
              @mouseleave="handleMouseUp"
            >
              <canvas 
                ref="canvasRef" 
                class="max-w-none cursor-grab active:cursor-grabbing will-change-transform"
                :style="{ 
                  transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
                  transformOrigin: 'center center'
                }"
              />
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
                    <!-- Image Area -->
                    <div v-if="hoveredNode.image_url" class="h-40 w-full relative">
                      <img :src="hoveredNode.image_url" class="absolute inset-0 w-full h-full object-cover" />
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
                  </div>
                </div>
              </Transition>
            </Teleport>

            <!-- EDGE HOVER LABEL -->
            <Teleport to="body">
              <Transition name="fade">
                <div 
                  v-if="hoveredEdge" 
                  class="fixed z-[110] pointer-events-none px-3 py-1.5 bg-slate-900/90 border border-amber-500/50 rounded-lg shadow-xl backdrop-blur-sm animate-tooltip-in"
                  :style="{ left: (hoveredEdge.x + 15) + 'px', top: (hoveredEdge.y - 30) + 'px' }"
                >
                  <div class="flex items-center gap-2">
                    <i class="ra ra-trail text-amber-400 text-xs"></i>
                    <span class="text-xs font-bold text-amber-200 uppercase tracking-tight">{{ hoveredEdge.label }}</span>
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
            <span>Tip: hover over rooms for details • sketched in real-time</span>
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

/* Tooltip Animations */
.tooltip-enter-active, .tooltip-leave-active { transition: opacity 0.2s, transform 0.2s; }
.tooltip-enter-from, .tooltip-leave-to { opacity: 0; transform: scale(0.95) translateY(5px); }

.animate-tooltip-in {
  animation: toolTipIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes toolTipIn {
  from { opacity: 0; transform: translateY(10px) scale(0.9); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
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
    transform: scale(0.96) translateY(8px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

canvas {
  filter: drop-shadow(0 0 10px rgba(0,0,0,0.5));
}
</style>
