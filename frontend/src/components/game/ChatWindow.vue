<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import BableFishSelector from '@/components/game/BableFishSelector.vue'
import type { ChatMessage } from '@/types'
import CommandPopup from '@/components/game/CommandPopup.vue'
import type { ConnectionStatus } from '@/composables/useGameSocket'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'

const props = defineProps<{
  messages: ChatMessage[]
  status: ConnectionStatus
  npcMetadata: Record<string, any>
  entities: any[]
  inventory: any[]
  trackedQuest?: any
  statusText?: string
  showDebugLog?: boolean
  debugLogs?: { timestamp: string, content: string }[]
  inventoryGlow?: boolean
  mapGlow?: boolean
  questGlow?: boolean
}>()

const emit = defineEmits<{
  send: [content: string]
  openSheet: []
  openQuests: []
  npcHover: [name: string, event: MouseEvent]
  npcLeave: []
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
  openMap: []
  openDebug: []
  toggleDebugLog: [enabled: boolean]
  takeDirect: [entity: any]
}>()

const inputText = ref('')
const fontSize = ref<'small' | 'medium' | 'large'>((localStorage.getItem('tw_chat_font_size') as any) || 'medium')
const logEl = ref<HTMLElement | null>(null)
const brokenImages = ref<Record<string, boolean>>({})

// Command Auto-completion
const showCommandPopup = ref(false)
const commandPopupIndex = ref(0)
const commands = [
  { id: '/sheet', label: '/sheet' },
  { id: '/inventory', label: '/inventory' },
  { id: '/map', label: '/map' },
  { id: '/quests', label: '/quests' },
  { id: '/hint', label: '/hint' },
  { id: '/walkthrough', label: '/walkthrough' },
  { id: '/equip', label: '/equip' },
  { id: '/unequip', label: '/unequip' },
  { id: '/consume', label: '/consume' },
  { id: '/debug session', label: '/debug session' },
  { id: '/debug reveal_map', label: '/debug reveal_map' },
  { id: '/debug walkthrough', label: '/debug walkthrough' },
  { id: '/debug log on', label: '/debug log on' },
  { id: '/debug log off', label: '/debug log off' },
]

// Command History
const history = ref<string[]>(JSON.parse(sessionStorage.getItem('tw_chat_history') || '[]'))
const historyIndex = ref(-1)

function addToHistory(text: string) {
  if (!text) return
  // Don't add if same as last entry
  if (history.value[0] === text) return
  
  history.value.unshift(text)
  if (history.value.length > 20) {
    history.value.pop()
  }
  sessionStorage.setItem('tw_chat_history', JSON.stringify(history.value))
}

function navigateHistory(direction: 'up' | 'down') {
  if (history.value.length === 0) return

  if (direction === 'up') {
    if (historyIndex.value < history.value.length - 1) {
      historyIndex.value++
      inputText.value = history.value[historyIndex.value]
    }
  } else {
    if (historyIndex.value > 0) {
      historyIndex.value--
      inputText.value = history.value[historyIndex.value]
    } else if (historyIndex.value === 0) {
      historyIndex.value = -1
      inputText.value = ''
    }
  }
}

const filteredCommands = computed(() => {
  if (!inputText.value.startsWith('/')) return []
  const q = inputText.value.toLowerCase().slice(1)
  if (!q) return commands
  return commands.filter(c => c.label.toLowerCase().includes(q))
})

watch(inputText, (newVal) => {
  if (newVal.startsWith('/')) {
    showCommandPopup.value = true
    // Reset index if query changes and index is out of bounds
    if (commandPopupIndex.value >= filteredCommands.value.length) {
      commandPopupIndex.value = 0
    }
  } else {
    showCommandPopup.value = false
  }
})

function selectCommand(cmdId: string) {
  inputText.value = cmdId + ' '
  showCommandPopup.value = false
}

watch(fontSize, (newSize) => {
  localStorage.setItem('tw_chat_font_size', newSize)
})

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
  () => props.messages,
  async () => {
    await nextTick()
    if (logEl.value) {
      logEl.value.scrollTop = logEl.value.scrollHeight
    }
  },
  { deep: true }
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
    completed: 'Completed',
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
    completed: 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20',
  }
  return map[props.status]
})

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function handleSend(): void {
  const text = inputText.value.trim()
  if (!text) return

  if (text.startsWith('/debug log')) {
    const parts = text.split(' ')
    const sub = parts[2] // on, off

    if (sub === 'on') {
      emit('toggleDebugLog', true)
    } else if (sub === 'off') {
      emit('toggleDebugLog', false)
    }
  }

  addToHistory(text)
  emit('send', text)
  inputText.value = ''
  historyIndex.value = -1
}

function handleKeydown(e: KeyboardEvent): void {
  // History Navigation (Ctrl + Up/Down)
  if (e.ctrlKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
    e.preventDefault()
    navigateHistory(e.key === 'ArrowUp' ? 'up' : 'down')
    return
  }

  if (showCommandPopup.value && filteredCommands.value.length > 0) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      commandPopupIndex.value = (commandPopupIndex.value + 1) % filteredCommands.value.length
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      commandPopupIndex.value = (commandPopupIndex.value - 1 + filteredCommands.value.length) % filteredCommands.value.length
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      const selected = filteredCommands.value[commandPopupIndex.value]
      if (selected) {
        selectCommand(selected.id)
      } else {
        showCommandPopup.value = false
        handleSend()
      }
      return
    }
    if (e.key === 'Escape') {
      e.preventDefault()
      showCommandPopup.value = false
      return
    }
  }

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
  // Matches ![alt](url) OR ```lang\ncode\n```
  const combinedRegex = /!\[(.*?)\]\((.*?)\)|```([a-z]*)\n([\s\S]*?)```/g
  let lastIdx = 0
  let match

  while ((match = combinedRegex.exec(content)) !== null) {
    if (match.index > lastIdx) {
      parts.push({ type: 'text', value: content.slice(lastIdx, match.index) })
    }
    
    if (match[1] !== undefined) {
      parts.push({ type: 'image', alt: match[1], url: match[2] })
    } else {
      parts.push({ type: 'code', lang: match[3], value: match[4] })
    }
    
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

function displayMessageContent(msg: ChatMessage): string {
  if (msg.role === 'system') {
    return msg.content.replace(/^\s*\[system\]\s*/i, '')
  }
  return msg.content
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
      <div class="flex items-center gap-4">
        <!-- Font Size Controls -->
        <div class="flex items-center bg-slate-950/40 border border-slate-800/50 rounded-xl p-1 mr-2 shadow-inner backdrop-blur-sm">
          <button 
            @click="fontSize = 'small'" 
            :class="['w-8 h-8 flex items-center justify-center rounded-lg transition-all transform active:scale-90', fontSize === 'small' ? 'bg-emerald-500 text-white shadow-[0_0_20px_rgba(16,185,129,0.4)] ring-2 ring-emerald-400/50 scale-105 z-10' : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/80']"
            title="Small Font"
          >
            <span class="text-xs font-black">A</span>
          </button>
          <button 
            @click="fontSize = 'medium'" 
            :class="['w-8 h-8 flex items-center justify-center rounded-lg transition-all transform active:scale-90', fontSize === 'medium' ? 'bg-emerald-500 text-white shadow-[0_0_20px_rgba(16,185,129,0.4)] ring-2 ring-emerald-400/50 scale-105 z-10' : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/80']"
            title="Medium Font"
          >
            <span class="text-xs font-black">A</span>
          </button>
          <button 
            @click="fontSize = 'large'" 
            :class="['w-8 h-8 flex items-center justify-center rounded-lg transition-all transform active:scale-90', fontSize === 'large' ? 'bg-emerald-500 text-white shadow-[0_0_20px_rgba(16,185,129,0.4)] ring-2 ring-emerald-400/50 scale-105 z-10' : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/80']"
            title="Large Font"
          >
            <span class="text-sm font-black">A</span>
          </button>
        </div>
        
        <BableFishSelector />

        <div 
          v-if="status !== 'connected'"
          :class="['px-2.5 py-1 text-xs font-semibold rounded-full border flex items-center gap-2 animate-fade-in', statusColor]"
        >
          <template v-if="status === 'connecting' || status === 'loading'">
            <span v-if="statusText" class="text-xs uppercase font-black opacity-70 tracking-widest">{{ statusText }}</span>
            <div class="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
          </template>
          <template v-else>
            <span class="w-1.5 h-1.5 rounded-full bg-current shadow-[0_0_8px_currentColor]"></span>
            {{ statusLabel }}
          </template>
        </div>
      </div>
    </div>

    <!-- Message log -->
    <div
      ref="logEl"
      class="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-h-0 relative scroll-smooth custom-scrollbar"
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
              'text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded',
              (msg as any).is_debug ? 'bg-cyan-500/30 text-cyan-300 border border-cyan-500/50' :
              msg.role === 'user' ? 'bg-cyan-500/20 text-cyan-400' :
              msg.role === 'assistant' ? 'bg-amber-500/20 text-amber-500' :
              'bg-emerald-500/20 text-emerald-500'
            ]"
          >
            {{ (msg as any).is_debug ? 'Debug' : msg.role === 'user' ? 'You' : msg.role === 'assistant' ? 'Game Master' : 'System' }}
          </span>
          <span class="text-xs text-slate-600 font-mono opacity-0 group-hover:opacity-100 transition-opacity">
            {{ formatTime(msg.timestamp) }}
          </span>
        </div>

        <!-- Content -->
        <div
          :class="[
            'leading-relaxed whitespace-pre-wrap break-words pl-4 border-l-2',
            fontSize === 'small' ? 'text-xs' : fontSize === 'large' ? 'text-base' : 'text-sm',
            msg.role === 'user' ? 'text-slate-300 border-cyan-500/50' :
            msg.role === 'assistant' ? 'text-amber-50/90 border-amber-500/50' :
            'text-emerald-300 border-emerald-500/50 italic opacity-80'
          ]"
        >
          <template v-for="(part, pIdx) in parseContent(displayMessageContent(msg))" :key="pIdx">
            <span v-if="part.type === 'text'" v-html="formatBolds(normalizeLineBreaks(part.value))"></span>
            <div v-else-if="part.type === 'image'" class="my-4 rounded-xl overflow-hidden border border-white/10 shadow-lg">
              <img :src="part.url" :alt="part.alt" class="w-full max-h-80 object-cover" />
              <div v-if="part.alt" class="px-3 py-1.5 bg-black/40 text-xxs text-slate-400 font-bold uppercase tracking-widest">{{ part.alt }}</div>
            </div>
            <pre v-else-if="part.type === 'code'" class="my-3 p-4 bg-slate-950 border border-slate-800 rounded-xl text-xs font-mono text-cyan-400 overflow-x-auto whitespace-pre custom-scrollbar shadow-inner">{{ part.value }}</pre>
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
              <div class="absolute top-2 right-2 px-1.5 py-0.5 bg-emerald-500/20 text-emerald-400 text-xxs font-bold uppercase rounded border border-emerald-500/30">
                New Discovery
              </div>
            </div>

            <!-- Item Details -->
            <div class="p-3 flex flex-col gap-1 flex-1">
              <h4 class="text-white font-bold text-sm truncate">{{ entities.find(e => e.id === itemId)?.name }}</h4>
              <p class="text-slate-400 text-xs leading-tight line-clamp-3 mb-2 italic">
                {{ entities.find(e => e.id === itemId)?.description }}
              </p>
              
              <button 
                v-if="entities.find(e => e.id === itemId)?.is_portable !== false"
                class="mt-auto py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 active:scale-95 shadow-lg shadow-emerald-500/10"
                @click="emit('takeDirect', entities.find(e => e.id === itemId))"
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

      <!-- Debug Logs (Technical) -->
      <template v-if="showDebugLog && debugLogs?.length">
        <div 
          v-for="(log, lidx) in debugLogs" 
          :key="'debug-' + lidx"
          class="flex items-center gap-3 py-1 opacity-40 hover:opacity-100 transition-opacity"
        >
          <div class="shrink-0 w-12 text-xs font-mono text-slate-600 tabular-nums">{{ log.timestamp }}</div>
          <div class="flex-grow h-px bg-slate-800/50"></div>
          <div class="shrink-0 text-xs font-mono text-cyan-500 uppercase tracking-widest bg-cyan-500/5 px-2 py-0.5 rounded border border-cyan-500/10">
            [DEBUG] {{ log.content }}
          </div>
          <div class="flex-grow h-px bg-slate-800/50"></div>
        </div>
      </template>
    </div>

    <!-- Input bar -->
    <div class="border-t border-slate-800 bg-slate-950 p-4 shrink-0">
      <div class="flex items-center gap-2">
        <!-- Text Input Wrapper -->
        <div class="relative flex-grow">
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
            class="w-full bg-slate-900 border border-slate-800 focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 rounded-xl py-3.5 pl-11 pr-4 text-slate-200 placeholder-slate-600 outline-none transition-all disabled:opacity-50"
            @keydown="handleKeydown"
          />

          <!-- Command Popup -->
          <CommandPopup 
            v-if="showCommandPopup && filteredCommands.length > 0"
            :query="inputText"
            :active-index="commandPopupIndex"
            @select="selectCommand"
            @close="showCommandPopup = false"
            @update:active-index="val => commandPopupIndex = val"
          />
        </div>

        <!-- Send Button (Primary Action) -->
        <button
          :disabled="!isConnected || !inputText.trim()"
          class="w-12 h-12 shrink-0 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white disabled:bg-slate-800 disabled:text-slate-600 transition-colors shadow-lg active:scale-95 flex items-center justify-center mr-4"
          title="Send Command"
          @click="handleSend"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
          </svg>
        </button>

        <!-- Tool Buttons -->
        <button
          class="shrink-0 p-2 transition-all active:scale-90 group flex items-center justify-center hover:-translate-y-1"
          :class="{ 'glow-quest': props.questGlow }"
          title="Quest Log"
          @click="emit('openQuests')"
        >
          <img src="@/assets/svg/fantasy-spellbook.svg" class="h-14 w-14 invert brightness-200 contrast-75 group-hover:drop-shadow-[0_0_20px_rgba(124,58,237,0.8)] transition-all" />
        </button>

        <button
          class="shrink-0 p-2 transition-all active:scale-90 group flex items-center justify-center hover:-translate-y-1"
          :class="{ 'glow-inventory': props.inventoryGlow }"
          title="Character Sheet"
          @click="emit('openSheet')"
        >
          <img src="@/assets/svg/warrior-upper-body-bust-silhouette.svg" class="h-14 w-14 invert brightness-200 contrast-75 group-hover:drop-shadow-[0_0_20px_rgba(129,140,248,0.8)] transition-all" />
        </button>

        <button
          class="shrink-0 p-2 transition-all active:scale-90 group flex items-center justify-center hover:-translate-y-1"
          :class="{ 'glow-map': props.mapGlow }"
          title="World Map"
          @click="emit('openMap')"
        >
          <img src="@/assets/svg/fantasy-rpg-map.svg" class="h-14 w-14 brightness-110 group-hover:brightness-125 group-hover:drop-shadow-[0_0_20px_rgba(251,191,36,0.8)] transition-all" />
        </button>
      </div>
      
      <div class="flex gap-4 mt-3 px-1 text-xs text-slate-500">
        <span><kbd class="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400">/sheet</kbd> to view character</span>
        <span><kbd class="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400">/equip</kbd> to equip</span>
        <span><kbd class="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400">/hint</kbd> 50 XP</span>
        <span><kbd class="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400">/walkthrough</kbd> reveal 200 XP</span>
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

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.15);
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

/* Glow animations */
@keyframes tool-glow-inventory {
  0%, 100% { filter: drop-shadow(0 0 0px rgba(129, 140, 248, 0)); }
  50% { filter: drop-shadow(0 0 25px rgba(129, 140, 248, 0.9)); transform: scale(1.1); }
}
@keyframes tool-glow-map {
  0%, 100% { filter: drop-shadow(0 0 0px rgba(251, 191, 36, 0)); }
  50% { filter: drop-shadow(0 0 25px rgba(251, 191, 36, 0.9)); transform: scale(1.1); }
}
@keyframes tool-glow-quest {
  0%, 100% { filter: drop-shadow(0 0 0px rgba(124, 58, 237, 0)); }
  50% { filter: drop-shadow(0 0 25px rgba(124, 58, 237, 0.9)); transform: scale(1.1); }
}

.glow-inventory { animation: tool-glow-inventory 1s ease-in-out infinite; }
.glow-map { animation: tool-glow-map 1s ease-in-out infinite; }
.glow-quest { animation: tool-glow-quest 1s ease-in-out infinite; }
</style>

