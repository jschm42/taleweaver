<script setup lang="ts">
/**
 * ImmersiveInputBar — Bottom player input area
 *
 * Includes text input, command auto-completion popup, push-to-talk voice recording,
 * TAB shortcut to insert /say, input history navigation, and send actions.
 */
import { ref, computed, watch, nextTick, toRef } from 'vue'
import CommandPopup from '@/components/game/CommandPopup.vue'
import { getFilteredCommands } from '@/utils/commands'
import { useVoiceInput } from '@/composables/useVoiceInput'
import { Mic, SendHorizontal, AlertTriangle, RotateCcw } from 'lucide-vue-next'

const props = defineProps<{
  canSendInput?: boolean
  isEvaluating?: boolean
  statusText?: string
  agentActive?: boolean
  debugMode?: boolean
  turnError?: { message: string; action: string } | null
}>()

const emit = defineEmits<{
  send: [content: string]
  retryTurn: []
  cancelTurnError: []
}>()

const inputText = ref('')
const inputEl = ref<HTMLInputElement | null>(null)
const history = ref<string[]>(JSON.parse(sessionStorage.getItem('tw_chat_history') || '[]'))
const historyIndex = ref(-1)

function addToHistory(text: string) {
  if (!text) return
  if (history.value[0] === text) return
  history.value.unshift(text)
  if (history.value.length > 20) history.value.pop()
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

function handleSend() {
  const trimmed = inputText.value.trim()
  if (!trimmed || !props.canSendInput) return
  addToHistory(trimmed)
  historyIndex.value = -1
  emit('send', trimmed)
  inputText.value = ''
}

// Prefill /say command when TAB key is pressed
function insertSayCommand() {
  if (!props.canSendInput) return
  if (!inputText.value.startsWith('/say ')) {
    inputText.value = '/say ' + inputText.value
  }
  void nextTick(() => {
    inputEl.value?.focus()
    const len = inputText.value.length
    inputEl.value?.setSelectionRange(len, len)
  })
}

// Command Autocompletion
const showCommandPopup = ref(false)
const commandPopupIndex = ref(0)

const filteredCommands = computed(() => {
  return getFilteredCommands(inputText.value, !!props.debugMode)
})

watch(inputText, (newVal) => {
  if (newVal.startsWith('/')) {
    showCommandPopup.value = true
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
  inputEl.value?.focus()
}

// Voice Recording Composable
const {
  isRecording,
  isTranscribing,
  handleMicButtonMousedown,
} = useVoiceInput({
  canSendInput: toRef(props, 'canSendInput'),
  inputText,
  onSend: handleSend,
})

function handleKeydown(e: KeyboardEvent) {
  // TAB key: Insert /say command
  if (e.key === 'Tab' || e.code === 'Tab' || e.keyCode === 9) {
    e.preventDefault()
    e.stopPropagation()
    if (props.canSendInput) {
      insertSayCommand()
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
      const sel = filteredCommands.value[commandPopupIndex.value]
      if (sel) selectCommand(sel.id)
      return
    }
    if (e.key === 'Escape') {
      showCommandPopup.value = false
      return
    }
  }

  if (e.key === 'ArrowUp') {
    e.preventDefault()
    navigateHistory('up')
    return
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    navigateHistory('down')
    return
  }
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (props.canSendInput) {
      handleSend()
    }
  }
}

defineExpose({
  setInputText: (text: string) => {
    inputText.value = text
    void nextTick(() => {
      inputEl.value?.focus()
      const pos = inputText.value.length
      inputEl.value?.setSelectionRange(pos, pos)
    })
  },
  appendText: (text: string) => {
    inputText.value = inputText.value ? `${inputText.value} ${text}` : text
    void nextTick(() => {
      inputEl.value?.focus()
      const pos = inputText.value.length
      inputEl.value?.setSelectionRange(pos, pos)
    })
  },
  toggleSayPrefix: () => {
    const current = inputText.value.trim()
    if (current.startsWith('/say ')) {
      inputText.value = current.slice(5)
    } else {
      inputText.value = '/say ' + inputText.value
    }
    void nextTick(() => {
      inputEl.value?.focus()
    })
  },
  insertSayCommand,
})
</script>

<template>
  <div class="p-3 sm:p-4">
    <!-- Turn Error / Retry Banner -->
    <div
      v-if="props.turnError"
      class="mb-2.5 p-3 rounded-2xl border border-red-500/50 bg-red-950/85 backdrop-blur-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs shadow-2xl animate-fade-in"
    >
      <div class="flex items-center gap-2.5 text-red-200 min-w-0">
        <div class="w-8 h-8 rounded-xl bg-red-500/20 border border-red-500/40 flex items-center justify-center shrink-0">
          <AlertTriangle class="w-4 h-4 text-red-400" />
        </div>
        <div class="flex flex-col min-w-0">
          <span class="font-black text-red-300 uppercase tracking-wider text-[10px]">Action Failed</span>
          <span class="truncate font-medium text-slate-200">{{ props.turnError.message }}</span>
        </div>
      </div>
      <div class="flex items-center gap-2 self-end sm:self-auto shrink-0">
        <button
          type="button"
          @click="emit('retryTurn')"
          class="px-3.5 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-black uppercase tracking-wider text-[11px] transition-all flex items-center gap-1.5 shadow-lg shadow-amber-500/20 active:scale-95 cursor-pointer"
          title="Retry this action"
        >
          <RotateCcw class="w-3.5 h-3.5" />
          Retry
        </button>
        <button
          type="button"
          @click="emit('cancelTurnError')"
          class="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white font-bold uppercase tracking-wider text-[11px] transition-all border border-white/10 active:scale-95 cursor-pointer"
          title="Cancel error and continue"
        >
          Cancel
        </button>
      </div>
    </div>

    <!-- Voice Recording Overlay -->
    <div
      v-if="isRecording || isTranscribing"
      class="mb-2 p-3 rounded-xl border flex items-center justify-between gap-3 text-xs font-bold shadow-lg animate-fade-in"
      :class="isRecording ? 'border-red-500/40 bg-red-950/60 text-red-200' : 'border-amber-500/40 bg-amber-950/60 text-amber-200'"
    >
      <div class="flex items-center gap-2">
        <span v-if="isRecording" class="w-2.5 h-2.5 rounded-full bg-red-500 animate-ping"></span>
        <span v-else class="w-2.5 h-2.5 rounded-full border-2 border-amber-400 border-t-transparent animate-spin"></span>
        <span>{{ isRecording ? 'PTT Active: Recording Voice...' : 'Transcribing Speech...' }}</span>
      </div>
      <span class="text-[10px] uppercase font-mono text-slate-400">
        {{ isRecording ? "Release key or mouse to finish" : "Please wait..." }}
      </span>
    </div>

    <!-- Input Box & Actions -->
    <div class="relative flex items-center gap-2">
      <!-- Command auto-completion popup -->
      <CommandPopup
        v-if="showCommandPopup && filteredCommands.length"
        :commands="filteredCommands"
        :active-index="commandPopupIndex"
        @select="selectCommand"
        @close="showCommandPopup = false"
        @update:active-index="val => commandPopupIndex = val"
      />

      <!-- Push-To-Talk Mic Button -->
      <button
        type="button"
        :disabled="!props.canSendInput"
        @mousedown="handleMicButtonMousedown"
        class="flex items-center justify-center w-11 h-11 rounded-xl bg-slate-900 border border-slate-700/80 hover:border-amber-400/60 hover:bg-amber-500/10 text-slate-300 hover:text-amber-300 transition-all shadow-md active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed shrink-0 cursor-pointer"
        title="Push-To-Talk (Hold to speak)"
      >
        <Mic class="w-5 h-5" :class="{ 'text-red-400 animate-pulse': isRecording }" />
      </button>

      <!-- Main Input Field -->
      <div class="relative flex-1">
        <input
          ref="inputEl"
          v-model="inputText"
          type="text"
          :disabled="!props.canSendInput"
          :placeholder="props.isEvaluating ? (props.statusText || 'GM is deciding...') : (props.agentActive ? 'AI Agent Mode is active.' : 'What do you do next? (TAB for /say, / for commands)')"
          class="w-full bg-slate-900/90 border-2 border-slate-700/70 focus:border-amber-400/80 focus:ring-2 focus:ring-amber-400/20 rounded-xl py-2.5 pl-4 pr-10 text-sm sm:text-base text-slate-100 placeholder-slate-500 outline-none transition-all disabled:opacity-50 font-medium"
          @keydown.tab.prevent.stop="insertSayCommand"
          @keydown="handleKeydown"
        />

        <!-- Send Button inside input -->
        <button
          type="button"
          :disabled="!props.canSendInput || !inputText.trim()"
          @click="handleSend"
          class="absolute right-1.5 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-md active:scale-90 cursor-pointer"
          title="Send Action (Enter)"
        >
          <SendHorizontal class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: comicPop 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes comicPop {
  0% {
    opacity: 0;
    transform: translateY(12px) scale(0.98);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
