<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { api, GENERATION_SAYINGS } from '@/composables/useApi'
import { ChevronDown, ChevronUp, Image as ImageIcon, Brain, BarChart3 } from 'lucide-vue-next'

const props = defineProps<{
  adventureId: string
  adventureTitle: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

interface LogEntry {
  timestamp: string
  type: 'status' | 'thinking' | 'image_generation'
  content: string
  image_url?: string
}

const logs = ref<LogEntry[]>([])
const isLoading = ref(true)
const isExpandedMap = ref<Record<string, boolean>>({}) // For collapsing/expanding thoughts
const chatContainer = ref<HTMLDivElement | null>(null)

let pollTimer: number | null = null

async function fetchLogs() {
  try {
    const data = await api.getAdventureGenerationLogs(props.adventureId)
    logs.value = data.logs || []
    
    // Auto scroll to bottom
    await nextTick()
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  } catch (error) {
    console.error('Error fetching generation logs:', error)
  } finally {
    isLoading.value = false
  }
}

// Check if generation is still active
const isReady = ref(false)
const hasError = ref(false)

async function checkStatus() {
  try {
    const statusData = await api.getAdventureStatus(props.adventureId)
    isReady.value = statusData.is_ready
    if (statusData.error || statusData.status === 'Failed' || statusData.status === 'Cancelled') {
      hasError.value = true
    }
    
    if (isReady.value || hasError.value) {
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    }
  } catch (error) {
    console.error('Error checking status:', error)
  }
}

function toggleExpand(timestamp: string) {
  isExpandedMap.value[timestamp] = !isExpandedMap.value[timestamp]
}

const lastStatusIndex = computed(() => {
  let lastIdx = -1
  for (let i = logs.value.length - 1; i >= 0; i--) {
    if (logs.value[i].type === 'status') {
      lastIdx = i
      break
    }
  }
  return lastIdx
})

const assetStats = computed(() => {
  const stats = {
    cover: { generated: 0, reused: 0 },
    protagonist: { generated: 0, reused: 0 },
    scene: { generated: 0, reused: 0 },
    npc: { generated: 0, reused: 0 },
    item: { generated: 0, reused: 0 }
  }
  
  logs.value.forEach((log, index) => {
    if (log.type !== 'image_generation') return
    
    const isReused = log.content.includes('Reused source asset')
    
    if (isReused) {
      const contentLower = log.content.toLowerCase()
      if (contentLower.includes('adventure cover')) {
        stats.cover.reused++
      } else if (contentLower.includes('protagonist')) {
        stats.protagonist.reused++
      } else if (contentLower.includes('scene:')) {
        stats.scene.reused++
      } else if (contentLower.includes('npc:')) {
        stats.npc.reused++
      } else if (contentLower.includes('item:')) {
        stats.item.reused++
      }
    } else {
      let assetType = 'other'
      for (let i = index - 1; i >= 0; i--) {
        if (logs.value[i].type === 'status') {
          const statusText = logs.value[i].content.toLowerCase()
          if (statusText.includes('adventure cover') || statusText.includes('painting cover')) {
            assetType = 'cover'
          } else if (statusText.includes('portrait for npc') || statusText.includes('npc:')) {
            assetType = 'npc'
          } else if (statusText.includes('portrait for item') || statusText.includes('item:')) {
            assetType = 'item'
          } else if (statusText.includes('portrait for') || statusText.includes('protagonist')) {
            assetType = 'protagonist'
          } else if (statusText.includes('scene:') || statusText.includes('drawing scene')) {
            assetType = 'scene'
          }
          break
        }
      }
      
      if (assetType === 'cover') stats.cover.generated++
      else if (assetType === 'protagonist') stats.protagonist.generated++
      else if (assetType === 'scene') stats.scene.generated++
      else if (assetType === 'npc') stats.npc.generated++
      else if (assetType === 'item') stats.item.generated++
    }
  })
  
  return stats
})

const totalStats = computed(() => {
  let generated = 0
  let reused = 0
  Object.values(assetStats.value).forEach(stat => {
    generated += stat.generated
    reused += stat.reused
  })
  return { generated, reused }
})

const currentSaying = ref(GENERATION_SAYINGS[Math.floor(Math.random() * GENERATION_SAYINGS.length)])
let sayingTimer: number | null = null

function updateSaying() {
  const randomIndex = Math.floor(Math.random() * GENERATION_SAYINGS.length)
  currentSaying.value = GENERATION_SAYINGS[randomIndex]
}

onMounted(() => {
  void fetchLogs()
  void checkStatus()
  
  pollTimer = window.setInterval(() => {
    void fetchLogs()
    void checkStatus()
  }, 1500)

  sayingTimer = window.setInterval(updateSaying, 5000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
  }
  if (sayingTimer) {
    clearInterval(sayingTimer)
  }
})
</script>

<template>
  <div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-fade-in font-ui">
    <div class="w-full max-w-2xl h-[80vh] flex flex-col rounded-2xl bg-[#070e17]/95 border border-white/10 shadow-[0_0_50px_rgba(56,189,248,0.15)] overflow-hidden">
      <!-- Modal Header -->
      <div class="px-6 py-4 border-b border-white/10 flex justify-between items-center bg-[#0a1424]">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <i class="ra ra-scroll text-lg animate-pulse"></i>
          </div>
          <div>
            <h3 class="text-md font-black text-white uppercase tracking-wider">Generation Progress</h3>
            <p class="text-xs text-slate-400 mt-0.5">Adventure: <span class="font-bold text-sky-400">{{ props.adventureTitle }}</span></p>
          </div>
        </div>
      </div>

      <!-- Log Content (Chat-like) -->
      <div 
        ref="chatContainer"
        class="flex-1 overflow-y-auto p-6 flex flex-col gap-4 bg-[#04080f]/50 scroll-smooth"
      >
        <div v-if="isLoading" class="flex-1 flex flex-col items-center justify-center gap-3">
          <div class="w-10 h-10 border-2 border-sky-500/10 border-t-sky-400 rounded-full animate-spin"></div>
          <span class="text-[10px] text-sky-400 font-bold uppercase tracking-widest">Opening Chronicles...</span>
        </div>

        <div v-else-if="logs.length === 0" class="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs">
          No logs recorded yet. Generation starting...
        </div>

        <div v-else class="flex flex-col gap-4">
          <div 
            v-for="(log, index) in logs" 
            :key="log.timestamp" 
            class="flex flex-col"
          >
            <!-- 1. Status Update -->
            <div v-if="log.type === 'status'" class="flex justify-center my-2">
              <div class="px-4 py-1.5 rounded-full bg-slate-900 border border-white/5 text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                <span 
                  v-if="index === lastStatusIndex && !isReady && !hasError" 
                  class="relative flex h-1.5 w-1.5 shrink-0"
                >
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-sky-500"></span>
                </span>
                {{ log.content }}
              </div>
            </div>

            <!-- 2. Thinking Log -->
            <div v-else-if="log.type === 'thinking'" class="flex justify-center w-full max-w-[85%] self-center my-1 animate-fade-in">
              <div class="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 flex flex-col gap-2 w-full items-center">
                <button 
                  class="flex items-center justify-center gap-2 text-xs font-black text-amber-400 uppercase tracking-widest select-none cursor-pointer w-full"
                  @click="toggleExpand(log.timestamp)"
                >
                  <Brain class="w-4 h-4 shrink-0" />
                  <span>LLM Thinking / Reasoning Process</span>
                  <component :is="isExpandedMap[log.timestamp] ? ChevronUp : ChevronDown" class="w-4 h-4" />
                </button>
                <div 
                  v-if="isExpandedMap[log.timestamp]"
                  class="text-xs text-amber-300/80 leading-relaxed font-mono whitespace-pre-wrap mt-2 p-3 bg-black/40 rounded-lg border border-amber-500/10 w-full text-left"
                >
                  {{ log.content }}
                </div>
              </div>
            </div>

            <!-- 3. Image Generation / Reused Log -->
            <div v-else-if="log.type === 'image_generation'" class="flex justify-center w-full max-w-[85%] self-center my-1 animate-fade-in">
              <div class="rounded-xl border border-sky-500/20 bg-sky-500/5 p-4 flex flex-col gap-3 items-center w-full">
                <div class="flex items-center justify-center gap-2 text-xs font-black text-sky-400 uppercase tracking-widest">
                  <ImageIcon class="w-4 h-4 shrink-0" />
                  <span>{{ log.content.includes('Reused source asset') ? 'Visual Asset Reused' : 'Envisioned Asset Generated' }}</span>
                </div>
                <p class="text-xs text-slate-300 italic bg-black/30 p-2.5 rounded-lg border border-white/5 leading-relaxed self-stretch text-center">
                  "{{ log.content }}"
                </p>
                <div v-if="log.image_url" class="relative group w-60 h-60 overflow-hidden rounded-lg border border-white/10 bg-[#030712] flex items-center justify-center">
                  <img 
                    :src="log.image_url" 
                    alt="Visual Asset" 
                    class="max-w-full max-h-full object-contain p-1 transition-transform duration-500 group-hover:scale-105"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- Statistics Summary (shown when generation is complete) -->
          <div v-if="isReady || hasError" class="mt-6 p-5 rounded-2xl border border-sky-500/20 bg-sky-500/5 backdrop-blur-md flex flex-col gap-4 self-center w-full max-w-[85%] shadow-[0_0_20px_rgba(56,189,248,0.05)] animate-fade-in">
            <div class="flex items-center justify-between border-b border-white/10 pb-3">
              <div class="flex items-center gap-2">
                <BarChart3 class="w-4 h-4 text-sky-400 shrink-0" />
                <h4 class="text-xs font-black text-white uppercase tracking-widest">Generation Summary</h4>
              </div>
              <span class="text-[10px] font-black uppercase tracking-widest px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/30">
                {{ isReady ? 'Success' : 'Failed / Cancelled' }}
              </span>
            </div>

            <div class="grid grid-cols-2 sm:grid-cols-5 gap-3">
              <!-- Cover Stat -->
              <div class="flex flex-col items-center p-3 rounded-xl bg-black/40 border border-white/5 text-center">
                <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Cover</span>
                <div class="flex flex-col gap-1 w-full text-[9px] font-black">
                  <div class="flex justify-between px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400">
                    <span>Created</span>
                    <span>{{ assetStats.cover.generated }}</span>
                  </div>
                  <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
                    <span>Reused</span>
                    <span>{{ assetStats.cover.reused }}</span>
                  </div>
                </div>
              </div>

              <!-- Protagonist Stat -->
              <div class="flex flex-col items-center p-3 rounded-xl bg-black/40 border border-white/5 text-center">
                <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Hero</span>
                <div class="flex flex-col gap-1 w-full text-[9px] font-black">
                  <div class="flex justify-between px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400">
                    <span>Created</span>
                    <span>{{ assetStats.protagonist.generated }}</span>
                  </div>
                  <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
                    <span>Reused</span>
                    <span>{{ assetStats.protagonist.reused }}</span>
                  </div>
                </div>
              </div>

              <!-- Scenes Stat -->
              <div class="flex flex-col items-center p-3 rounded-xl bg-black/40 border border-white/5 text-center">
                <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Scenes</span>
                <div class="flex flex-col gap-1 w-full text-[9px] font-black">
                  <div class="flex justify-between px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400">
                    <span>Created</span>
                    <span>{{ assetStats.scene.generated }}</span>
                  </div>
                  <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
                    <span>Reused</span>
                    <span>{{ assetStats.scene.reused }}</span>
                  </div>
                </div>
              </div>

              <!-- NPCs Stat -->
              <div class="flex flex-col items-center p-3 rounded-xl bg-black/40 border border-white/5 text-center">
                <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">NPCs</span>
                <div class="flex flex-col gap-1 w-full text-[9px] font-black">
                  <div class="flex justify-between px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400">
                    <span>Created</span>
                    <span>{{ assetStats.npc.generated }}</span>
                  </div>
                  <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
                    <span>Reused</span>
                    <span>{{ assetStats.npc.reused }}</span>
                  </div>
                </div>
              </div>

              <!-- Items Stat -->
              <div class="flex flex-col items-center p-3 rounded-xl bg-black/40 border border-white/5 text-center">
                <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Items</span>
                <div class="flex flex-col gap-1 w-full text-[9px] font-black">
                  <div class="flex justify-between px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400">
                    <span>Created</span>
                    <span>{{ assetStats.item.generated }}</span>
                  </div>
                  <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
                    <span>Reused</span>
                    <span>{{ assetStats.item.reused }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="flex justify-between items-center text-[10px] font-bold text-slate-400 uppercase tracking-widest border-t border-white/10 pt-3">
              <div class="flex items-center gap-4">
                <span>Total Created: <span class="text-sky-400 font-black">{{ totalStats.generated }}</span></span>
                <span>Total Reused: <span class="text-purple-400 font-black">{{ totalStats.reused }}</span></span>
              </div>
              <div class="text-slate-500">
                Total Assets: <span class="text-white font-black">{{ totalStats.generated + totalStats.reused }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer / Status indicator -->
      <div class="px-6 py-4 border-t border-white/10 bg-[#060b13] flex justify-between items-center">
        <div class="flex items-center gap-2 text-xxs font-bold uppercase tracking-wider">
          <span v-if="isReady" class="text-emerald-400 flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full bg-emerald-400"></span> Ready
          </span>
          <span v-else-if="hasError" class="text-red-400 flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full bg-red-400"></span> Failed / Cancelled
          </span>
          <span v-else class="text-sky-400 flex items-center gap-1.5 max-w-[450px] line-clamp-1">
            <span class="w-2 h-2 border-2 border-sky-400/20 border-t-sky-400 rounded-full animate-spin shrink-0"></span>
            <span>{{ currentSaying }}</span>
          </span>
        </div>
        <button 
          class="px-5 py-2 rounded-xl text-xs font-black uppercase tracking-widest transition-all duration-200 border"
          :class="[
            isReady || hasError
              ? 'bg-sky-600 border-sky-500 text-white hover:bg-sky-500 hover:shadow-[0_0_15px_rgba(56,189,248,0.4)]'
              : 'bg-transparent border-white/10 text-slate-400 hover:text-white hover:border-white/20'
          ]"
          @click="emit('close')"
        >
          {{ isReady || hasError ? 'Done' : 'Close' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
