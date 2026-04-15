<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import type { ChatMessage } from '@/types'
import type { ConnectionStatus } from '@/composables/useGameSocket'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'

const props = defineProps<{
  messages: ChatMessage[]
  status: ConnectionStatus
  npcMetadata: Record<string, any>
  entities: any[]
}>()

const emit = defineEmits<{
  send: [content: string]
  openSheet: []
  npcHover: [name: string, event: MouseEvent]
  npcLeave: []
}>()

const inputText = ref('')
const logEl = ref<HTMLElement | null>(null)
const brokenImages = ref<Record<string, boolean>>({})

const handleImageError = (path?: string | null) => {
  if (!path) return
  brokenImages.value[path] = true
}

const showImage = (path?: string | null) => {
  return !!path && !brokenImages.value[path]
}

function appendText(text: string) {
  const current = inputText.value.trim()
  inputText.value = current ? `${current} ${text}` : text
}

defineExpose({ appendText })

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
  // Pattern: **Name:**
  return text
    .replace(/\*\*(.*?):\*\*/g, (_match, name) => {
      const data = props.npcMetadata[name]
      if (data) {
        const iconOrImg = data.image_url 
          ? `<img src="${getImageUrl(data.image_url)}" class="npc-avatar" alt="${name}-portrait">`
          : `<div class="npc-avatar ra ra-player flex items-center justify-center bg-slate-800 text-amber-500/80 text-xl border-amber-500/30 font-normal"></div>`;
        
        return `<span class="npc-portrait-trigger" data-npc-name="${name}">${iconOrImg}<strong class="npc-name">${name}:</strong></span>`
      }
      return `<strong class="text-amber-400 font-bold">${name}:</strong>`
    })
    .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-white">$1</strong>')
}

function handleMouseMove(e: MouseEvent) {
  const target = e.target as HTMLElement
  const npcWrapper = target.closest('[data-npc-name]')
  if (npcWrapper) {
    const name = npcWrapper.getAttribute('data-npc-name')
    if (name) {
      emit('npcHover', name, e)
      return
    }
  }
  emit('npcLeave')
}

function normalizeLineBreaks(text: string): string {
  // Keep intentional paragraph breaks, but cap excessive blank lines.
  return text.replace(/\n{3,}/g, '\n\n')
}
</script>

<template>
  <div class="flex flex-col w-full h-full bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-xl overflow-hidden shadow-2xl relative z-10">
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
      @mousemove="handleMouseMove"
      @mouseleave="emit('npcLeave')"
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

        <!-- Discovery Cards (Items revealed this turn) -->
        <div v-if="msg.itemIds && msg.itemIds.length" class="mt-4 flex flex-wrap gap-4 pl-4">
          <div 
            v-for="itemId in msg.itemIds" 
            :key="itemId"
            v-show="entities.find(e => e.id === itemId)"
            class="item-card flex flex-col w-56 bg-slate-800/80 border border-slate-700/50 rounded-xl overflow-hidden shadow-xl backdrop-blur-sm transition-all hover:scale-[1.02] hover:border-emerald-500/30"
          >
            <!-- Item Image -->
            <div class="h-32 bg-slate-900 relative overflow-hidden group/img flex items-center justify-center">
              <img 
                v-if="entities.find(e => e.id === itemId)?.image_url && showImage(entities.find(e => e.id === itemId).image_url)" 
                :src="getImageUrl(entities.find(e => e.id === itemId).image_url)" 
                class="w-full h-full object-cover transition-transform duration-500 group-hover/img:scale-110"
                @error="handleImageError(entities.find(e => e.id === itemId).image_url)"
              />
              <div v-else class="w-full h-full flex items-center justify-center text-slate-700 bg-slate-900/50">
                <i :class="['ra text-5xl', getItemIcon(entities.find(e => e.id === itemId)?.item_type), getTypeColor(entities.find(e => e.id === itemId)?.item_type)]"></i>
              </div>
              <div class="absolute top-2 right-2 px-1.5 py-0.5 bg-emerald-500/20 text-emerald-400 text-[10px] font-bold uppercase rounded border border-emerald-500/30">
                New Discovery
              </div>
            </div>

            <!-- Item Details -->
            <div class="p-3 flex flex-col gap-1 flex-1">
              <h4 class="text-white font-bold text-sm truncate">{{ entities.find(e => e.id === itemId)?.name }}</h4>
              <p class="text-slate-400 text-[11px] leading-tight line-clamp-3 mb-2 italic">
                {{ entities.find(e => e.id === itemId)?.description }}
              </p>
              
              <button 
                v-if="entities.find(e => e.id === itemId)?.is_portable !== false"
                class="mt-auto py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 active:scale-95 shadow-lg shadow-emerald-500/10"
                @click="emit('send', `/take ${entities.find(e => e.id === itemId)?.name}`)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M8 9a3 3 0 100-6 3 3 0 000 6zM8 11a6 6 0 016 6H2a6 6 0 016-6zM16 7a1 1 0 10-2 0v1h-1a1 1 0 100 2h1v1a1 1 0 102 0v-1h1a1 1 0 100-2h-1V7z" />
                </svg>
                Take Item
              </button>
            </div>
          </div>
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

<style scoped>
/* Target elements inside v-html */
:deep(.npc-portrait-trigger) {
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  vertical-align: middle;
  margin-right: 0.5rem;
  cursor: help;
}

:deep(.npc-avatar) {
  width: 2.5rem; /* 40px */
  height: 2.5rem;
  border-radius: 9999px;
  object-fit: cover;
  border: 2px solid rgba(245, 158, 11, 0.4); /* amber-500/40 */
  box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
}

:deep(.npc-name) {
  color: #fbbf24; /* amber-400 */
  font-weight: 700;
  font-size: 0.9375rem; /* 15px */
  line-height: 1;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.item-card {
  animation: cardAppear 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes cardAppear {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* Ensure RPG Awesome icons render correctly */
.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
