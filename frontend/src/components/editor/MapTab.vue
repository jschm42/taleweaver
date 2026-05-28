<script setup lang="ts">
/**
 * MapTab — Renders the adventure template scenes as an interactive world map.
 * Reuses Dagre for graph layouts and Rough.js for a hand-drawn sketch aesthetic.
 */
import { watch, ref, nextTick, onMounted, computed } from 'vue'
import rough from 'roughjs'
import dagre from 'dagre'
import mapSvg from '@/assets/svg/fantasy-rpg-map.svg'
import { visualService } from '@/services/visualService'

const props = defineProps<{
  debugData: any
  editorScenes: any[]
  visualsCacheVersion?: number
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const mapContainer = ref<HTMLDivElement | null>(null)

// Tooltip State
const hoveredNodeId = ref<string | null>(null)
const hoveredNode = ref<any | null>(null)
const tooltipPos = ref({ x: 0, y: 0 })

// Node positions for hit testing
const nodeBounds = ref<Record<string, { x: number, y: number, w: number, h: number }>>({})
// Edge midpoints for hit testing
const edgeMidpoints = ref<Array<{ from: string, to: string, x: number, y: number, label: string }>>([])
const hoveredEdge = ref<{ label: string, x: number, y: number } | null>(null)

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

function resetView() {
  zoom.value = 1
  offset.value = { x: 0, y: 0 }
}

/**
 * Normalizes an ID to match the backend safe_id logic.
 */
function safeId(raw: string): string {
  if (!raw) return ''
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
  if (!props.editorScenes || props.editorScenes.length === 0) return null

  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 60, edgesep: 20, ranksep: 120, ranker: 'network-simplex' })
  g.setDefaultEdgeLabel(() => ({}))

  // 1. Add all scenes as nodes
  props.editorScenes.forEach(scene => {
    const id = safeId(scene.id)
    g.setNode(id, { 
      label: scene.label || scene.name || scene.id, 
      width: 160, 
      height: 70 
    })
  })

  // 2. Add edges (exits)
  const exits = props.debugData?.exits || []
  const mergedEdges: Array<{ from: string, to: string, isBidirectional: boolean, labels: string[], is_locked: boolean }> = []

  exits.forEach((edge: any) => {
    const fromId = safeId(edge.from_scene_id)
    const toId = safeId(edge.to_scene_id)
    
    // Skip if nodes don't exist in the current template
    if (!g.hasNode(fromId) || !g.hasNode(toId)) return

    const existing = mergedEdges.find(me => me.from === toId && me.to === fromId)
    if (existing) {
      existing.isBidirectional = true
      if (edge.label && !existing.labels.includes(edge.label)) {
        existing.labels.push(edge.label)
      }
      if (edge.is_locked) {
        existing.is_locked = true
      }
    } else {
      mergedEdges.push({
        from: fromId,
        to: toId,
        isBidirectional: false,
        labels: edge.label ? [edge.label] : [],
        is_locked: !!edge.is_locked
      })
    }
  })

  mergedEdges.forEach(me => {
    g.setEdge(me.from, me.to, { isBidirectional: me.isBidirectional, labels: me.labels, is_locked: me.is_locked })
  })

  dagre.layout(g)
  return g
}

/**
 * Renders the sketchy map using Rough.js on a Canvas.
 */
async function renderMap() {
  if (!canvasRef.value || !props.editorScenes.length) return

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

  const startNodeOptions = {
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

  const exits = props.debugData?.exits || []

  // 1. Draw Edges
  g.edges().forEach(e => {
    const edge = g.edge(e)
    const points = edge.points
    if (points && points.length > 1) {
      const flatPoints: [number, number][] = points.map(p => [p.x + margin, p.y + margin])
      
      const isLocked = !!edge.is_locked
      const options = isLocked ? lockedEdgeOptions : edgeOptions
      const isBidirectional = edge.isBidirectional
      
      const simplified = flatPoints.length > 4 
        ? [flatPoints[0], flatPoints[Math.floor(flatPoints.length/2)], flatPoints[flatPoints.length-1]]
        : flatPoints
      rc.curve(simplified, options)

      // Arrow head at THE END
      if (flatPoints.length >= 2) {
        drawArrowHead(rc, flatPoints[flatPoints.length - 2], flatPoints[flatPoints.length - 1], options)
      }

      // Arrow head at THE START (If bidirectional)
      if (isBidirectional && flatPoints.length >= 2) {
        drawArrowHead(rc, flatPoints[1], flatPoints[0], options)
      }

      // Store midpoint for hover detection
      const label = edge.labels?.join(' / ')
      const midIdx = Math.floor(points.length / 2)
      const midPoint = points[midIdx]
      const midX = midPoint.x + margin
      const midY = midPoint.y + margin

      if (label) {
        edgeMidpoints.value.push({
          from: e.v,
          to: e.w,
          x: midX,
          y: midY,
          label: label
        })
      }

      if (isLocked) {
        drawLockIcon(ctx, midX, midY)
      }
    }
  })

  // 2. Draw Nodes
  g.nodes().forEach(id => {
    const node = g.node(id)
    const isStart = startSceneId.value === id
    const x = node.x - node.width / 2 + margin
    const y = node.y - node.height / 2 + margin
    const w = node.width
    const h = node.height

    nodeBounds.value[id] = { x, y, w, h }

    const options = isStart ? startNodeOptions : nodeOptions
    rc.rectangle(x, y, w, h, options)

    // Text Label
    ctx.font = isStart ? 'bold 15px Acme, sans-serif' : '14px Acme, sans-serif'
    ctx.fillStyle = '#f5e6c8'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    
    const label = isStart ? `${node.label} 🚩` : node.label
    
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
 * Helper to draw a small RPG-style lock icon at the midpoint of a locked edge.
 */
function drawLockIcon(ctx: CanvasRenderingContext2D, x: number, y: number) {
  ctx.save()
  
  // Draw Shackle (arch)
  ctx.beginPath()
  ctx.arc(x, y - 2, 4, Math.PI, 0, false)
  ctx.lineWidth = 2
  ctx.strokeStyle = '#ffd97d' // Amber/yellow matching path stroke
  ctx.stroke()
  
  // Draw Body (rounded rectangle)
  ctx.fillStyle = '#b45309' // Darker amber/brown for body
  ctx.strokeStyle = '#ffd97d'
  ctx.lineWidth = 1.5
  
  const bodyW = 12
  const bodyH = 8
  const bodyX = x - bodyW / 2
  const bodyY = y - 2
  
  ctx.beginPath()
  ctx.rect(bodyX, bodyY, bodyW, bodyH)
  ctx.fill()
  ctx.stroke()
  
  // Draw keyhole
  ctx.beginPath()
  ctx.arc(x, bodyY + 3, 1.2, 0, Math.PI * 2)
  ctx.fillStyle = '#020617' // dark background slate
  ctx.fill()
  
  ctx.beginPath()
  ctx.moveTo(x, bodyY + 4)
  ctx.lineTo(x, bodyY + 6)
  ctx.strokeStyle = '#020617'
  ctx.lineWidth = 1
  ctx.stroke()
  
  ctx.restore()
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
  
  const x = (e.clientX - rect.left) / zoom.value
  const y = (e.clientY - rect.top) / zoom.value

  let foundNodeId: string | null = null
  for (const [id, bounds] of Object.entries(nodeBounds.value)) {
    if (x >= bounds.x && x <= bounds.x + bounds.w && y >= bounds.y && y <= bounds.y + bounds.h) {
      foundNodeId = id
      break
    }
  }

  // Check for edges if no node is found
  let foundEdge = null
  if (!foundNodeId) {
    for (const em of edgeMidpoints.value) {
      const dist = Math.sqrt(Math.pow(x - em.x, 2) + Math.pow(y - em.y, 2))
      if (dist < 30) {
        foundEdge = { label: em.label, x: e.clientX, y: e.clientY }
        break
      }
    }
  }
  hoveredEdge.value = foundEdge

  if (foundNodeId !== hoveredNodeId.value) {
    hoveredNodeId.value = foundNodeId
    if (foundNodeId) {
      const originalScene = props.editorScenes.find(s => safeId(s.id) === foundNodeId)
      if (originalScene) {
        hoveredNode.value = originalScene
      }
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
  zoom.value = newZoom
}

function buildImageUrl(path?: string | null) {
  return visualService.buildImageUrl(path, props.visualsCacheVersion || 0)
}

watch(() => [props.editorScenes, props.debugData], async () => {
  await nextTick()
  renderMap()
}, { deep: true })

onMounted(async () => {
  await nextTick()
  renderMap()
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

      <!-- Map Render canvas -->
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
            <span class="inline-block w-2.5 h-2.5 rounded bg-emerald-800 border border-emerald-500"></span> Start Scene
          </span>
          <span class="flex items-center gap-1.5">
            <span class="inline-block w-2.5 h-2.5 rounded bg-[#3d1f00] border border-[#8b6914]"></span> Regular Scene
          </span>
          <span class="flex items-center gap-1.5">
            <span class="inline-block w-2.5 h-1 border-t-2 border-dashed border-[#ffd97d]/50"></span> Locked Exit
          </span>
        </div>

        <div class="text-[10px] text-slate-500 bg-slate-900/60 px-3 py-1.5 border border-white/5 rounded-lg backdrop-blur-sm uppercase tracking-wider">
          Drag to pan • Scroll to zoom • Hover for info
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
              <div v-if="hoveredNode.image_url" class="h-40 w-full relative">
                <img :src="buildImageUrl(hoveredNode.image_url)" class="absolute inset-0 w-full h-full object-cover" />
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

      <!-- Edge Hover Label -->
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
  </div>
</template>

<style scoped>
.bg-radial-gradient {
  background: radial-gradient(circle at center, #0f172a 0%, #020617 100%);
}

.tooltip-enter-active, .tooltip-leave-active { transition: opacity 0.2s, transform 0.2s; }
.tooltip-enter-from, .tooltip-leave-to { opacity: 0; transform: scale(0.95) translateY(5px); }

.animate-tooltip-in {
  animation: toolTipIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes toolTipIn {
  from { opacity: 0; transform: translateY(10px) scale(0.9); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

canvas {
  filter: drop-shadow(0 0 10px rgba(0,0,0,0.5));
}
</style>
