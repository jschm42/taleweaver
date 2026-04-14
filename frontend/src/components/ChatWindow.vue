<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import type { ChatMessage } from '@/types'
import type { ConnectionStatus } from '@/composables/useGameSocket'

const props = defineProps<{
  messages: ChatMessage[]
  status: ConnectionStatus
}>()

const emit = defineEmits<{
  send: [content: string]
  openSheet: []
}>()

const inputText = ref('')
const logEl = ref<HTMLElement | null>(null)

watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    if (logEl.value) {
      logEl.value.scrollTop = logEl.value.scrollHeight
    }
  },
)

const isConnected = computed(() => props.status === 'connected')
const statusLabel = computed(() => {
  const map: Record<ConnectionStatus, string> = {
    loading: 'Loading…',
    disconnected: 'Disconnected',
    connecting: 'Connecting…',
    connected: 'Connected',
    error: 'Error',
    game_over: 'Game Over',
  }
  return map[props.status]
})
const statusColor = computed(() => {
  const map: Record<ConnectionStatus, string> = {
    loading: 'text-blue-500 bg-blue-500/10 border-blue-500/20',
    disconnected: 'text-slate-500 bg-slate-500/10 border-slate-500/20',
    connecting: 'text-amber-500 bg-amber-500/10 border-amber-500/20',
    connected: 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20',
    error: 'text-red-500 bg-red-500/10 border-red-500/20',
    game_over: 'text-purple-500 bg-purple-500/10 border-purple-500/20',
  }
  return map[props.status]
})

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function handleSend(): void {
  const text = inputText.value.trim()
  if (!text) return

  if (text === '/sheet') {
    emit('openSheet')
    inputText.value = ''
    return
  }

  emit('send', text)
  inputText.value = ''
}

function handleKeydown(e: KeyboardEvent): void {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

/**
 * Very basic markdown parser for images and bolds.
 */
function parseContent(content: string) {
  const parts: any[] = []
  const imgRegex = /!\[(.*?)\]\((.*?)\)/g
  let lastIdx = 0
  let match

  while ((match = imgRegex.exec(content)) !== null) {
    if (match.index > lastIdx) {
      parts.push({ type: 'text', value: content.slice(lastIdx, match.index) })
    }
    parts.push({ type: 'image', alt: match[1], url: match[2] })
    lastIdx = match.index + match[0].length
  }

  if (lastIdx < content.length) {
    parts.push({ type: 'text', value: content.slice(lastIdx) })
  }

  return parts
}

function formatBolds(text: string) {
  return text
    .replace(/\*\*(.*?):\*\*/g, '<strong class="text-amber-400 font-bold">$1:</strong>')
    .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-white">$1</strong>')
}

function normalizeLineBreaks(text: string): string {
  // Keep intentional paragraph breaks, but cap excessive blank lines.
  return text.replace(/\n{3,}/g, '\n\n')
}
</script>

<template>
  <div class="flex flex-col h-full bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
    <!-- Header -->
    <div class="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-950/50 backdrop-blur-md shrink-0">
      <div class="flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-emerald-500" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M18 5v8a2 2 0 01-2 2h-5l-5 4v-4H4a2 2 0 01-2-2V5a2 2 0 012-2h12a2 2 0 012 2zM7 8H5v2h2V8zm2 0h2v2H9V8zm6 0h-2v2h2V8z" clip-rule="evenodd" />
        </svg>
        <span class="text-slate-300 text-sm font-semibold tracking-wide uppercase">Chronicle Log</span>
      </div>
      <div :class="['px-2.5 py-1 text-xs font-semibold rounded-full border flex items-center gap-1.5', statusColor]">
        <span class="w-1.5 h-1.5 rounded-full bg-current shadow-[0_0_8px_currentColor]"></span>
        {{ statusLabel }}
      </div>
    </div>

    <!-- Message log -->
    <div
      ref="logEl"
      class="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-h-0 relative scroll-smooth"
      aria-live="polite"
      aria-label="Game log"
    >
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="group flex flex-col pt-1"
      >
        <!-- Author info -->
        <div class="flex items-center gap-3 mb-1.5">
          <span 
            :class="[
              'text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded',
              msg.role === 'user' ? 'bg-cyan-500/20 text-cyan-400' :
              msg.role === 'assistant' ? 'bg-amber-500/20 text-amber-500' :
              'bg-emerald-500/20 text-emerald-500'
            ]"
          >
            {{ msg.role === 'user' ? 'You' : msg.role === 'assistant' ? 'Game Master' : 'System' }}
          </span>
          <span class="text-xs text-slate-600 font-mono opacity-0 group-hover:opacity-100 transition-opacity">
            {{ formatTime(msg.timestamp) }}
          </span>
        </div>

        <!-- Content -->
        <div
          :class="[
            'text-sm leading-normal whitespace-pre-wrap break-words pl-4 border-l-2',
            msg.role === 'user' ? 'text-slate-300 border-cyan-500/50' :
            msg.role === 'assistant' ? 'text-amber-50/90 border-amber-500/50' :
            'text-emerald-300 border-emerald-500/50 italic opacity-80'
          ]"
        >
          <template v-for="(part, pIdx) in parseContent(msg.content)" :key="pIdx">
            <span v-if="part.type === 'text'" v-html="formatBolds(normalizeLineBreaks(part.value))"></span>
            <div v-else-if="part.type === 'image'" class="my-4 rounded-xl overflow-hidden border border-white/10 shadow-lg">
              <img :src="part.url" :alt="part.alt" class="w-full max-h-80 object-cover" />
              <div v-if="part.alt" class="px-3 py-1.5 bg-black/40 text-[10px] text-slate-400 font-bold uppercase tracking-widest">{{ part.alt }}</div>
            </div>
          </template>
        </div>
      </div>

      <!-- Connecting/empty state -->
      <div v-if="isConnected && messages.length === 0" class="absolute inset-0 flex items-center justify-center text-slate-500 text-sm">
        <div class="flex flex-col items-center gap-3">
          <div class="w-8 h-8 rounded-full border-t-2 border-emerald-500 animate-spin"></div>
          <p>Awaiting game start...</p>
        </div>
      </div>
    </div>

    <!-- Input bar -->
    <div class="border-t border-slate-800 bg-slate-950 p-4 shrink-0">
      <div class="relative flex items-center">
        <div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-emerald-500" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
          </svg>
        </div>
        <input
          v-model="inputText"
          type="text"
          :disabled="!isConnected"
          placeholder="What do you do next?"
          class="w-full bg-slate-900 border border-slate-800 focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 rounded-xl py-3.5 pl-11 pr-16 text-slate-200 placeholder-slate-600 outline-none transition-all disabled:opacity-50"
          @keydown="handleKeydown"
        />
        <div class="absolute inset-y-0 right-2 flex items-center">
          <button
            :disabled="!isConnected || !inputText.trim()"
            class="p-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-white disabled:bg-slate-800 disabled:text-slate-600 transition-colors"
            @click="handleSend"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
            </svg>
          </button>
        </div>
      </div>
      
      <div class="flex gap-4 mt-3 px-1 text-[11px] text-slate-500">
        <span><kbd class="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400">/sheet</kbd> to view character</span>
        <span><kbd class="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400">/equip</kbd> to equip</span>
      </div>
    </div>
  </div>
</template>
