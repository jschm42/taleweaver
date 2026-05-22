<script setup lang="ts">
import { ref, watch, nextTick, computed, onMounted, onUnmounted } from 'vue'
import { configState } from '@/store/config'
import BableFishSelector from '@/components/game/BableFishSelector.vue'
import type { ChatMessage } from '@/types'
import CommandPopup from '@/components/game/CommandPopup.vue'
import GameActionBar from '@/components/game/GameActionBar.vue'
import { useGameSocket, type ConnectionStatus } from '@/composables/useGameSocket'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'
import { audioService } from '@/services/audioService'

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
  activeActionId?: string | null
  mode?: string
  inputLocked?: boolean
  sheet?: any
  gameId?: string
  currentSceneDescription?: string
}>()

const { deleteMessage, agentPaused, agentStepByStep, runAgentTurn } = useGameSocket()

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
  npcContextmenu: [entity: any, event: MouseEvent]
  itemContextmenu: [entity: any, event: MouseEvent]
  selectAction: [actionId: string | null]
  npcClick: [name: string]
  itemClick: [item: any]
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
  { id: '/rule-pass', label: '/rule-pass (Force Rule Check)' },
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
  
  const debugEnabled = !!props.sheet?.debug_mode
  let list = commands
  if (!debugEnabled) {
    list = list.filter(c => !c.id.startsWith('/debug'))
  }
  
  if (!q) return list
  return list.filter(c => c.label.toLowerCase().includes(q))
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

const visibleStart = ref(0)
const visibleEnd = ref(0)
const isShifting = ref(false)

const visibleMessages = computed(() => {
  return props.messages.slice(visibleStart.value, visibleEnd.value)
})

const handleScroll = () => {
  if (!logEl.value || isShifting.value) return
  const el = logEl.value
  const scrollTop = el.scrollTop
  const scrollHeight = el.scrollHeight
  const clientHeight = el.clientHeight

  const WINDOW_SIZE = 50
  const total = props.messages.length

  if (total <= WINDOW_SIZE) return

  // Scroll up: if near the top and there are older messages not visible
  if (scrollTop < 100 && visibleStart.value > 0) {
    const K = visibleStart.value
    const anchorEl = el.querySelector(`[data-index="${K}"]`) as HTMLElement
    if (anchorEl) {
      const anchorOffsetBefore = anchorEl.offsetTop
      
      // Shift window up
      const shift = Math.min(15, visibleStart.value)
      isShifting.value = true
      visibleStart.value -= shift
      visibleEnd.value -= shift

      nextTick(() => {
        const anchorElAfter = el.querySelector(`[data-index="${K}"]`) as HTMLElement
        if (anchorElAfter) {
          const anchorOffsetAfter = anchorElAfter.offsetTop
          el.scrollTop = scrollTop + (anchorOffsetAfter - anchorOffsetBefore)
        }
        isShifting.value = false
      })
    }
  }

  // Scroll down: if near the bottom and there are newer messages not visible
  if (scrollHeight - scrollTop - clientHeight < 150 && visibleEnd.value < total) {
    const shift = Math.min(15, total - visibleEnd.value)
    const K = visibleStart.value + shift
    const anchorEl = el.querySelector(`[data-index="${K}"]`) as HTMLElement
    if (anchorEl) {
      const anchorOffsetBefore = anchorEl.offsetTop
      
      // Shift window down
      isShifting.value = true
      visibleStart.value += shift
      visibleEnd.value += shift

      nextTick(() => {
        const anchorElAfter = el.querySelector(`[data-index="${K}"]`) as HTMLElement
        if (anchorElAfter) {
          const anchorOffsetAfter = anchorElAfter.offsetTop
          el.scrollTop = scrollTop + (anchorOffsetAfter - anchorOffsetBefore)
        }
        isShifting.value = false
      })
    }
  }
}

watch(
  () => props.messages,
  async (newMsgs, oldMsgs) => {
    const total = newMsgs ? newMsgs.length : 0
    const WINDOW_SIZE = 50
    let wasAtEnd = true

    if (total <= WINDOW_SIZE) {
      visibleStart.value = 0
      visibleEnd.value = total
    } else {
      wasAtEnd = !oldMsgs || visibleEnd.value >= oldMsgs.length
      if (wasAtEnd) {
        visibleEnd.value = total
        visibleStart.value = Math.max(0, total - WINDOW_SIZE)
      } else {
        if (visibleEnd.value > total) {
          visibleEnd.value = total
        }
        if (visibleStart.value >= visibleEnd.value) {
          visibleStart.value = Math.max(0, visibleEnd.value - WINDOW_SIZE)
        }
      }
    }

    await nextTick()
    if (logEl.value && wasAtEnd) {
      logEl.value.scrollTop = logEl.value.scrollHeight
    }
  },
  { deep: true, immediate: true }
)

onMounted(async () => {
  await nextTick()
  if (logEl.value) {
    logEl.value.scrollTop = logEl.value.scrollHeight
  }
})

const canSendInput = computed(() => (props.status === 'connected' || props.status === 'completed') && !props.inputLocked)
const isPassRunning = computed(() => props.status === 'connecting' || props.status === 'loading')
const messageTypographyClass = computed(() => {
  if (fontSize.value === 'small') return 'text-xs'
  if (fontSize.value === 'large') return 'text-lg md:text-xl'
  return 'text-sm md:text-base'
})

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
  if (!canSendInput.value) return
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

  // Verbal Speech Shortcut (Tab)
  if (e.key === 'Tab') {
    e.preventDefault()
    if (!inputText.value.startsWith('/say ')) {
      inputText.value = '/say ' + inputText.value
    }
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
  const resolveNpcMetadata = (rawName: string): { key: string; data: any } | null => {
    const normalized = String(rawName || '').trim().replace(/^\*\*|\*\*$/g, '')
    if (!normalized) return null

    const exact = props.npcMetadata[normalized]
    if (exact) return { key: normalized, data: exact }

    const lowered = normalized.toLowerCase()
    for (const [key, value] of Object.entries(props.npcMetadata || {})) {
      if (String(key).toLowerCase() === lowered) {
        return { key, data: value }
      }
      // Fallback: search by name property within the metadata object
      if (value && typeof value === 'object' && value.name && String(value.name).toLowerCase() === lowered) {
        return { key, data: value }
      }
    }

    return null
  }

  const renderNpcLabel = (rawName: string): string => {
    const displayName = String(rawName || '').trim().replace(/^\*\*|\*\*$/g, '')
    if (!displayName) return ''

    const resolved = resolveNpcMetadata(displayName)
    if (!resolved) {
      return `<strong class="text-amber-400 font-bold">${displayName}:</strong>`
    }

    const iconOrImg = resolved.data.image_url
      ? `<img src="${getImageUrl(resolved.data.image_url)}" class="npc-avatar" alt="${displayName}-portrait">`
      : `<div class="npc-avatar ra ra-player flex items-center justify-center bg-slate-800 text-amber-500/80 text-xl border-amber-500/30 font-normal"></div>`

    return `<span class="npc-portrait-trigger" data-npc-name="${resolved.key}">${iconOrImg}<strong class="npc-name">${displayName}:</strong></span>`
  }

  // Pattern: **Name:**
  return text
    .replace(/\*\*([^*:\n][^:\n]*?):\*\*/g, (_match, name) => renderNpcLabel(name))
    // Support plain dialogue labels after switching output format to Name: "..."
    .replace(/(^|\n)([^\n:<][^\n:]{0,120}):(?=\s|"|$)/g, (_match, prefix, name) => `${prefix}${renderNpcLabel(name)}`)
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
function handleClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  const npcWrapper = target.closest('[data-npc-name]')
  if (npcWrapper) {
    const name = npcWrapper.getAttribute('data-npc-name')
    if (name) {
      emit('npcClick', name)
      return
    }
  }
}
function handleContextMenu(e: MouseEvent) {
  const target = e.target as HTMLElement
  const npcWrapper = target.closest('[data-npc-name]')
  if (npcWrapper) {
    const name = npcWrapper.getAttribute('data-npc-name')
    if (name) {
      e.preventDefault()
      const metadata = props.npcMetadata[name]
      if (metadata) {
        emit('npcContextmenu', { ...metadata, entity_type: 'NPC' }, e)
      } else {
        emit('npcContextmenu', { name, entity_type: 'NPC' }, e)
      }
      return
    }
  }
}

function normalizeLineBreaks(text: string): string {
  // Keep intentional paragraph breaks, but cap excessive blank lines.
  return text.replace(/\n{3,}/g, '\n\n')
}

/** Escapes HTML special characters to prevent XSS in v-html interpolation. */
function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * Transforms GM voice-direction tags like [shouting] or [very fast] into
 * styled inline labels. Each tag's scope ends at the next paragraph break.
 * If a new [tag] begins on its own line without a preceding blank line,
 * a paragraph break is forced before it.
 */
function formatVoiceTags(text: string): string {
  // Force a paragraph break before any [tag] that starts a new line
  // but is not already preceded by a blank line.
  const withBreaks = text.replace(/(?<!\n)\n(?!\n)(\[[^\]\n]+\])/g, '\n\n$1')

  // Style any [tag] that is at the start of a line, segment, or follows a quote/colon
  // This allows tags inside dialogue like Architect: "[matter-of-fact] ..."
  return withBreaks.replace(/(\[[^\]\n]+\])/g, (match, tag, offset, fullText) => {
    const prevChar = offset > 0 ? fullText[offset - 1] : ''
    
    // Check if tag is "leading" in its context (start of string, whitespace, quotes, or colon)
    if (!prevChar || /[\s"':]/.test(prevChar)) {
      const label = escapeHtml(tag.slice(1, -1).trim())
      return `<span class="voice-tag-label">${label}</span>`
    }
    
    return match
  })
}

function fixNewlines(text: string | null | undefined): string {
  if (!text) return ''
  return text.replace(/\\n/g, '\n')
}

function displayMessageContent(msg: ChatMessage): string {
  let content = msg.content
  if (msg.role === 'system') {
    content = content
      .replace(/^\s*\[system\]\s*/i, '')
      .replace(/^\s*SYSTEM:\s*/i, '')
  }
  return fixNewlines(content)
}

/**
 * Colorizes stat names and their +/- modifiers in system messages to match
 * the character sheet's stat theme colors.
 */
function colorizeStatNames(text: string): string {
  const statColors: Record<string, string> = {
    'Strength':    'color: #f59e0b',  // amber
    'Dexterity':   'color: #06b6d4',  // cyan
    'Intelligence':'color: #8b5cf6',  // violet
    'Wisdom':      'color: #3b82f6',  // blue
    'Charisma':    'color: #ec4899',  // pink
    'Armor Class': 'color: #94a3b8',  // slate
    'HP':          'color: #e11d48',  // crimson/red
    'Stamina':     'color: #10b981',  // emerald/green
    'Mana':        'color: #2563eb',  // sapphire/blue
  }

  // Match patterns like "+5 Strength" or "-3 Dexterity" or just "Strength"
  for (const [stat, style] of Object.entries(statColors)) {
    // With numeric modifier: "+5 Strength" or "-3 Strength"
    const modifierPattern = new RegExp(`([+-]\\d+)\\s+(${stat})`, 'g')
    text = text.replace(modifierPattern, (_match, num: string, name: string) => {
      const numVal = parseInt(num)
      const numStyle = numVal > 0 ? 'color: #4ade80; font-weight: 700' : 'color: #f87171; font-weight: 700'
      return `<span style="${numStyle}">${num}</span> <span style="${style}; font-weight: 700">${name}</span>`
    })
  }

  return text
}

const lastUserMessage = computed(() => {
  const userMsgs = props.messages.filter(m => m.role === 'user')
  return userMsgs.length > 0 ? userMsgs[userMsgs.length - 1].content : null
})

function isRetryableError(content: string): boolean {
  const c = content.toLowerCase()
  return c.includes('temporarily unavailable') || 
         c.includes('busy right now') || 
         c.includes('took too long')
}

function handleRetry() {
  if (lastUserMessage.value) {
    emit('send', lastUserMessage.value)
  }
}


function handleGlobalKeydown(e: KeyboardEvent) {
  if (e.code !== 'Space' || !configState.isTtsEnabled) return
  if (e.repeat || e.ctrlKey || e.metaKey || e.altKey) return
  
  // Don't hijack space while typing
  const target = e.target as HTMLElement
  const isTyping = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable
  if (isTyping) return

  e.preventDefault()
  
  if (audioService.isPlaying.value) {
    audioService.stop()
  } else {
    // Find last assistant message to speak
    const assistantMsgs = props.messages.filter(m => m.role === 'assistant' && !(m as any).is_debug)
    if (assistantMsgs.length > 0) {
      const lastMsg = assistantMsgs[assistantMsgs.length - 1]
      audioService.unlock()
      audioService.speak(lastMsg.content, {
        sceneDescription: props.currentSceneDescription,
        adventureId: props.sheet?.template_id,
        sessionId: props.gameId,
        title: props.sheet?.adventure_title,
        sceneName: props.sheet?.current_scene,
        tone: props.sheet?.adventure_tone,
        npcMetadata: props.npcMetadata,
      })
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
})
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
      class="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-h-0 relative custom-scrollbar"
      aria-live="polite"
      aria-label="Game log"
      @mousemove="handleMouseMove"
      @mouseleave="emit('npcLeave')"
      @click="handleClick"
      @contextmenu="handleContextMenu"
      @scroll="handleScroll"
    >

      <div
        v-for="(msg, idx) in visibleMessages"
        :key="visibleStart + idx"
        :data-index="visibleStart + idx"
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
              msg.role === 'thought' ? 'bg-indigo-500/30 text-indigo-300 border border-indigo-500/50' :
              'bg-emerald-500/20 text-emerald-500'
            ]"
          >
            {{ (msg as any).is_debug ? 'Debug' : msg.role === 'user' ? 'You' : msg.role === 'assistant' ? 'Game Master' : msg.role === 'thought' ? 'Agent Thoughts' : 'System' }}
          </span>
          <span class="text-xs text-slate-600 font-mono opacity-0 group-hover:opacity-100 transition-opacity">
            {{ formatTime(msg.timestamp) }}
          </span>
          <span
            v-if="msg.role === 'assistant' && audioService.isGenerating.value && audioService.currentlyGeneratingContent.value === msg.content"
            class="inline-flex items-center gap-2 px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.2em] rounded-lg bg-amber-500/10 text-amber-300 border border-amber-500/30"
            title="Voice generation in progress"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>
            Generating
          </span>

          <!-- Manual Speak Button -->
          <button 
            v-if="msg.role === 'assistant' && configState.isTtsEnabled"
            @click="audioService.unlock(); audioService.speak(msg.content, {
              sceneDescription: props.currentSceneDescription,
              adventureId: props.sheet?.template_id,
              sessionId: props.gameId,
              title: props.sheet?.adventure_title,
              sceneName: props.sheet?.current_scene,
              tone: props.sheet?.adventure_tone,
              npcMetadata: props.npcMetadata,
            })"
            class="ml-auto p-1.5 px-3 text-[10px] font-black uppercase tracking-widest bg-slate-800/80 border border-slate-700/50 rounded-xl text-slate-400 hover:bg-amber-500/20 hover:text-amber-400 transition-all opacity-0 group-hover:opacity-100 flex items-center gap-2"
            title="Listen to this narration (SPACE)"
          >
            <i class="ra ra-microphone text-xs"></i>
            <span>Speak</span>
          </button>

          <!-- Download Button -->
          <button 
            v-if="msg.role === 'assistant' && configState.isTtsEnabled"
            @click="audioService.download(msg.content, {
              sceneDescription: props.currentSceneDescription,
              adventureId: props.sheet?.template_id,
              sessionId: props.gameId,
              title: props.sheet?.adventure_title,
              sceneName: props.sheet?.current_scene,
              tone: props.sheet?.adventure_tone,
              npcMetadata: props.npcMetadata,
            })"
            class="p-1.5 px-3 text-[10px] font-black uppercase tracking-widest bg-slate-800/80 border border-slate-700/50 rounded-xl text-slate-400 hover:bg-cyan-500/20 hover:text-cyan-400 transition-all opacity-0 group-hover:opacity-100 flex items-center gap-2"
            title="Download as WAV"
          >
            <i class="ra ra-download text-xs"></i>
            <span>WAV</span>
          </button>

          <!-- Delete Message Button (Debug Mode Only) -->
          <button 
            v-if="props.sheet?.debug_mode && (msg as any).id"
            @click="deleteMessage((msg as any).id)"
            class="p-1.5 px-3 text-[10px] font-black uppercase tracking-widest bg-slate-800/80 border border-slate-700/50 rounded-xl text-red-400 hover:bg-red-500/20 hover:text-red-300 transition-all opacity-0 group-hover:opacity-100 flex items-center gap-2"
            title="Delete this message (Debug)"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            <span>Delete</span>
          </button>
        </div>

        <!-- Content -->
        <div
          :class="[
            'leading-relaxed whitespace-pre-wrap break-words pl-4 border-l-2 transition-all relative',
            messageTypographyClass,
            msg.role === 'user' ? 'text-slate-300 border-cyan-500/50' :
            msg.role === 'assistant' ? 'text-amber-50/90 border-amber-500/50' :
            msg.role === 'thought' ? 'text-indigo-200/90 border-indigo-500/50 bg-indigo-950/20 py-2.5 px-4 rounded-r-lg italic font-medium' :
            'text-emerald-400 border-emerald-500/30 bg-emerald-500/5 py-2 px-4 rounded-r-lg italic font-medium'
          ]"
        >
          <template v-for="(part, pIdx) in parseContent(displayMessageContent(msg))" :key="pIdx">
            <span v-if="part.type === 'text'" v-html="msg.role === 'system' ? colorizeStatNames(formatBolds(formatVoiceTags(normalizeLineBreaks(part.value)))) : formatBolds(formatVoiceTags(normalizeLineBreaks(part.value)))"></span>
            <div v-else-if="part.type === 'image'" class="my-4 rounded-xl overflow-hidden border border-white/10 shadow-lg">
              <img :src="part.url" :alt="part.alt" class="w-full max-h-80 object-cover" />
              <div v-if="part.alt" class="px-3 py-1.5 bg-black/40 text-xxs text-slate-400 font-bold uppercase tracking-widest">{{ part.alt }}</div>
            </div>
            <pre v-else-if="part.type === 'code'" class="my-3 p-4 bg-slate-950 border border-slate-800 rounded-xl text-xs font-mono text-cyan-400 overflow-x-auto whitespace-pre custom-scrollbar shadow-inner">{{ part.value }}</pre>
          </template>

          <!-- Retry Button for Errors -->
          <div v-if="msg.role === 'system' && isRetryableError(msg.content) && lastUserMessage" class="mt-4 flex justify-start">
            <button 
              @click="handleRetry"
              class="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-black uppercase tracking-[0.2em] rounded-xl flex items-center gap-2.5 transition-all active:scale-95 shadow-lg shadow-emerald-500/20 border border-emerald-400/30 group"
            >
              <i class="ra ra-reload group-hover:rotate-180 transition-transform duration-500"></i>
              Retry Last Action
            </button>
          </div>
        </div>

        <!-- Discovery Cards (Items revealed this turn) -->
        <div v-if="msg.itemIds && msg.itemIds.length" class="mt-4 flex flex-wrap gap-4 pl-4">
          <div 
            v-for="itemId in msg.itemIds" 
            :key="itemId"
            v-show="entities.find(e => e.id === itemId)"
            class="item-card flex flex-col w-56 bg-slate-800/80 border border-slate-700/50 rounded-xl overflow-hidden shadow-xl backdrop-blur-sm transition-all hover:scale-[1.02] hover:border-emerald-500/30"
            :class="entities.find(e => e.id === itemId)?.is_portable !== false ? 'cursor-pointer' : 'cursor-help'"
            @click="emit('itemClick', entities.find(e => e.id === itemId))"
            @contextmenu.prevent="emit('itemContextmenu', entities.find(e => e.id === itemId), $event)"
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
      <div v-if="canSendInput && props.messages.length === 0" class="absolute inset-0 flex items-center justify-center text-slate-500 text-sm">
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

    <!-- AGENT ACTIVE BANNER -->
    <div
      v-if="props.sheet?.agent_active"
      class="mx-4 mb-2 px-4 py-3 rounded-xl border border-indigo-500/30 bg-indigo-500/10 text-indigo-200 text-xs font-semibold tracking-wide flex items-center justify-between gap-2 shadow-[0_0_15px_rgba(99,102,241,0.2)] shrink-0"
      :class="{ 'animate-pulse': !agentPaused }"
    >
      <div class="flex items-center gap-2">
        <div :class="['w-2.5 h-2.5 rounded-full', agentPaused ? 'bg-amber-400' : 'bg-indigo-400 animate-ping']"></div>
        <span>{{ agentPaused ? 'Autonomous Agent Mode is paused.' : 'Autonomous Agent Mode is active. The AI is playing the game.' }}</span>
      </div>
      <div class="flex items-center gap-2.5 select-none shrink-0">
        <!-- Step by Step Toggle -->
        <label class="flex items-center gap-1.5 cursor-pointer text-[10px] font-black uppercase tracking-wider text-indigo-300 hover:text-indigo-200">
          <input 
            type="checkbox" 
            v-model="agentStepByStep" 
            class="w-3.5 h-3.5 rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500/50 focus:ring-offset-slate-950 focus:ring-1" 
          />
          Step-by-Step
        </label>

        <!-- Next Step Button -->
        <button 
          v-if="agentStepByStep && !agentPaused"
          :disabled="props.status !== 'connected'"
          @click="runAgentTurn"
          class="px-3 py-1.5 bg-emerald-600/80 hover:bg-emerald-600 border border-emerald-500/50 hover:border-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-[10px] font-black uppercase tracking-[0.15em] transition-all transform active:scale-95 flex items-center gap-1.5 shadow-lg"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
          </svg>
          Next
        </button>

        <!-- Pause / Resume Button -->
        <button 
          @click="agentPaused = !agentPaused"
          class="px-3 py-1.5 bg-indigo-600/80 hover:bg-indigo-600 border border-indigo-500/50 hover:border-indigo-400 text-white rounded-lg text-[10px] font-black uppercase tracking-[0.15em] transition-all transform active:scale-95 flex items-center gap-1.5 shadow-lg"
        >
          <svg v-if="agentPaused" xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {{ agentPaused ? 'Resume' : 'Pause' }}
        </button>

        <!-- Stop Agent Button -->
        <button 
          @click="emit('send', '/agent off')"
          class="px-3 py-1.5 bg-red-600/80 hover:bg-red-600 border border-red-500/50 hover:border-red-400 text-white rounded-lg text-[10px] font-black uppercase tracking-[0.15em] transition-all transform active:scale-95 flex items-center gap-1.5 shadow-lg"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
          </svg>
          Stop
        </button>
      </div>
    </div>

    <!-- ACTION BAR -->
    <GameActionBar 
      :active-action-id="props.activeActionId" 
      :mode="props.mode"
      :disabled="!!props.inputLocked || isPassRunning"
      @select-action="emit('selectAction', $event)" 
    />

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
            :disabled="!canSendInput || audioService.isGenerating.value || props.sheet?.agent_active"
            :placeholder="props.sheet?.agent_active ? (agentPaused ? 'Agent Mode Paused. Click Resume or Stop.' : 'Agent Mode Active. Click Stop to regain control.') : 'What do you do next?'"
            class="w-full bg-slate-900 border border-slate-800 focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 rounded-xl py-3.5 pl-11 pr-4 text-slate-200 placeholder-slate-600 outline-none transition-all disabled:opacity-50"
            @keydown="handleKeydown"
          />

          <!-- Command Popup -->
          <CommandPopup 
            v-if="showCommandPopup && filteredCommands.length > 0"
            :query="inputText"
            :active-index="commandPopupIndex"
            :debug-mode="!!sheet?.debug_mode"
            @select="selectCommand"
            @close="showCommandPopup = false"
            @update:active-index="val => commandPopupIndex = val"
          />
        </div>

        <!-- Send Button (Primary Action) -->
        <button
          :disabled="!canSendInput || !inputText.trim()"
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

        <button
          class="shrink-0 p-2 transition-all active:scale-90 group flex items-center justify-center hover:-translate-y-1"
          title="Evaluate Rules & Quests"
          @click="emit('send', '/rule-pass')"
        >
          <div class="h-14 w-14 rounded-full bg-slate-800/40 border border-slate-700/50 flex items-center justify-center group-hover:border-emerald-500/50 transition-all shadow-xl backdrop-blur-md">
            <i class="ra ra-cog text-3xl text-slate-400 group-hover:text-emerald-400 group-hover:drop-shadow-[0_0_15px_rgba(16,185,129,0.8)] transition-all"></i>
          </div>
        </button>

      </div>
      
      <!-- Verbal Speech Hint -->
      <div class="mt-1 pl-11 flex items-center gap-1.5 opacity-60 hover:opacity-100 transition-opacity pointer-events-none select-none">
         <span class="text-[9px] uppercase tracking-widest text-slate-400 font-black">Shortcut</span>
         <kbd class="px-1.5 py-0.5 bg-slate-900 border border-slate-800 rounded text-[9px] text-emerald-400 font-mono shadow-2xl">TAB</kbd>
         <span class="text-[9px] uppercase tracking-widest text-slate-400 font-black">to insert /say (Verbal Speech)</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Target elements inside v-html */
:deep(.voice-tag-label) {
  font-style: italic;
  font-weight: 700;
  color: rgba(251, 191, 36, 0.65);
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-right: 0.15em;
}

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

