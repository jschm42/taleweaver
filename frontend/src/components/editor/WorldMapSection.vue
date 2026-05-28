<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import dagre from 'dagre'
import rough from 'roughjs'
import mapSvg from '@/assets/svg/fantasy-rpg-map.svg'

interface SceneNode {
  id: string
  label: string
  description?: string
  image_url?: string | null
}

interface ExitEdge {
  from: string
  to: string
  label?: string
  is_locked?: boolean
}

const props = defineProps<{
  debugData: any
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const mapContainerRef = ref<HTMLDivElement | null>(null)
const zoom = ref(1)
const offset = ref({ x: 0, y: 0 })
const isPanning = ref(false)
const lastMousePos = ref({ x: 0, y: 0 })

const scenes = computed<SceneNode[]>(() => {
  const raw = Array.isArray(props.debugData?.scenes) ? props.debugData.scenes : []
  return raw
    .filter((scene: any) => !!scene?.id)
    .map((scene: any) => ({
      id: String(scene.id),
      label: String(scene.label || scene.name || scene.id),
      description: typeof scene.description === 'string' ? scene.description : '',
      image_url: scene.image_url || null,
    }))
})

const exits = computed<ExitEdge[]>(() => {
  const raw = Array.isArray(props.debugData?.exits) ? props.debugData.exits : []
  return raw
    .map((edge: any) => {
      const from = String(edge.from_scene_id || edge.from || '').trim()
      const to = String(edge.to_scene_id || edge.to || '').trim()
      if (!from || !to) return null
      return {
        from,
        to,
        label: typeof edge.label === 'string' ? edge.label : undefined,
        is_locked: edge.is_locked === true,
      }
    })
    .filter((edge: ExitEdge | null): edge is ExitEdge => edge !== null)
})

const currentSceneId = computed<string | null>(() => {
  const adventure = props.debugData?.adventure || {}
  const candidate =
    adventure.current_scene_id ||
    adventure.scene_id ||
    adventure.start_scene_id ||
    null
  return candidate ? String(candidate) : null
})

const hasMapData = computed(() => scenes.value.length > 0)

function safeId(raw: string): string {
  if (!raw) return ''
  return raw
    .replace(/-/g, '_')
    .split('')
    .map((char) => /[\p{L}\p{N}_]/u.test(char) ? char : '_')
    .join('')
    .toUpperCase()
}

function resetView() {
  zoom.value = 1
  offset.value = { x: 0, y: 0 }
}

function calculateLayout() {
  if (!hasMapData.value) return null

  const graph = new dagre.graphlib.Graph()
  graph.setGraph({ rankdir: 'LR', nodesep: 60, edgesep: 20, ranksep: 110, ranker: 'network-simplex' })
  graph.setDefaultEdgeLabel(() => ({}))

  const idMap = new Map<string, string>()
  for (const scene of scenes.value) {
    const normalized = safeId(scene.id)
    idMap.set(scene.id, normalized)
    graph.setNode(normalized, {
      id: scene.id,
      label: scene.label,
      width: 170,
      height: 76,
    })
  }

  for (const edge of exits.value) {
    const fromId = idMap.get(edge.from) || safeId(edge.from)
    const toId = idMap.get(edge.to) || safeId(edge.to)
    if (!graph.hasNode(fromId) || !graph.hasNode(toId)) continue
    graph.setEdge(fromId, toId, {
      label: edge.label,
      is_locked: edge.is_locked,
    })
  }

  dagre.layout(graph)
  return graph
}

function drawArrowHead(
  rc: rough.RoughCanvas,
  p1: [number, number],
  p2: [number, number],
  options: rough.Options,
) {
  const angle = Math.atan2(p2[1] - p1[1], p2[0] - p1[0])
  const headLen = 12
  const h1x = p2[0] - headLen * Math.cos(angle - Math.PI / 6)
  const h1y = p2[1] - headLen * Math.sin(angle - Math.PI / 6)
  const h2x = p2[0] - headLen * Math.cos(angle + Math.PI / 6)
  const h2y = p2[1] - headLen * Math.sin(angle + Math.PI / 6)

  rc.polygon(
    [[p2[0], p2[1]], [h1x, h1y], [h2x, h2y]],
    {
      ...options,
      fill: options.stroke,
      fillStyle: 'solid',
      roughness: 0.3,
    },
  )
}

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

function renderMap() {
  if (!canvasRef.value || !hasMapData.value) return

  const graph = calculateLayout()
  if (!graph) return

  const canvas = canvasRef.value
  const context = canvas.getContext('2d')
  if (!context) return

  const roughCanvas = rough.canvas(canvas)

  const graphInfo = graph.graph()
  const margin = 110
  const width = (graphInfo.width || 1000) + margin * 2
  const height = (graphInfo.height || 700) + margin * 2

  canvas.width = width
  canvas.height = height
  context.clearRect(0, 0, width, height)

  const edgeOptions: rough.Options = {
    roughness: 0.35,
    stroke: '#ffd97d',
    strokeWidth: 1.6,
  }

  const lockedEdgeOptions: rough.Options = {
    ...edgeOptions,
    strokeDasharray: [5, 5],
    opacity: 0.55,
  }

  for (const edgeRef of graph.edges()) {
    const edge = graph.edge(edgeRef)
    const points = edge.points
    if (!points || points.length < 2) continue

    const polyline: [number, number][] = points.map((point: any) => [point.x + margin, point.y + margin])
    const isLocked = !!edge.is_locked
    const options = isLocked ? lockedEdgeOptions : edgeOptions
    const simplified = polyline.length > 4
      ? [polyline[0], polyline[Math.floor(polyline.length / 2)], polyline[polyline.length - 1]]
      : polyline

    roughCanvas.curve(simplified, options)
    drawArrowHead(roughCanvas, polyline[polyline.length - 2], polyline[polyline.length - 1], options)

    if (isLocked) {
      const midIdx = Math.floor(points.length / 2)
      const midPoint = points[midIdx]
      drawLockIcon(context, midPoint.x + margin, midPoint.y + margin)
    }
  }

  const currentId = currentSceneId.value ? safeId(currentSceneId.value) : null

  for (const nodeId of graph.nodes()) {
    const node = graph.node(nodeId)
    const x = node.x - node.width / 2 + margin
    const y = node.y - node.height / 2 + margin
    const isCurrent = currentId === nodeId

    const nodeOptions: rough.Options = isCurrent
      ? {
          roughness: 1.8,
          stroke: '#c9a84c',
          strokeWidth: 3,
          fill: '#1a5c2a',
          fillStyle: 'hachure',
          fillWeight: 2.5,
          hachureGap: 4,
        }
      : {
          roughness: 1.3,
          stroke: '#8b6914',
          strokeWidth: 2,
          fill: '#3d1f00',
          fillStyle: 'hachure',
          fillWeight: 1.3,
          hachureGap: 4,
        }

    roughCanvas.rectangle(x, y, node.width, node.height, nodeOptions)

    context.font = isCurrent ? 'bold 15px Acme, sans-serif' : '14px Acme, sans-serif'
    context.fillStyle = isCurrent ? '#fdf4d5' : '#f5e6c8'
    context.textAlign = 'center'
    context.textBaseline = 'middle'

    const label = isCurrent ? `${node.label} (Current)` : node.label
    context.fillText(label, node.x + margin, node.y + margin)
  }
}

function handleWheel(event: WheelEvent) {
  event.preventDefault()
  const delta = event.deltaY > 0 ? 0.9 : 1.1
  zoom.value = Math.max(0.2, Math.min(3, zoom.value * delta))
}

function handleMouseDown(event: MouseEvent) {
  if (event.button !== 0) return
  isPanning.value = true
  lastMousePos.value = { x: event.clientX, y: event.clientY }
}

function handleMouseMove(event: MouseEvent) {
  if (!isPanning.value) return
  offset.value.x += event.clientX - lastMousePos.value.x
  offset.value.y += event.clientY - lastMousePos.value.y
  lastMousePos.value = { x: event.clientX, y: event.clientY }
}

function handleMouseUp() {
  isPanning.value = false
}

watch(() => [scenes.value, exits.value, currentSceneId.value], async () => {
  await nextTick()
  renderMap()
}, { deep: true })

onMounted(async () => {
  await nextTick()
  renderMap()
})
</script>

<template>
  <section class="space-y-4 bg-slate-900/40 p-8 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">World Map</h3>
        <p class="text-xs text-slate-400 mt-2">Complete map of all scenes and transitions in this adventure.</p>
      </div>
      <div class="flex items-center bg-slate-800/50 rounded-full px-1.5 py-1 border border-slate-700/50 gap-1">
        <button
          @click="zoom = Math.max(0.2, zoom - 0.1)"
          class="p-1.5 rounded-full text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
          title="Zoom Out"
        >
          -
        </button>
        <span class="text-xxs font-mono text-slate-500 min-w-[3rem] text-center">{{ Math.round(zoom * 100) }}%</span>
        <button
          @click="zoom = Math.min(3, zoom + 0.1)"
          class="p-1.5 rounded-full text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
          title="Zoom In"
        >
          +
        </button>
        <div class="w-px h-4 bg-slate-700 mx-1"></div>
        <button
          @click="resetView"
          class="p-1.5 rounded-full text-slate-400 hover:text-emerald-400 hover:bg-slate-700 transition-colors"
          title="Reset View"
        >
          Reset
        </button>
      </div>
    </div>

    <div
      ref="mapContainerRef"
      class="relative h-[34rem] rounded-3xl border border-slate-800 overflow-auto bg-slate-950 bg-radial-gradient"
      @wheel="handleWheel"
      @mousedown="handleMouseDown"
      @mousemove="handleMouseMove"
      @mouseup="handleMouseUp"
      @mouseleave="handleMouseUp"
    >
      <div
        v-if="!hasMapData"
        class="absolute inset-0 flex flex-col items-center justify-center text-slate-600"
      >
        <i class="ra ra-compass text-6xl mb-4 opacity-50"></i>
        <p class="text-lg font-medium">No map data yet</p>
        <p class="text-sm mt-1">Create scenes and exits to render the full world map.</p>
      </div>

      <div v-else class="w-full h-full flex items-center justify-center relative z-10">
        <canvas
          ref="canvasRef"
          class="max-w-none cursor-grab active:cursor-grabbing will-change-transform"
          :style="{
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
            transformOrigin: 'center center'
          }"
        />
      </div>

      <div
        class="absolute inset-0 pointer-events-none opacity-[0.06] z-0"
        :style="{
          backgroundImage: `url(${mapSvg})`,
          backgroundSize: '85% auto',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat'
        }"
      ></div>

      <div class="absolute inset-0 bg-gradient-to-tr from-emerald-500/5 via-transparent to-amber-500/5 pointer-events-none z-0"></div>
    </div>

    <div class="text-xs text-slate-600 flex justify-between items-center">
      <div class="flex gap-4">
        <span><i class="ra ra-plain-dagger mr-1"></i> Drag to pan</span>
        <span><i class="ra ra-scroll-unfurled mr-1"></i> Scroll to zoom</span>
      </div>
      <span>Shows complete scene graph from editor data</span>
    </div>
  </section>
</template>

<style scoped>
.bg-radial-gradient {
  background: radial-gradient(circle at center, #0f172a 0%, #020617 100%);
}

canvas {
  filter: drop-shadow(0 0 10px rgba(0, 0, 0, 0.5));
}
</style>
