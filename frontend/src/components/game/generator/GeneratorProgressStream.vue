<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { Brain, ChevronDown, ChevronUp, Image as ImageIcon, ZoomIn } from 'lucide-vue-next'

export interface LogEntry {
  timestamp: string
  type: 'status' | 'thinking' | 'image_generation'
  content: string
  image_url?: string
}

const props = defineProps<{
  logs: LogEntry[]
  isLoadingLogs: boolean
  isReady: boolean
  hasError: boolean
  lastStatusIndex: number
}>()

const emit = defineEmits<{
  (e: 'previewImage', url: string): void
}>()

const chatContainer = ref<HTMLDivElement | null>(null)
const isExpandedMap = ref<Record<string, boolean>>({})

function toggleExpand(timestamp: string) {
  isExpandedMap.value[timestamp] = !isExpandedMap.value[timestamp]
}

// Auto scroll to bottom on new logs
watch(
  () => props.logs.length,
  async () => {
    await nextTick()
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  }
)

defineExpose({
  scrollToBottom: async () => {
    await nextTick()
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  }
})
</script>

<template>
  <div
    ref="chatContainer"
    class="flex-1 overflow-y-auto p-4 sm:p-6 flex flex-col gap-3.5 sm:gap-4 bg-[#04080f]/50 scroll-smooth custom-scrollbar"
  >
    <!-- Loading indicator -->
    <div v-if="props.isLoadingLogs && props.logs.length === 0" class="flex-1 flex flex-col items-center justify-center gap-3 py-12">
      <div class="w-10 h-10 border-2 border-cyan-500/10 border-t-cyan-400 rounded-full animate-spin"></div>
      <span class="text-xs text-cyan-400 font-bold uppercase tracking-widest animate-pulse text-center">
        Contacting The Reality Loom...
      </span>
    </div>

    <!-- Empty indicator -->
    <div v-else-if="props.logs.length === 0" class="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs py-12 text-center">
      No logs recorded yet. World generation starting...
    </div>

    <!-- Stream -->
    <div v-else class="flex flex-col gap-3.5">
      <div
        v-for="(log, index) in props.logs"
        :key="log.timestamp"
        class="flex flex-col"
      >
        <!-- 1. Status Update Pill -->
        <div v-if="log.type === 'status'" class="flex justify-center my-1">
          <div class="px-3.5 py-1.5 rounded-full bg-slate-900/90 border border-white/10 text-[10px] sm:text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2 shadow-sm max-w-[95%] sm:max-w-none text-center">
            <span
              v-if="index === props.lastStatusIndex && !props.isReady && !props.hasError"
              class="relative flex h-1.5 w-1.5 shrink-0"
            >
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-cyan-500"></span>
            </span>
            <span class="truncate">{{ log.content }}</span>
          </div>
        </div>

        <!-- 2. LLM Thinking / Reasoning Log -->
        <div v-else-if="log.type === 'thinking'" class="flex justify-center w-full max-w-[95%] sm:max-w-[90%] self-center my-1 animate-fade-in">
          <div class="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-3.5 sm:p-4 flex flex-col gap-2 w-full items-center">
            <button
              type="button"
              class="flex items-center justify-center gap-2 text-xs font-black text-amber-400 uppercase tracking-widest select-none cursor-pointer w-full hover:text-amber-300 transition-colors"
              @click="toggleExpand(log.timestamp)"
            >
              <Brain class="w-4 h-4 shrink-0" />
              <span class="text-[11px] sm:text-xs truncate">LLM Thinking / Reasoning Process</span>
              <component :is="isExpandedMap[log.timestamp] ? ChevronUp : ChevronDown" class="w-4 h-4 shrink-0" />
            </button>
            <div
              v-if="isExpandedMap[log.timestamp]"
              class="text-xs text-amber-300/80 leading-relaxed font-mono whitespace-pre-wrap mt-2 p-3 sm:p-3.5 bg-black/60 rounded-xl border border-amber-500/10 w-full text-left custom-scrollbar max-h-60 overflow-y-auto"
            >
              {{ log.content }}
            </div>
          </div>
        </div>

        <!-- 3. Image Generation / Reused Log -->
        <div v-else-if="log.type === 'image_generation'" class="flex justify-center w-full max-w-[95%] sm:max-w-[90%] self-center my-1 animate-fade-in">
          <div class="rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-3.5 sm:p-4 flex flex-col gap-3 items-center w-full">
            <div class="flex items-center justify-center gap-2 text-xs font-black text-cyan-400 uppercase tracking-widest">
              <ImageIcon class="w-4 h-4 shrink-0" />
              <span>{{ log.content.includes('Reused source asset') ? 'Visual Asset Reused' : 'Envisioned Asset Generated' }}</span>
            </div>
            <p class="text-xs text-slate-300 italic bg-black/40 p-2.5 rounded-xl border border-white/5 leading-relaxed self-stretch text-center break-words">
              "{{ log.content }}"
            </p>
            <div
              v-if="log.image_url"
              class="relative group w-48 h-48 sm:w-60 sm:h-60 overflow-hidden rounded-xl border border-cyan-500/30 bg-[#030712] flex items-center justify-center cursor-pointer shadow-lg hover:border-cyan-400/60 transition-all active:scale-95"
              @click="emit('previewImage', log.image_url!)"
              title="Click to view full image"
            >
              <img
                :src="log.image_url"
                alt="Visual Asset"
                class="max-w-full max-h-full object-contain p-1 transition-transform duration-500 group-hover:scale-105"
              />
              <div class="absolute inset-0 bg-cyan-500/0 group-hover:bg-cyan-500/10 transition-colors flex items-end justify-end p-2">
                <span class="text-[10px] font-bold text-cyan-300 bg-black/80 px-2 py-0.5 rounded opacity-90 sm:opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                  <ZoomIn class="w-3 h-3" /> Zoom
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.3);
  border-radius: 9999px;
}
</style>
