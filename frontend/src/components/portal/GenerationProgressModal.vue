<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { api, GENERATION_SAYINGS } from '@/composables/useApi'
import { ChevronDown, ChevronUp, Image as ImageIcon, Brain } from 'lucide-vue-next'

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
            <div v-else-if="log.type === 'thinking'" class="flex justify-start max-w-[85%] self-start my-1">
              <div class="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 flex flex-col gap-2 w-full">
                <button 
                  class="flex items-center gap-2 text-xs font-black text-amber-400 uppercase tracking-widest select-none cursor-pointer"
                  @click="toggleExpand(log.timestamp)"
                >
                  <Brain class="w-4 h-4 shrink-0" />
                  <span>LLM Thinking / Reasoning Process</span>
                  <component :is="isExpandedMap[log.timestamp] ? ChevronUp : ChevronDown" class="w-4 h-4" />
                </button>
                <div 
                  v-if="isExpandedMap[log.timestamp]"
                  class="text-xs text-amber-300/80 leading-relaxed font-mono whitespace-pre-wrap mt-2 p-3 bg-black/40 rounded-lg border border-amber-500/10"
                >
                  {{ log.content }}
                </div>
              </div>
            </div>

            <!-- 3. Image Generation / Reused Log -->
            <div v-else-if="log.type === 'image_generation'" class="flex justify-end max-w-[85%] self-end my-1">
              <div class="rounded-xl border border-sky-500/20 bg-sky-500/5 p-4 flex flex-col gap-3 items-end">
                <div class="flex items-center gap-2 text-xs font-black text-sky-400 uppercase tracking-widest self-start">
                  <ImageIcon class="w-4 h-4 shrink-0" />
                  <span>{{ log.content.includes('Reused source asset') ? 'Visual Asset Reused' : 'Envisioned Asset Generated' }}</span>
                </div>
                <p class="text-xs text-slate-300 italic bg-black/30 p-2.5 rounded-lg border border-white/5 leading-relaxed self-stretch">
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
