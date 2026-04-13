<script setup lang="ts">
/**
 * GameView — The active adventure screen
 *
 * Connects to the given game session and displays the chat,
 * intercepting commands and showing the character sheet.
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ChatWindow from '@/components/ChatWindow.vue'
import CharacterSheetModal from '@/components/CharacterSheetModal.vue'
import { useGameSocket } from '@/composables/useGameSocket'

const props = defineProps<{
  id: string
}>()

const router = useRouter()
const showSheet = ref(false)

const {
  messages,
  sheet,
  status,
  gameOverReason,
  connect,
  disconnect,
  sendMessage,
} = useGameSocket()

const goBack = () => {
  disconnect()
  router.push({ name: 'portal' })
}

onMounted(() => {
  if (props.id) {
    connect(props.id)
  }
})

watch(() => props.id, (newId) => {
  disconnect()
  if (newId) {
    connect(newId)
  }
})

onBeforeUnmount(() => {
  disconnect()
})
</script>

<template>
  <main class="min-h-screen bg-slate-950 flex flex-col font-sans">
    <!-- Header Navigation -->
    <header class="bg-slate-900 border-b border-slate-800 px-6 py-4 flex justify-between items-center z-10 shrink-0">
      <div class="flex items-center gap-4">
        <button 
          @click="goBack" 
          class="p-2 rounded-full bg-slate-800 border border-slate-700 hover:bg-slate-700 transition-colors"
          title="Return to Portal"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-slate-300" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
          </svg>
        </button>
        <div>
          <h1 class="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-cyan-500">TaleWeaver Engine</h1>
          <p class="text-slate-500 text-xs mt-0.5">Session: {{ props.id.substring(0, 8) }}</p>
        </div>
      </div>
      
      <button
        class="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-slate-300 text-sm font-medium transition-colors"
        @click="showSheet = true"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-emerald-500" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clip-rule="evenodd" />
        </svg>
        Character Sheet
      </button>
    </header>

    <!-- Main Game Area -->
    <div class="flex-grow relative overflow-hidden flex flex-col items-center p-4 sm:p-6 w-full max-w-5xl mx-auto">
      <div v-if="gameOverReason" class="w-full bg-red-900/20 border border-red-500/30 p-4 rounded-xl mb-4 text-red-400 font-medium flex items-center gap-3 shadow-lg backdrop-blur-sm shrink-0">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <span>{{ gameOverReason }}</span>
      </div>

      <ChatWindow
        class="w-full flex-grow shadow-[0_8px_30px_rgb(0,0,0,0.5)] rounded-2xl border border-slate-800 bg-slate-900/80 backdrop-blur-xl overflow-hidden"
        :messages="messages"
        :status="status"
        @send="sendMessage"
        @open-sheet="showSheet = true"
      />
    </div>

    <!-- Modals -->
    <CharacterSheetModal :open="showSheet" :sheet="sheet" @close="showSheet = false" />
  </main>
</template>
