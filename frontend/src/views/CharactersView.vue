<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

interface Character {
  id: string
  name: string
  profile_image: string | null
}

const characters = ref<Character[]>([])
const isLoading = ref(true)
const importInput = ref<HTMLInputElement | null>(null)

const fetchCharacters = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/characters')
    if (res.ok) {
      characters.value = await res.json()
    }
  } catch (error) {
    console.error('API Error:', error)
  } finally {
    isLoading.value = false
  }
}

const deleteCharacter = async (charId: string) => {
  if (confirm('Are you sure you want to delete this character?')) {
    try {
      const res = await fetch(`http://localhost:8000/api/characters/${charId}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        characters.value = characters.value.filter(c => c.id !== charId)
      }
    } catch (error) {
      console.error('Error deleting character:', error)
    }
  }
}

const goToCreate = () => {
  router.push({ name: 'character-create' })
}

const importCharacter = async (event: Event) => {
  const target = event.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return
  
  const file = target.files[0]
  try {
    const text = await file.text()
    const payload = JSON.parse(text)
    
    // Validate it's likely a character
    if (!payload.name) {
      alert("Invalid character file.")
      return
    }
    
    const res = await fetch('http://localhost:8000/api/characters/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    
    if (res.ok) {
      await fetchCharacters()
      alert("Character imported successfully!")
    } else {
      alert("Failed to import character.")
    }
  } catch (err) {
    alert("Error reading character file.")
  } finally {
    target.value = ''
  }
}

const goToEdit = (id: string) => {
  router.push({ name: 'character-edit', params: { id } })
}

const goBack = () => {
  router.push({ name: 'portal' })
}

onMounted(() => {
  fetchCharacters()
})
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 font-sans p-8 flex flex-col items-center">
    <header class="w-full max-w-6xl mb-12 flex justify-between items-center px-4">
      <div class="flex items-center gap-4">
        <button 
          @click="goBack" 
          class="p-2 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
          </svg>
        </button>
        <h1 class="text-4xl font-extrabold tracking-tight text-white shadow-sm">
          Character Compendium
        </h1>
      </div>
      <button 
        @click="goToCreate"
        class="px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white font-semibold rounded-lg shadow-md hover:shadow-emerald-500/25 transition-all duration-300 flex items-center gap-2"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
        </svg>
        New Character
      </button>
      <div class="relative">
        <button 
          @click="importInput?.click()"
          class="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 transition-all flex items-center gap-2"
        >
          <i class="ra ra-save text-lg"></i>
          Import Blueprint
        </button>
        <input 
          type="file" 
          ref="importInput"
          class="hidden" 
          accept=".json"
          @change="importCharacter"
        />
      </div>
    </header>

    <main class="w-full max-w-6xl flex-grow px-4">
      <div v-if="isLoading" class="flex justify-center items-center h-64">
        <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500"></div>
      </div>

      <div v-else-if="characters.length === 0" class="text-center py-20 bg-white/5 rounded-3xl border border-white/10 backdrop-blur-md">
        <h2 class="text-2xl font-bold text-white mb-2">No characters found</h2>
        <p class="text-slate-400 mb-8 max-w-md mx-auto">Your roster is empty. Create a new hero to embark on journeys.</p>
        <button 
          @click="goToCreate"
          class="px-8 py-3 bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-bold rounded-xl shadow-lg hover:shadow-emerald-500/25 transition-all duration-300 transform hover:-translate-y-1"
        >
          Create Character
        </button>
      </div>

      <div v-else class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
        <div 
          v-for="char in characters" 
          :key="char.id" 
          class="group relative bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden hover:border-emerald-500/50 transition-all duration-300 shadow-lg flex flex-col"
        >
          <!-- Profile Banner / Image -->
          <div class="h-48 w-full bg-slate-800 flex items-center justify-center relative overflow-hidden bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMSIgY3k9IjEiIHI9IjEiIGZpbGw9InJnYmEoMjU1LDI1NSwyNTUsMC4wNSkiLz48L3N2Zz4=')]">
            <template v-if="char.profile_image">
              <img :src="'http://localhost:8000' + char.profile_image" alt="Profile" class="w-full h-full object-cover opacity-90 group-hover:opacity-100 transition-opacity" />
            </template>
            <template v-else>
              <i class="ra ra-player text-6xl text-slate-600 drop-shadow-md"></i>
            </template>
          </div>
          
          <div class="p-6 text-center flex-grow flex flex-col items-center">
            <h3 class="text-xl font-bold text-white truncate w-full">{{ char.name }}</h3>
            
            <div class="mt-auto pt-6 flex w-full gap-3">
              <button 
                @click="goToEdit(char.id)" 
                class="flex-1 py-2 bg-white/5 hover:bg-emerald-500/20 text-emerald-400 rounded-lg border border-white/5 hover:border-emerald-500/30 transition-colors"
                title="Edit Character"
              >
                Edit
              </button>
              <button 
                @click.stop="deleteCharacter(char.id)" 
                class="py-2 px-4 bg-white/5 hover:bg-red-500/20 text-red-400 rounded-lg border border-white/5 hover:border-red-500/30 transition-colors"
                title="Delete Character"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
