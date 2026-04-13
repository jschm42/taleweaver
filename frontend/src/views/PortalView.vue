<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import EditAdventureModal from '@/components/EditAdventureModal.vue'

const router = useRouter()

interface Adventure {
  game_id: string
  adventure_id: string
  avatar_id: string
  adventure_title: string
  image_url: string | null
  scene_id: string
  in_game_time: number
  is_paused: boolean
}

// For the active adventures list
const adventures = ref<Adventure[]>([])
const isLoading = ref(true)

// Modals
const showModal = ref(false)
const showEditModal = ref(false)
const selectedAdventureId = ref<string | null>(null)
const isSubmitting = ref(false)
const errorMsg = ref('')
const creationStatus = ref('')

// Adventure form
const form = ref({
  title: '',
  context: '',
  character_id: '',
  image_url: '' as string | null,
  generate_npc_images: false,
  generate_item_images: false
})

// Characters available to pick
interface Character {
  id: string
  name: string
  profile_image: string | null
}
const availableCharacters = ref<Character[]>([])

const fetchAdventures = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/adventures')
    if (res.ok) {
      adventures.value = await res.json()
    }
  } catch (error) {
    console.error('API Error:', error)
  } finally {
    isLoading.value = false
  }
}

const fetchCharacters = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/characters')
    if (res.ok) {
      availableCharacters.value = await res.json()
      // Default selection if only one character exists
      if (availableCharacters.value.length === 1 && !form.value.character_id) {
        form.value.character_id = availableCharacters.value[0].id
      }
    }
  } catch (error) {
    console.error('Characters API Error:', error)
  }
}

const deleteAdventure = async (adventureId: string) => {
  if (confirm('Are you sure you want to delete this adventure? This action cannot be undone.')) {
    try {
      const res = await fetch(`http://localhost:8000/api/adventures/${adventureId}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        adventures.value = adventures.value.filter(a => a.adventure_id !== adventureId)
      }
    } catch (error) {
      console.error('Error deleting adventure:', error)
    }
  }
}

const playAdventure = (gameId: string) => {
  router.push({ name: 'game', params: { id: gameId } })
}

const openNewAdventureModal = () => {
  form.value = { title: '', context: '', character_id: '', image_url: null }
  errorMsg.value = ''
  showModal.value = true
}

const openEditModal = (adventureId: string) => {
  selectedAdventureId.value = adventureId
  showEditModal.value = true
}

const handleAdventureUpdate = () => {
  fetchAdventures()
}

const handleImageUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return

  const file = target.files[0]
  const formData = new FormData()
  formData.append('file', file)

  try {
    errorMsg.value = ''
    const res = await fetch(`http://localhost:8000/api/data/image?type=adventure`, {
      method: 'POST',
      body: formData
    })

    if (res.ok) {
      const data = await res.json()
      form.value.image_url = data.url
    } else {
      errorMsg.value = 'Failed to upload adventure image. Max dimensions 512x512.'
    }
  } catch (err) {
    errorMsg.value = 'Network error uploading image.'
  }
}

async function createAdventure() {
  if (!form.value.title || !form.value.character_id) {
    errorMsg.value = "Character and Title are required."
    return
  }

  isSubmitting.value = true
  errorMsg.value = ''
  creationStatus.value = 'Initializing...'

  try {
    const res = await fetch('http://localhost:8000/api/adventures', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: crypto.randomUUID(),
        title: form.value.title,
        character_id: form.value.character_id,
        context: form.value.context,
        image_url: form.value.image_url,
        strict_rules: true,
        generate_npc_images: form.value.generate_npc_images,
        generate_item_images: form.value.generate_item_images,
        heartbeat_enabled: false
      })
    })

    if (!res.ok) throw new Error('Failed to start creation. Please check settings.')
    
    const data = await res.json()
    const adventureId = data.adventure_id
    
    // Start polling
    pollAdventureStatus(adventureId)
  } catch (err: any) {
    errorMsg.value = err.message || "Network connection failed."
    isSubmitting.value = false
  }
}

function pollAdventureStatus(id: string) {
  const pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`http://localhost:8000/api/adventures/${id}/status`)
      if (!res.ok) {
        clearInterval(pollInterval)
        errorMsg.value = "Engine failure: Generation stopped and session was cleaned up. Please try a different theme."
        isSubmitting.value = false
        return
      }

      const data = await res.json()
      creationStatus.value = data.status || "Constructing world..."

      if (data.is_ready) {
        clearInterval(pollInterval)
        router.push({ name: 'game', params: { id: id } })
      }
    } catch (err) {
      clearInterval(pollInterval)
      errorMsg.value = "Lost connection to the weaver's loom."
      isSubmitting.value = false
    }
  }, 1500)
}

const goToCharacters = () => {
  router.push({ name: 'characters' })
}

const goToAdmin = () => {
  router.push({ name: 'admin' })
}

onMounted(() => {
  fetchAdventures()
  fetchCharacters()
})
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 font-sans p-8 flex flex-col items-center">
    
    <!-- HEADER -->
    <header class="w-full max-w-6xl mb-12 flex justify-between items-center px-4">
      <h1 class="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-cyan-500 shadow-sm">
        TaleWeaver
      </h1>
      <div class="flex items-center gap-4">
        <button 
          @click="goToCharacters" 
          class="group flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 hover:border-emerald-500/50 transition-all duration-300"
        >
          <span class="text-sm font-medium">Characters</span>
          <i class="ra ra-helmet text-emerald-400"></i>
        </button>
        <button 
          @click="goToAdmin" 
          class="group flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 transition-all duration-300"
        >
          <span class="text-sm font-medium">Settings</span>
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-emerald-400 group-hover:rotate-45 transition-transform duration-300" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
    </header>

    <!-- CONTENT -->
    <main class="w-full max-w-6xl flex-grow px-4 relative">
      <div v-if="isLoading" class="flex justify-center items-center h-64">
        <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500"></div>
      </div>

      <div v-else-if="adventures.length === 0" class="text-center py-20 bg-white/5 rounded-3xl border border-white/10 backdrop-blur-md">
        <h2 class="text-2xl font-bold text-white mb-2">No active adventures</h2>
        <p class="text-slate-400 mb-8 max-w-md mx-auto">It appears your library is empty. Spin a new tale and embark on your first journey.</p>
        <button 
          @click="openNewAdventureModal"
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
            @click="openNewAdventureModal"
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
            <div class="h-32 bg-slate-800 relative overflow-hidden flex items-center justify-center">
               <template v-if="adv.image_url"> 
                 <img :src="'http://localhost:8000' + adv.image_url" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" />
               </template>
               <template v-else>
                 <i class="ra ra-scroll-unfurled text-6xl text-slate-700 opacity-50 group-hover:opacity-100 transition-opacity"></i>
               </template>
            </div>
            
            <div class="p-6 flex-grow flex flex-col">
              <div class="flex items-center justify-between mb-4">
                <span class="text-xs font-mono text-emerald-500/80 bg-emerald-500/5 px-2 py-1 rounded">SESSION: {{ adv.game_id.substring(0,8) }}</span>
                <span class="text-[10px] px-2 py-1 bg-slate-800 rounded uppercase text-slate-500 tracking-wider font-bold">{{ adv.is_paused ? 'PAUSED' : 'ACTIVE' }}</span>
              </div>
              
              <h3 class="text-xl font-bold text-white mb-2 line-clamp-1 hover:text-emerald-400 transition-colors cursor-pointer" @click="playAdventure(adv.game_id)">
                {{ adv.adventure_title }}
              </h3>
              
              <div class="flex-grow space-y-3 mt-2">
                <div class="flex justify-between text-[11px] pb-2 border-b border-white/5">
                  <span class="text-slate-500 uppercase tracking-widest font-semibold">Location</span>
                  <span class="text-slate-300 font-mono">{{ adv.scene_id }}</span>
                </div>
              </div>

              <!-- Action Footer -->
              <div class="mt-6 flex gap-2">
                <button 
                  @click="playAdventure(adv.game_id)" 
                  class="flex-grow py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl shadow-lg shadow-emerald-900/20 transition-all duration-300 flex items-center justify-center gap-2"
                >
                  <i class="ra ra-gear-hammer text-lg"></i>
                  Play
                </button>
                <button 
                  @click="openEditModal(adv.adventure_id)" 
                  class="px-4 py-3 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-xl border border-slate-700 transition-all duration-300 flex items-center justify-center gap-2"
                  title="Configure Adventure"
                >
                  <i class="ra ra-gear text-lg"></i>
                  <span class="hidden lg:inline text-xs font-bold uppercase tracking-tight">Edit</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- NEW ADVENTURE MODAL -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center pt-10">
      <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="showModal = false"></div>
      
      <div class="bg-slate-900 border border-slate-700 rounded-3xl w-full max-w-2xl max-h-[90vh] overflow-y-auto relative z-10 shadow-2xl p-8 flex flex-col animate-fade-in-up">
        
        <button @click="showModal = false" class="absolute top-6 right-6 text-slate-500 hover:text-white transition-colors">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <h2 class="text-3xl font-extrabold text-white mb-2">Create New Adventure</h2>
        <p class="text-slate-400 mb-8 text-base">Define the world and choose who will explore it.</p>

        <div class="space-y-5">
           
          <!-- Title -->
          <div>
            <label class="block text-base font-semibold text-slate-300 mb-2">Adventure Chronicle Title *</label>
            <input 
              v-model="form.title" 
              type="text" 
              maxlength="50"
              placeholder="e.g. The Curse of Blackwood" 
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all"
            />
          </div>

          <!-- Character Select -->
          <div>
            <label class="block text-base font-semibold text-slate-300 mb-2">Select your Champion *</label>
            <div v-if="availableCharacters.length === 0" class="text-amber-500 bg-amber-500/10 p-3 rounded-xl border border-amber-500/20 text-sm">
               You need to create a character first before starting an adventure. 
               <a href="#" @click.prevent="goToCharacters" class="underline font-bold">Go to Characters</a>
            </div>
            <div v-else class="grid grid-cols-2 gap-3 max-h-48 overflow-y-auto pr-2 custom-scrollbar">
               <button 
                  v-for="char in availableCharacters" 
                  :key="char.id"
                  @click="form.character_id = char.id"
                  :class="[
                    'flex items-center gap-4 p-4 rounded-xl border-2 text-left transition-all duration-300',
                    form.character_id === char.id 
                      ? 'bg-emerald-500/10 border-emerald-500 ring-4 ring-emerald-500/20 text-white' 
                      : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-emerald-500/50 hover:bg-slate-900'
                  ]"
               >
                 <div class="w-12 h-12 rounded-lg bg-slate-800 overflow-hidden flex items-center justify-center border border-white/10 shrink-0">
                    <img v-if="char.profile_image" :src="'http://localhost:8000' + char.profile_image" class="w-full h-full object-cover"/>
                    <i v-else class="ra ra-player text-2xl text-slate-500"></i>
                 </div>
                 <div class="truncate font-bold text-lg">{{ char.name }}</div>
               </button>
            </div>
          </div>

          <!-- Story Idea -->
          <div>
            <label class="block text-base font-semibold text-slate-300 mb-2">Story Idea / Context</label>
            <textarea 
              v-model="form.context" 
              rows="4"
              placeholder="Describe the setting or specific plot you have in mind..." 
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all resize-none"
            ></textarea>
          </div>

          <!-- Adventure Cover Image -->
          <div>
            <label class="block text-base font-semibold text-slate-300 mb-2">Adventure Cover Image</label>
            <div class="relative w-full h-32 rounded-xl border-2 border-dashed border-slate-700 bg-slate-950/50 flex items-center justify-center hover:border-emerald-500/50 transition-colors overflow-hidden group cursor-pointer">
              <template v-if="form.image_url">
                <img :src="'http://localhost:8000' + form.image_url" class="absolute inset-0 w-full h-full object-cover">
              </template>
              <div class="relative z-10 flex flex-col items-center">
                 <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-slate-400 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                 </svg>
                 <span class="text-xs text-slate-400 font-medium">Click to upload (max 512x512)</span>
              </div>
              <input type="file" @change="handleImageUpload" accept="image/png, image/jpeg, image/webp" class="absolute inset-0 opacity-0 cursor-pointer z-20">
            </div>
          </div>

          <!-- AI Generation Options -->
          <div class="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-4">
            <h3 class="text-xs font-bold text-slate-500 uppercase tracking-widest px-1">Engine Auxiliaries</h3>
            
            <div class="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5 hover:bg-white/10 transition-all cursor-pointer" @click="form.generate_npc_images = !form.generate_npc_images">
              <div class="flex flex-col">
                <span class="text-sm font-bold text-white">Envision NPCs</span>
                <span class="text-[10px] text-slate-400">Generate unique portraits for all inhabitants.</span>
              </div>
              <div :class="['w-10 h-6 rounded-full relative transition-colors duration-300', form.generate_npc_images ? 'bg-emerald-500' : 'bg-slate-800']">
                <div :class="['absolute top-1 w-4 h-4 bg-white rounded-full transition-all duration-300', form.generate_npc_images ? 'left-5' : 'left-1']"></div>
              </div>
            </div>

            <div class="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5 hover:bg-white/10 transition-all cursor-pointer" @click="form.generate_item_images = !form.generate_item_images">
              <div class="flex flex-col">
                <span class="text-sm font-bold text-white">Envision Items</span>
                <span class="text-[10px] text-slate-400">Generate visuals for key objects and loot.</span>
              </div>
              <div :class="['w-10 h-6 rounded-full relative transition-colors duration-300', form.generate_item_images ? 'bg-emerald-500' : 'bg-slate-800']">
                <div :class="['absolute top-1 w-4 h-4 bg-white rounded-full transition-all duration-300', form.generate_item_images ? 'left-5' : 'left-1']"></div>
              </div>
            </div>
          </div>

          <div v-if="errorMsg" class="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-lg">
             {{ errorMsg }}
          </div>

        </div>

        <div class="mt-8 flex justify-end gap-4">
           <button 
             @click="showModal = false"
             class="px-6 py-2.5 rounded-xl border border-slate-700 text-slate-300 hover:bg-slate-800 transition-colors"
           >
             Cancel
           </button>
           <button 
             @click="createAdventure"
             :disabled="isSubmitting || !form.title || !form.character_id"
             class="px-8 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-bold rounded-xl shadow-lg transition-all flex items-center gap-2 disabled:opacity-50"
           >
             <span v-if="isSubmitting" class="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin"></span>
             {{ isSubmitting ? (creationStatus || 'Creating...') : 'Forge Adventure' }}
           </button>
        </div>

      </div>
    </div>

    <!-- EDIT ADVENTURE MODAL -->
    <EditAdventureModal 
      :open="showEditModal" 
      :adventure-id="selectedAdventureId"
      @close="showEditModal = false"
      @updated="handleAdventureUpdate"
    />

  </div>
</template>

<style scoped>
.animate-fade-in-up {
  animation: fadeInUp 0.3s ease-out;
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(10px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(0,0,0,0.2); 
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(16, 185, 129, 0.3); 
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(16, 185, 129, 0.5); 
}
</style>
