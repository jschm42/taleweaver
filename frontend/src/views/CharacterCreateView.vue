<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const archetypes = [
  { id: 'knight', name: 'Knight', description: 'Master of arms and armor, relying on physical prowess.', icon: '🛡️', color: 'from-slate-600 to-slate-800' },
  { id: 'mage', name: 'Mage', description: 'Wielder of arcane forces and elemental magic.', icon: '🔮', color: 'from-indigo-600 to-purple-800' },
  { id: 'rogue', name: 'Rogue', description: 'Expert in stealth, precision strikes, and evasion.', icon: '🗡️', color: 'from-emerald-700 to-teal-900' },
  { id: 'cleric', name: 'Cleric', description: 'A holy champion who heals allies and smites foes.', icon: '✨', color: 'from-amber-500 to-amber-700' },
]

const form = ref({
  adventureTitle: '',
  characterName: '',
  selectedArchetype: ''
})

const isSubmitting = ref(false)
const errorMsg = ref('')

const goBack = () => {
  router.push({ name: 'portal' })
}

const selectArchetype = (id: string) => {
  form.value.selectedArchetype = id
}

const beginAdventure = async () => {
  if (!form.value.adventureTitle.trim() || !form.value.characterName.trim() || !form.value.selectedArchetype) {
    errorMsg.value = 'Please provide an adventure name, a character name, and select an archetype.'
    return
  }

  isSubmitting.value = true
  errorMsg.value = ''

  try {
    const res = await fetch('http://localhost:8000/api/v1/adventures', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        title: form.value.adventureTitle,
        avatar_name: form.value.characterName,
        strict_rules: true,
        heartbeat_enabled: false
      })
    })

    if (res.ok) {
      const data = await res.json()
      // data returns game_id, adventure_id, avatar_id
      router.push({ name: 'game', params: { id: data.game_id } })
    } else {
      errorMsg.value = 'Failed to create the adventure. Server returned an error.'
    }
  } catch (err) {
    errorMsg.value = 'Network error. Could not connect to the API.'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 font-sans p-8 flex justify-center pt-16">
    <div class="w-full max-w-4xl">
      <!-- Header -->
      <div class="flex items-center gap-4 mb-10">
        <button 
          @click="goBack" 
          class="p-2 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
          </svg>
        </button>
        <div>
          <h1 class="text-4xl font-extrabold text-white">Forging a New Tale</h1>
          <p class="text-slate-400 mt-2">Establish the realm and choose your champion.</p>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        <!-- Left Column: Details -->
        <div class="lg:col-span-1 space-y-6">
          <div class="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 shadow-xl">
            <h2 class="text-lg font-semibold text-white mb-4">Chronicle Details</h2>
            
            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-slate-400 mb-1">Adventure Chronicle Title</label>
                <input 
                  v-model="form.adventureTitle" 
                  type="text" 
                  placeholder="e.g. Shadows of Eldoria" 
                  class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all font-medium"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-slate-400 mb-1">Champion's Name</label>
                <input 
                  v-model="form.characterName" 
                  type="text" 
                  placeholder="e.g. Arthur Pendragon" 
                  class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all font-medium"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- Right Column: Archetypes -->
        <div class="lg:col-span-2">
          <div class="bg-slate-900/40 backdrop-blur-md rounded-3xl p-8 border border-white/5">
            <h2 class="text-xl font-semibold text-white mb-6">Select Archetype</h2>
            
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <button 
                v-for="arch in archetypes" 
                :key="arch.id"
                @click="selectArchetype(arch.id)"
                :class="[
                  'text-left p-5 rounded-2xl border transition-all duration-300 relative overflow-hidden group',
                  form.selectedArchetype === arch.id 
                    ? 'border-emerald-500 bg-white/5 shadow-[0_0_20px_rgba(16,185,129,0.2)]' 
                    : 'border-slate-800 bg-slate-950/50 hover:border-slate-600 hover:bg-slate-900'
                ]"
              >
                <!-- Selection indicator base format -->
                <div 
                  v-if="form.selectedArchetype === arch.id" 
                  class="absolute top-0 right-0 w-2 h-full bg-emerald-500 shadow-[0_0_10px_#10b981]"
                ></div>

                <!-- Icon background gradient on hover -->
                <div :class="`absolute -right-6 -bottom-6 w-32 h-32 rounded-full opacity-10 bg-gradient-to-br ${arch.color} blur-xl group-hover:opacity-30 transition-opacity duration-500`"></div>

                <div class="flex items-center gap-4 relative z-10">
                  <div class="text-4xl filter drop-shadow-md">{{ arch.icon }}</div>
                  <div>
                    <h3 class="text-lg font-bold text-white">{{ arch.name }}</h3>
                    <p class="text-sm text-slate-400 mt-1">{{ arch.description }}</p>
                  </div>
                </div>
              </button>
            </div>

            <!-- Error output -->
            <div 
              v-if="errorMsg" 
              class="mt-6 p-4 rounded-xl text-sm font-medium bg-red-500/10 text-red-400 border border-red-500/20"
            >
              {{ errorMsg }}
            </div>

            <div class="mt-8 flex justify-end">
              <button 
                @click="beginAdventure"
                :disabled="isSubmitting"
                class="px-8 py-3 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-bold rounded-xl shadow-lg hover:shadow-emerald-500/25 transition-all duration-300 transform hover:-translate-y-0.5 disabled:opacity-50 disabled:transform-none"
              >
                {{ isSubmitting ? 'Weaving Tale...' : 'Begin Journey' }}
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>
