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
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const mapContainer = ref<HTMLDivElement | null>(null)
const renderError = ref<string | null>(null)

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    primaryColor: '#1e293b',
    primaryTextColor: '#e2e8f0',
    primaryBorderColor: '#475569',
    lineColor: '#64748b',
    secondaryColor: '#0f172a',
    tertiaryColor: '#0f172a',
    background: '#0f172a',
    mainBkg: '#1e293b',
    nodeBorder: '#475569',
    clusterBkg: '#0f172a',
    titleColor: '#10b981',
    edgeLabelBackground: '#0f172a',
    fontFamily: 'Inter, system-ui, sans-serif',
  },
})

/** Re-renders the Mermaid diagram whenever the source changes or modal opens. */
async function renderMermaid(): Promise<void> {
  if (!props.open || !mapContainer.value || !props.mermaidSrc) return

  renderError.value = null
  mapContainer.value.innerHTML = ''

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
          <div class="flex-grow overflow-auto p-6 relative bg-slate-950">
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
              class="w-full h-full flex items-center justify-center [&_svg]:max-w-full [&_svg]:max-h-full"
            />
          </div>

          <!-- Footer hint -->
          <div class="px-8 py-3 border-t border-slate-800 text-xs text-slate-600 text-right shrink-0">
            Tip: type <code class="text-emerald-600 font-mono">/map</code> in the game to refresh
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
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
