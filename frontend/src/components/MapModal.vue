<script setup lang="ts">
/**
 * MapModal — Renders the world map as an interactive Mermaid.js flowchart.
 *
 * Props:
 *   open        — controls modal visibility
 *   mermaidSrc  — the Mermaid diagram string received from the server
 *
 * Emits: close
 */
import { watch, ref, nextTick, onMounted } from 'vue'
import mermaid from 'mermaid'

const props = defineProps<{
  open: boolean
  mermaidSrc: string
  nodes: Record<string, any>
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const mapContainer = ref<HTMLDivElement | null>(null)
const renderError = ref<string | null>(null)

// Tooltip State
const hoveredNode = ref<any | null>(null)
const tooltipPos = ref({ x: 0, y: 0 })

mermaid.initialize({
  startOnLoad: false,
  theme: 'base', // Use base to fully control with themeVariables
  themeVariables: {
    fontFamily: 'Acme, sans-serif',
    primaryColor: '#3d1f00', // ink-light
    primaryTextColor: '#f5e6c8', // parchment
    primaryBorderColor: '#8b6914', // panel-border-gold
    lineColor: '#c9a84c', // gold
    secondaryColor: '#1a0a00',
    tertiaryColor: '#1a0a00',
    mainBkg: '#1a0a00',
    nodeBorder: '#8b6914',
    clusterBkg: '#0d0d0d',
    titleColor: '#c9a84c',
    edgeLabelBackground: '#0d0d0d',
  },
  themeCSS: `
    .node rect, .node circle, .node polygon {
      stroke-width: 2px !important;
      filter: drop-shadow(0px 4px 6px rgba(0,0,0,0.6));
      pointer-events: all;
    }
    .edgePath .path {
      stroke-width: 2px !important;
      stroke: #c9a84c !important;
    }
    .marker {
      fill: #c9a84c !important;
      stroke: #c9a84c !important;
    }
    .label {
      color: #f5e6c8 !important;
      font-weight: 500;
      font-size: 14px;
      pointer-events: none;
    }
    .visited rect {
      fill: #3d1f00 !important;
      stroke: #8b6914 !important;
      stroke-width: 2px !important;
    }
    .current rect {
      fill: #1a5c2a !important;
      stroke: #c9a84c !important;
      stroke-width: 3px !important;
      animation: pulse-current 2s infinite;
    }
    .node:hover rect {
      stroke: #f0d080 !important;
      cursor: help;
    }
    .unvisited rect {
      fill: #0d0d0d !important;
      stroke: #3a2a1a !important;
      opacity: 0.5;
    }
    @keyframes pulse-current {
      0% { filter: drop-shadow(0 0 2px #27ae60); }
      50% { filter: drop-shadow(0 0 10px #27ae60); }
      100% { filter: drop-shadow(0 0 2px #27ae60); }
    }
  `,
})

/** 
 * Matches the Mermaid-mangled node ID back to our original scene_id.
 * Mermaid flowchart IDs are often formatted as 'flowchart-[scene_id]-[index]'
 */
function extractSceneId(mermaidId: string): string | null {
  // Mermaid IDs are typically: [diagram-id]-flowchart-[sceneId]-[index]
  // We use a regex to capture everything between 'flowchart-' and the final '-index'
  const match = mermaidId.match(/flowchart-(.+)-\d+$/)
  return match ? match[1] : null
}

/** Attaches hover events to the generated SVG nodes. */
function addMapInteractivity(): void {
  const nodes = mapContainer.value?.querySelectorAll('.node')
  if (!nodes) return

  console.log(`[MapMap] Synchronizing nodes...`)

  nodes.forEach((nodeEl) => {
    const mermaidId = nodeEl.id
    const sceneId = extractSceneId(mermaidId)

    nodeEl.addEventListener('mouseenter', (e: any) => {
      if (sceneId && props.nodes[sceneId]) {
        hoveredNode.value = props.nodes[sceneId]
        tooltipPos.value = { x: e.clientX, y: e.clientY }
      }
    })

    nodeEl.addEventListener('mousemove', (e: any) => {
      tooltipPos.value = { x: e.clientX, y: e.clientY }
    })

    nodeEl.addEventListener('mouseleave', () => {
      hoveredNode.value = null
    })
  })
}

/** Re-renders the Mermaid diagram whenever the source changes or modal opens. */
async function renderMermaid(): Promise<void> {
  if (!props.open || !mapContainer.value || !props.mermaidSrc) return

  renderError.value = null
  // We don't clear innerHTML immediately to avoid flicker during re-renders
  
  try {
    const id = `mermaid-map-${Date.now()}`
    const { svg } = await mermaid.render(id, props.mermaidSrc)
    mapContainer.value.innerHTML = svg

    // Make the SVG responsive
    const svgEl = mapContainer.value.querySelector('svg')
    if (svgEl) {
      svgEl.removeAttribute('width')
      svgEl.removeAttribute('height')
      svgEl.style.width = '100%'
      svgEl.style.height = '100%'
      
      // Inject interactivity after SVG is in DOM
      addMapInteractivity()
    }
  } catch (err) {
    renderError.value = 'Failed to render map. The data may be incomplete.'
    console.error('[MapModal] Mermaid render error:', err)
  }
}

watch(() => [props.open, props.mermaidSrc], async () => {
  await nextTick()
  await renderMermaid()
})

onMounted(async () => {
  if (props.open) {
    await nextTick()
    await renderMermaid()
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
                <p class="text-xs text-slate-400 mt-0.5">Auto-updated as you explore</p>
              </div>
            </div>
            <div class="flex items-center gap-4">
              <!-- Legend -->
              <div class="hidden sm:flex items-center gap-4 text-xs text-slate-400">
                <span class="flex items-center gap-1.5">
                  <span class="inline-block w-3 h-3 rounded bg-emerald-500"></span> Current Location
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="inline-block w-3 h-3 rounded bg-slate-700 border border-slate-600"></span> Visited
                </span>
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
          <div class="flex-grow overflow-auto p-6 relative bg-slate-950 bg-grid-pattern">
            <!-- Empty state -->
            <div
              v-if="!mermaidSrc"
              class="absolute inset-0 flex flex-col items-center justify-center text-slate-600"
            >
              <i class="ra ra-compass text-6xl mb-4 opacity-50"></i>
              <p class="text-lg font-medium">No map data yet</p>
              <p class="text-sm mt-1">Start your adventure to reveal the world.</p>
            </div>

            <!-- Render error -->
            <div
              v-else-if="renderError"
              class="absolute inset-0 flex flex-col items-center justify-center text-red-400"
            >
              <i class="ra ra-skull text-5xl mb-4 opacity-60"></i>
              <p>{{ renderError }}</p>
            </div>

            <!-- Mermaid output -->
            <div
              v-else
              ref="mapContainer"
              class="w-full h-full flex items-center justify-center [&_svg]:max-w-full [&_svg]:max-h-full transition-transform duration-300"
            />

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
                      <img :src="'http://localhost:8000' + hoveredNode.image_url" class="absolute inset-0 w-full h-full object-cover" />
                      <div class="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent"></div>
                    </div>

                    <!-- Content -->
                    <div class="p-5 bg-slate-900">
                      <div class="flex items-center justify-between mb-2">
                        <span class="text-sm font-bold text-white uppercase tracking-wider">{{ hoveredNode.label }}</span>
                        <div class="flex gap-1.5">
                          <span class="text-[8px] px-1.5 py-0.5 rounded border border-emerald-500/30 text-emerald-400 font-mono uppercase">
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
          </div>

          <!-- Footer hint -->
          <div class="px-8 py-3 border-t border-slate-800 text-xs text-slate-600 text-right shrink-0">
            Tip: hover over rooms for details • type <code class="text-emerald-600 font-mono">/map</code> to refresh
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.bg-grid-pattern {
  background-image: 
    linear-gradient(rgba(100, 116, 139, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(100, 116, 139, 0.05) 1px, transparent 1px);
  background-size: 40px 40px;
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
</style>
