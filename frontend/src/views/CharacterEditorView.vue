<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const isEditMode = computed(() => route.params.id !== undefined)

const charId = ref<string | null>(route.params.id as string || null)
const isSubmitting = ref(false)
const errorMsg = ref('')

// Form state
const name = ref('')
const profileImageUrl = ref<string | null>(null)

// For character sheet display locking defaults
const stats = ref({ strength: 10, endurance: 10, agility: 10, intelligence: 10, charisma: 10 })

const goBack = () => {
  router.push({ name: 'characters' })
}

const loadCharacter = async () => {
  if (!isEditMode.value) return;

  try {
    const res = await fetch(`http://localhost:8000/api/characters`)
    if (res.ok) {
      const all = await res.json()
      const character = all.find((c: any) => c.id === charId.value)
      if (character) {
        name.value = character.name
        profileImageUrl.value = character.profile_image
        if (character.stats) {
          stats.value = character.stats
        }
      }
    }
  } catch (err) {
    console.error('Failed to load character', err)
  }
}

const handleImageUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return

  const file = target.files[0]
  const formData = new FormData()
  formData.append('file', file)

  try {
    errorMsg.value = ''
    const res = await fetch(`http://localhost:8000/api/uploads/image?type=character`, {
      method: 'POST',
      body: formData
    })

    if (res.ok) {
      const data = await res.json()
      profileImageUrl.value = data.url
    } else {
      const err = await res.json()
      errorMsg.value = err.detail || 'Image upload failed. Must be under 256x256 dimensions logically.'
    }
  } catch (error) {
    errorMsg.value = 'Failed network connection for upload.'
  }
}

const saveCharacter = async () => {
  if (!name.value.trim()) {
    errorMsg.value = "A character must have a name."
    return
  }

  isSubmitting.value = true
  errorMsg.value = ''

  const payload = {
    name: name.value.trim(),
    profile_image: profileImageUrl.value,
    stats: stats.value
  }

  try {
    const url = isEditMode.value
      ? `http://localhost:8000/api/characters/${charId.value}`
      : `http://localhost:8000/api/characters`

    const method = isEditMode.value ? 'PUT' : 'POST'

    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    if (res.ok) {
      router.push({ name: 'characters' })
    } else {
      errorMsg.value = "Failed to save character."
    }
  } catch (err) {
    errorMsg.value = "Network error while saving."
  } finally {
    isSubmitting.value = false
  }
}

onMounted(() => {
  if (isEditMode.value) {
    loadCharacter()
  }
})
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 font-sans p-8 flex justify-center pt-16">
    <div class="w-full max-w-5xl">
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
          <h1 class="text-4xl font-extrabold text-white">{{ isEditMode ? 'Edit Champion' : 'Create Champion' }}</h1>
          <p class="text-slate-400 mt-2">Design your blueprint. Stats will initialize at 10.</p>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        <!-- Left: Form -->
        <div class="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-8 shadow-xl flex flex-col">
          <div class="space-y-6 flex-grow">
            <!-- Profile Image Uploader -->
            <div class="flex flex-col items-center mb-6">
              <div class="relative group cursor-pointer w-48 h-48 rounded-2xl overflow-hidden border-2 border-dashed border-slate-700 bg-slate-950/50 hover:border-emerald-500/50 transition-colors flex items-center justify-center">
                <template v-if="profileImageUrl">
                  <img :src="'http://localhost:8000' + profileImageUrl" alt="Avatar Preview" class="w-full h-full object-cover">
                </template>
                <template v-else>
                  <i class="ra ra-player text-6xl text-slate-600"></i>
                </template>
                
                <div class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  <span class="text-sm font-medium text-white shadow-sm flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                    Upload Image
                  </span>
                </div>
                <!-- Native file input overlaid and invisible -->
                <input type="file" @change="handleImageUpload" accept="image/png, image/jpeg, image/webp" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full" />
              </div>
              <p class="text-xs text-slate-500 mt-3 text-center">Max dimensions: 256x256 (PNG, JPG, WEBP)</p>
            </div>

            <!-- Character Name -->
            <div>
              <label class="block text-base font-semibold text-slate-300 mb-2">Character Name <span class="text-red-500">*</span></label>
              <input 
                v-model="name" 
                type="text" 
                maxlength="30"
                placeholder="e.g. Orion the Brave" 
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all font-medium"
              />
              <div class="text-right text-xs text-slate-500 mt-1">{{ name.length }} / 30</div>
            </div>

          </div>

          <!-- Error mapping -->
          <div v-if="errorMsg" class="mb-4 mt-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {{ errorMsg }}
          </div>

          <div class="mt-6 flex justify-end">
            <button 
              @click="saveCharacter"
              :disabled="isSubmitting || !name"
              class="w-full sm:w-auto px-8 py-3 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-bold rounded-xl shadow-lg hover:shadow-emerald-500/25 transition-all duration-300 disabled:opacity-50 disabled:transform-none"
            >
              {{ isSubmitting ? 'Saving...' : 'Save Character' }}
            </button>
          </div>
        </div>

        <!-- Right: Preview Sheet -->
        <div class="bg-slate-900/30 backdrop-blur-md rounded-3xl p-8 border border-white/5 relative overflow-hidden">
          <div class="absolute -right-16 -top-16 opacity-5 pointer-events-none">
             <i class="ra ra-scroll-unfurled text-[250px] text-white"></i>
          </div>

          <h2 class="text-xl font-semibold text-white mb-6 relative z-10 flex items-center gap-2">
            <i class="ra ra-perspective-dice-three text-emerald-500"></i>
            Base Attributes
          </h2>
          
          <div class="relative z-10 grid grid-cols-2 gap-4 mb-8">
            <div v-for="(val, statName) in stats" :key="statName" class="bg-slate-950/50 rounded-xl p-5 border border-slate-800 flex justify-between items-center">
              <span class="text-slate-300 capitalize font-semibold text-base">{{ statName }}</span>
              <span class="text-emerald-400 font-mono font-bold text-xl">{{ val }}</span>
            </div>
          </div>

          <div class="mt-8 relative z-10 opacity-60">
            <h2 class="text-lg font-semibold text-white mb-4">Equipment & Inventory</h2>
            <div class="p-8 border-2 border-dashed border-slate-700 rounded-xl text-center flex flex-col items-center">
              <i class="ra ra-locked text-3xl text-slate-500 mb-2"></i>
              <p class="text-sm text-slate-400 max-w-[200px]">Equipment slots remain empty until you begin your adventure.</p>
            </div>
          </div>

        </div>

      </div>
    </div>
  </div>
</template>
