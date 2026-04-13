<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

interface Adventure {
  game_id: string
  adventure_id: string
  avatar_id: string
  scene_id: string
  in_game_time: number
  is_paused: boolean
}

const adventures = ref<Adventure[]>([])
const isLoading = ref(true)

const fetchAdventures = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/v1/adventures')
    if (res.ok) {
      adventures.value = await res.json()
    } else {
      console.error('Failed to fetch adventures')
    }
  } catch (error) {
    console.error('API Error:', error)
  } finally {
    isLoading.value = false
  }
}

const deleteAdventure = async (adventureId: string) => {
  if (confirm('Are you sure you want to delete this adventure? This action cannot be undone.')) {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/adventures/${adventureId}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        // Remove from local state to avoid full reload
        adventures.value = adventures.value.filter(a => a.adventure_id !== adventureId)
      } else {
        console.error('Failed to delete adventure')
      }
    } catch (error) {
      console.error('Error deleting adventure:', error)
    }
  }
}

const playAdventure = (gameId: string) => {
  router.push({ name: 'game', params: { id: gameId } })
}

const createNewAdventure = () => {
  router.push({ name: 'character-create' })
}

const goToAdmin = () => {
  router.push({ name: 'admin' })
}

onMounted(() => {
  fetchAdventures()
})
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 font-sans p-8 flex flex-col items-center">
    <header class="w-full max-w-6xl mb-12 flex justify-between items-center px-4">
      <h1 class="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-cyan-500 shadow-sm">
        TaleWeaver
      </h1>
      <button 
        @click="goToAdmin" 
        class="group flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 hover:border-white/20 transition-all duration-300"
      >
        <span class="text-sm font-medium">Settings</span>
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-emerald-400 group-hover:rotate-45 transition-transform duration-300" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clip-rule="evenodd" />
        </svg>
      </button>
    </header>

    <main class="w-full max-w-6xl flex-grow px-4">
      <div v-if="isLoading" class="flex justify-center items-center h-64">
        <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500"></div>
      </div>

      <div v-else-if="adventures.length === 0" class="text-center py-20 bg-white/5 rounded-3xl border border-white/10 backdrop-blur-md">
        <h2 class="text-2xl font-bold text-white mb-2">No active adventures</h2>
        <p class="text-slate-400 mb-8 max-w-md mx-auto">It appears your library is empty. Spin a new tale and embark on your first journey.</p>
        <button 
          @click="createNewAdventure"
          class="px-8 py-3 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white font-bold rounded-xl shadow-lg hover:shadow-emerald-500/25 transition-all duration-300 transform hover:-translate-y-1"
        >
          Begin New Adventure
        </button>
      </div>

      <div v-else>
        <div class="flex justify-between items-end mb-8">
          <div>
            <h2 class="text-2xl font-bold text-white">Your Journeys</h2>
            <p class="text-slate-400 text-sm mt-1">Continue where you left off</p>
          </div>
          <button 
            @click="createNewAdventure"
            class="px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white font-semibold rounded-lg shadow-md hover:shadow-emerald-500/25 transition-all duration-300 transform hover:-translate-y-0.5 flex items-center gap-2"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
            </svg>
            New Adventure
          </button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div 
            v-for="adv in adventures" 
            :key="adv.game_id" 
            class="group relative bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden hover:border-emerald-500/50 transition-all duration-500 hover:shadow-[0_8px_30px_rgb(16,185,129,0.12)] flex flex-col"
          >
            <!-- Card visual header -->
            <div class="h-32 bg-gradient-to-br from-slate-800 to-slate-950 relative overflow-hidden">
              <div class="absolute inset-0 opacity-20 group-hover:opacity-40 transition-opacity duration-700 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMSIgY3k9IjEiIHI9IjEiIGZpbGw9InJnYmEoMjU1LDI1NSwyNTUsMC4xKSIvPjwvc3ZnPg==')]"></div>
              
              <div class="absolute top-4 right-4">
                <button 
                  @click.stop="deleteAdventure(adv.adventure_id)" 
                  class="p-2 backdrop-blur-md bg-black/40 hover:bg-red-500/80 text-white/70 hover:text-white rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-300"
                  title="Abandon Journey"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
            
            <!-- Card body -->
            <div class="p-6 flex-grow flex flex-col">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-mono text-emerald-400">SESSION: {{ adv.game_id.substring(0,8) }}</span>
                <span class="text-xs px-2 py-1 bg-slate-800 rounded-full text-slate-400">{{ adv.is_paused ? 'PAUSED' : 'ACTIVE' }}</span>
              </div>
              <h3 class="text-xl font-bold text-white mb-4 line-clamp-2">{{ adv.adventure_id }}</h3>
              
              <div class="mt-auto space-y-3">
                <div class="flex justify-between text-sm">
                  <span class="text-slate-400">Current Scene</span>
                  <span class="text-slate-200 font-medium truncate max-w-[120px]">{{ adv.scene_id }}</span>
                </div>
                <div class="flex justify-between text-sm">
                  <span class="text-slate-400">In-game Time</span>
                  <span class="text-slate-200 font-medium">{{ adv.in_game_time }} turns</span>
                </div>
              </div>

              <!-- Action -->
              <button 
                @click="playAdventure(adv.game_id)" 
                class="mt-6 w-full py-3 bg-white/5 hover:bg-emerald-500/20 text-white font-medium rounded-xl border border-white/10 hover:border-emerald-500/50 transition-all duration-300"
              >
                Enter Realm
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
    
    <footer class="mt-12 w-full max-w-6xl text-center text-slate-500 text-sm">
      <p>Powered by the TaleWeaver Engine</p>
    </footer>
  </div>
</template>
