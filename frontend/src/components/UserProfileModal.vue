<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { authState } from '@/store/auth'
import { api } from '@/composables/useApi'

const isOpen = ref(false)
const bio = ref(authState.user?.bio || '')
const isSaving = ref(false)
const isGeneratingBio = ref(false)
const isGeneratingImage = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const canGenerateProfileImage = ref(false)

async function refreshProfileImageGenerationAvailability() {
  canGenerateProfileImage.value = false
  try {
    const settings = await api.getSettings()
    const t2i = (settings?.t2i_settings || {}) as Record<string, unknown>
    const simpleModel = String(t2i.simple_model || '').trim()
    canGenerateProfileImage.value = simpleModel.length > 0
  } catch (err) {
    console.error('Failed to load settings for profile image generation:', err)
  }
}

async function handleOpen() {
  bio.value = authState.user?.bio || ''
  isOpen.value = true
  await refreshProfileImageGenerationAvailability()
}

onMounted(() => {
  window.addEventListener('open-profile-modal', handleOpen)
})

onUnmounted(() => {
  window.removeEventListener('open-profile-modal', handleOpen)
})

async function saveProfile() {
  isSaving.value = true
  try {
    const updated = await api.updateMyBio(bio.value)
    authState.user = updated
    isOpen.value = false
  } catch (err) {
    console.error('Failed to save profile:', err)
  } finally {
    isSaving.value = false
  }
}

async function handleImageUpload(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  
  try {
    const updated = await api.uploadProfileImage(file)
    authState.user = updated
  } catch (err) {
    console.error('Image upload failed:', err)
  }
}

async function generateBio() {
  isGeneratingBio.value = true
  try {
    const data = await api.generateMyBio()
    bio.value = data.bio
  } catch (err) {
    console.error('Bio generation failed:', err)
  } finally {
    isGeneratingBio.value = false
  }
}

async function generateImage() {
  isGeneratingImage.value = true
  try {
    const updated = await api.generateMyProfileImage(bio.value)
    authState.user = updated
  } catch (err) {
    console.error('Image generation failed:', err)
  } finally {
    isGeneratingImage.value = false
  }
}
</script>

<template>
  <Transition
    enter-active-class="transition duration-300 ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-200 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div v-if="isOpen" class="fixed inset-0 z-[200] flex items-center justify-center p-6 bg-[#02060c]/80 backdrop-blur-md">
      <div class="w-full max-w-xl bg-[#0a111c] border border-white/10 rounded-[2rem] overflow-hidden shadow-2xl relative">
        <!-- Close Button -->
        <button @click="isOpen = false" class="absolute top-6 right-6 text-slate-500 hover:text-white transition-colors">
          <i class="ra ra-cancel text-xl"></i>
        </button>

        <div class="p-10">
          <h2 class="text-2xl font-black text-white font-display mb-8">User Profile</h2>

          <div class="flex gap-8 mb-10">
            <!-- Profile Image Section -->
            <div class="flex flex-col items-center gap-4">
              <div class="w-32 h-32 rounded-3xl bg-white/5 border border-white/10 overflow-hidden relative group">
                <img 
                  v-if="authState.user?.profile_image_url" 
                  :src="authState.user.profile_image_url" 
                  class="w-full h-full object-cover" 
                />
                <div v-else class="w-full h-full flex items-center justify-center bg-aether-primary/10">
                  <i class="ra ra-hood text-4xl text-aether-primary"></i>
                </div>
                
                <div 
                  @click="fileInput?.click()"
                  class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center cursor-pointer transition-opacity"
                >
                  <i class="ra ra-camera text-xl text-white"></i>
                </div>
              </div>
              <input ref="fileInput" type="file" hidden accept="image/*" @change="handleImageUpload" />
              
              <button
                v-if="canGenerateProfileImage"
                @click="generateImage"
                :disabled="isGeneratingImage"
                class="text-[9px] font-black text-slate-500 hover:text-aether-primary uppercase tracking-[0.2em] transition-all flex items-center gap-2"
              >
                <i class="ra ra-crystal-ball text-xs"></i>
                {{ isGeneratingImage ? 'Summoning...' : 'Summon Portrait' }}
              </button>
              
              <span class="text-[10px] font-black text-slate-700 uppercase tracking-widest mt-2">Master of Tales</span>
            </div>

            <!-- Fields Section -->
            <div class="flex-1 space-y-6">
              <div class="space-y-2">
                <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Username</label>
                <div class="p-3 bg-white/5 border border-white/5 rounded-xl text-white font-bold text-sm opacity-60">
                  {{ authState.user?.username }}
                </div>
              </div>

              <div class="space-y-2">
                <div class="flex justify-between items-center ml-1">
                  <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest">Lore / Bio</label>
                  <button 
                    @click="generateBio"
                    :disabled="isGeneratingBio"
                    class="text-[9px] font-black text-aether-primary uppercase tracking-widest hover:text-white transition-colors disabled:opacity-40"
                  >
                    <i class="ra ra-crystal-ball mr-1"></i>
                    {{ isGeneratingBio ? 'Weaving...' : 'Generate Bio' }}
                  </button>
                </div>
                <textarea 
                  v-model="bio"
                  rows="4"
                  class="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-sm text-slate-300 focus:outline-none focus:border-aether-primary/50 transition-all resize-none"
                  placeholder="Describe your legend..."
                ></textarea>
              </div>
            </div>
          </div>

          <div class="flex justify-end gap-4">
            <button @click="isOpen = false" class="px-6 py-2.5 text-xs font-bold text-slate-500 hover:text-white transition-colors">
              Cancel
            </button>
            <button 
              @click="saveProfile"
              :disabled="isSaving"
              class="btn-primary px-8 !py-2.5 shadow-ambient-emerald/10"
            >
              {{ isSaving ? 'Saving...' : 'Save Changes' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
