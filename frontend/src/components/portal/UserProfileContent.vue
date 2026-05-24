<template>
  <div class="profile-container custom-scrollbar">
    <div class="profile-card glassmorphism animate-page-in">
      <div class="profile-dashboard">
        
        <!-- Left Side: Identity, Bio, Settings (Sidebar) -->
        <aside class="profile-sidebar">
          <div class="avatar-section">
            <div class="avatar-wrapper group">
              <div class="avatar-container relative">
                <img :src="userAvatar" class="user-avatar" alt="User" />
                <!-- Generation Loading Spinner -->
                <div v-if="isGeneratingAvatar" class="absolute inset-0 bg-black/60 flex items-center justify-center rounded-full backdrop-blur-sm z-10">
                  <i class="ra ra-crystal-ball text-4xl text-white animate-spin"></i>
                </div>
                <div class="avatar-overlay opacity-0 group-hover:opacity-100 transition-all duration-300">
                  <button @click="triggerAvatarUpload" class="avatar-action-btn" title="Upload Avatar">
                    <i class="ra ra-plain-dagger rotate-45"></i>
                  </button>
                  <button 
                    v-if="canGenerateProfileImage"
                    @click="generateAvatar" 
                    :disabled="isGeneratingAvatar" 
                    class="avatar-action-btn" 
                    title="Generate with AI"
                  >
                    <i :class="['ra ra-crystal-ball', { 'animate-spin': isGeneratingAvatar }]"></i>
                  </button>
                </div>
              </div>
              <input type="file" ref="avatarInput" class="hidden" accept="image/*" @change="onAvatarFileSelected" />
            </div>
            
            <div class="user-identity text-center">
              <h2>{{ user?.username || 'Adventurer' }}</h2>
              <span class="user-role">{{ user?.role || 'Player' }}</span>
            </div>
          </div>

          <!-- Bio Chronicle Card -->
          <div class="glass-panel bio-card">
            <h4><i class="ra ra-quill-ink"></i> Chronicle Entry</h4>
            <div class="bio-container">
              <div v-if="!isEditingBio" class="bio-display group">
                <p v-if="user?.bio" class="bio-text italic text-slate-400">"{{ user.bio }}"</p>
                <p v-else class="bio-text text-slate-500 italic opacity-50">No chronicle entry yet...</p>
                <button @click="startEditBio" class="edit-bio-btn opacity-0 group-hover:opacity-100 transition-opacity">
                  <i class="ra ra-quill-ink"></i> Edit
                </button>
              </div>
              <div v-else class="bio-editor space-y-3">
                <textarea 
                  v-model="editBio" 
                  rows="3" 
                  class="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-slate-200 outline-none focus:border-emerald-500/50 transition-all shadow-inner"
                  placeholder="Tell your story..."
                ></textarea>
                <div class="flex justify-between items-center gap-2">
                  <button @click="generateBio" :disabled="isGeneratingBio" class="text-xxs font-black uppercase tracking-widest text-emerald-500/60 hover:text-emerald-400 flex items-center gap-1">
                    <i :class="['ra ra-crystal-ball', { 'animate-spin': isGeneratingBio }]"></i>
                    {{ isGeneratingBio ? 'Weaving...' : 'AI Lore' }}
                  </button>
                  <div class="flex gap-2">
                    <button @click="cancelEditBio" class="text-xxs font-black uppercase tracking-widest text-slate-500 hover:text-white">Discard</button>
                    <button @click="saveBio" :disabled="isSavingBio" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-lg shadow-lg shadow-emerald-900/20">
                      Save
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Bable Fish Default Settings -->
          <div class="glass-panel language-card">
            <div class="flex flex-col gap-3">
              <div class="flex items-center gap-3">
                <div class="lang-icon bg-cyan-500/10 text-cyan-400">
                  <i class="ra ra-fish"></i>
                </div>
                <div>
                  <h4 class="text-xs font-black uppercase tracking-widest text-cyan-400">Bable Fish</h4>
                  <p class="text-[9px] text-slate-500 uppercase font-bold tracking-wider italic">Primary translator tongue</p>
                </div>
              </div>
              
              <div class="flex items-center gap-2">
                <select 
                  v-model="selectedLanguage" 
                  @change="saveDefaultLanguage"
                  :disabled="isSavingLanguage"
                  class="bg-black/60 border border-cyan-500/30 rounded-xl px-3 py-1.5 text-xs font-bold text-white outline-none focus:border-cyan-400 transition-all cursor-pointer w-full"
                >
                  <option v-for="lang in languages" :key="lang.code" :value="lang.code">
                    {{ lang.name }}
                  </option>
                </select>
                <i v-if="isSavingLanguage" class="ra ra-cycle animate-spin text-cyan-400 text-xs"></i>
              </div>
            </div>
          </div>
        </aside>

        <!-- Right Side: Stats, Awards, Chronicle (Main Content) -->
        <main class="profile-main">
          
          <!-- Stats Overview Card -->
          <div class="stats-overview">
            <div class="stat-item">
              <div class="stat-icon"><i class="ra ra-trophy"></i></div>
              <div class="stat-details">
                <span class="stat-value">{{ earnedAwards.length }}</span>
                <span class="stat-label">Awards</span>
              </div>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <div class="stat-icon"><i class="ra ra-scroll"></i></div>
              <div class="stat-details">
                <span class="stat-value">{{ user?.adventure_count || 0 }}</span>
                <span class="stat-label">Adventures</span>
              </div>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <div class="stat-icon"><i class="ra ra-sparkles"></i></div>
              <div class="stat-details">
                <span class="stat-value">{{ user?.total_xp || 0 }}</span>
                <span class="stat-label">Total XP</span>
              </div>
            </div>
          </div>

          <!-- Trophy Room -->
          <div class="awards-section">
            <h3><span class="section-icon">🏆</span> Trophy Room</h3>
            
            <div v-if="earnedAwards.length === 0" class="empty-trophy">
              <i class="ra ra-trophy empty-icon"></i>
              <p>Your trophy room is currently empty.</p>
              <p class="hint">Earn awards by completing heroic deeds in adventures!</p>
            </div>

            <div v-else class="trophy-grid">
              <AwardTile 
                v-for="award in earnedAwards" 
                :key="(award.earned_at || '') + award.key"
                :award="award"
              />
            </div>
          </div>

          <!-- Chronicle of Deeds -->
          <div class="history-section">
            <h3><span class="section-icon">📜</span> Chronicle of Deeds</h3>
            
            <div v-if="!gameLog.length" class="empty-history text-center py-12 bg-white/5 rounded-3xl border border-white/5">
              <i class="ra ra-scroll text-4xl text-white/5 block mb-3"></i>
              <p class="text-slate-500 italic text-xs">No historical records found in the archives.</p>
            </div>

            <div v-else class="history-grid">
              <div v-for="(entry, idx) in gameLog" :key="idx" class="history-entry p-4 bg-black/40 rounded-2xl border border-white/5 hover:border-emerald-500/30 transition-all group">
                <div class="flex justify-between items-start gap-4">
                  <div class="flex-grow">
                    <div class="flex items-center gap-2 mb-2 flex-wrap">
                      <span :class="entry.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'" class="text-[10px] font-black uppercase tracking-[0.15em] px-2 py-0.5 rounded-full border border-current/20">
                        {{ entry.status === 'completed' ? 'Victory' : 'Defeat' }}
                      </span>
                      <span class="bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[10px] font-black uppercase tracking-[0.15em] px-2 py-0.5 rounded-full">
                        {{ entry.xp || 0 }} XP
                      </span>
                      <span class="text-[10px] text-slate-600 font-bold uppercase tracking-widest ml-auto">{{ formatDate(entry.completed_at) }}</span>
                    </div>
                    <h4 class="text-base font-bold text-white group-hover:text-emerald-400 transition-colors leading-snug">{{ entry.adventure_title }}</h4>
                    <p class="text-xs text-slate-400 mt-2 italic line-clamp-2 leading-relaxed">"{{ entry.outcome_note }}"</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>

      </div>
    </div>

    <!-- Notifications -->
    <Teleport to="body">
      <div class="fixed bottom-8 right-8 z-[100] flex flex-col gap-3 pointer-events-none">
        <TransitionGroup name="notification">
          <div 
            v-for="n in notifications" 
            :key="n.id"
            class="pointer-events-auto flex items-center gap-4 px-6 py-4 rounded-2xl border backdrop-blur-xl shadow-2xl min-w-[300px] max-w-md animate-notification-in"
            :class="[
              n.type === 'error' ? 'bg-red-500/10 border-red-500/20 text-red-400' :
              n.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' :
              'bg-blue-500/10 border-blue-500/20 text-blue-400'
            ]"
          >
            <i :class="['text-lg', n.type === 'error' ? 'ra ra-cancel' : n.type === 'success' ? 'ra ra-circle' : 'ra ra-light-bulb']"></i>
            <div class="flex-grow">
              <p class="text-xxs font-black uppercase tracking-widest opacity-50">{{ n.type }}</p>
              <p class="text-xs font-bold leading-relaxed">{{ n.message }}</p>
            </div>
            <button @click="notifications = notifications.filter(x => x.id !== n.id)" class="opacity-50 hover:opacity-100 transition-opacity">
              <i class="ra ra-cancel text-xs"></i>
            </button>
          </div>
        </TransitionGroup>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { authState, refreshUser } from '@/store/auth'
import { api } from '@/composables/useApi'
import AwardTile from './AwardTile.vue'

const BASE = '/api'

function normalizeProfileImageUrl(url: string): string {
  let normalized = (url || '').replace(/\\\\/g, '/')
  while (normalized.startsWith('/data/data/')) {
    normalized = normalized.replace('/data/data/', '/data/')
  }
  return normalized
}

const user = computed(() => authState.user)
const userAvatar = computed(() => {
  if (user.value?.profile_image_url) {
    const baseUrl = ''
    const normalized = normalizeProfileImageUrl(user.value.profile_image_url)
    return normalized.startsWith('http') 
      ? normalized 
      : `${baseUrl}${normalized}`
  }
  return `https://api.dicebear.com/7.x/avataaars/svg?seed=${user.value?.username || 'default'}`
})

const earnedAwards = computed(() => {
  return (user.value?.earned_awards || []) as any[]
})

const gameLog = computed(() => {
  return (user.value?.game_log || []) as any[]
})

function formatDate(dateStr?: string): string {
  if (!dateStr) return 'Eons ago'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

// Bio Editing
const isEditingBio = ref(false)
const isSavingBio = ref(false)
const isGeneratingBio = ref(false)
const isSavingLanguage = ref(false)
const editBio = ref('')

const languages = [
  { code: '', name: 'Default (English)' },
  { code: 'German', name: 'Deutsch' },
  { code: 'English', name: 'English' },
  { code: 'French', name: 'Français' },
  { code: 'Spanish', name: 'Español' },
  { code: 'Italian', name: 'Italiano' },
  { code: 'Japanese', name: '日本語' },
  { code: 'Chinese', name: '中文' },
  { code: 'Russian', name: 'Русский' },
  { code: 'Portuguese', name: 'Português' },
]

const selectedLanguage = ref(user.value?.default_language || '')

function startEditBio() {
  editBio.value = user.value?.bio || ''
  isEditingBio.value = true
}

function cancelEditBio() {
  isEditingBio.value = false
}

async function saveBio() {
  isSavingBio.value = true
  try {
    const res = await fetch(`${BASE}/users/me/bio`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authState.token}`
      },
      body: JSON.stringify({ bio: editBio.value })
    })
    if (!res.ok) throw new Error('Failed to save bio')
    await refreshUser()
    isEditingBio.value = false
    addNotification('Biography updated in the archives.', 'success')
  } catch (error: any) {
    addNotification(error.message, 'error')
  } finally {
    isSavingBio.value = false
  }
}

async function generateBio() {
  isGeneratingBio.value = true
  try {
    const res = await fetch(`${BASE}/users/me/bio/generate`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${authState.token}` }
    })
    if (!res.ok) throw new Error('Generation failed')
    const data = await res.json()
    editBio.value = data.bio
    addNotification('AI weaver has crafted your lore.', 'success')
  } catch (error: any) {
    addNotification(error.message, 'error')
  } finally {
    isGeneratingBio.value = false
  }
}

async function saveDefaultLanguage() {
  if (!user.value) return
  isSavingLanguage.value = true
  try {
    const res = await fetch(`${BASE}/users/${user.value.id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authState.token}`
      },
      body: JSON.stringify({ default_language: selectedLanguage.value })
    })
    if (!res.ok) throw new Error('Failed to save language preference')
    await refreshUser()
    addNotification('Universal translator recalibrated.', 'success')
  } catch (error: any) {
    addNotification(error.message, 'error')
    selectedLanguage.value = user.value.default_language || ''
  } finally {
    isSavingLanguage.value = false
  }
}

// Avatar Management
const avatarInput = ref<HTMLInputElement | null>(null)
const isGeneratingAvatar = ref(false)
const canGenerateProfileImage = ref(false)

async function checkAvatarGenerationAvailability() {
  try {
    const settings = await api.getSettings()
    const t2i = (settings?.t2i_settings || {}) as any
    canGenerateProfileImage.value = !!(t2i.simple_model)
    
    // Log for debugging purposes
    if (!t2i.simple_model) {
      console.warn('Profile image generation disabled: No simple_model configured in T2I settings')
    }
  } catch (err) {
    console.error('Error checking avatar generation availability:', err)
    canGenerateProfileImage.value = false
  }
}

onMounted(() => {
  checkAvatarGenerationAvailability()
})

function triggerAvatarUpload() {
  avatarInput.value?.click()
}

async function onAvatarFileSelected(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)

  try {
    const res = await fetch(`${BASE}/users/me/profile-image`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${authState.token}` },
      body: formData
    })
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}))
      throw new Error(errorData.detail || `Upload failed with status ${res.status}`)
    }
    await refreshUser()
    addNotification('New identity visual uploaded.', 'success')
  } catch (error: any) {
    console.error('Profile image upload error:', error)
    addNotification(error.message || 'Failed to upload profile image', 'error')
  } finally {
    target.value = ''
  }
}

async function generateAvatar() {
  isGeneratingAvatar.value = true
  try {
    const res = await fetch(`${BASE}/users/me/profile-image/generate`, {
      method: 'POST',
      headers: { 
        'Authorization': `Bearer ${authState.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ bio: user.value?.bio })
    })
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}))
      throw new Error(errorData.detail || `Generation failed with status ${res.status}`)
    }
    await refreshUser()
    addNotification('Aether has manifested your new form.', 'success')
  } catch (error: any) {
    console.error('Profile image generation error:', error)
    addNotification(error.message || 'Failed to generate profile image. Please check admin T2I settings.', 'error')
  } finally {
    isGeneratingAvatar.value = false
  }
}

// Notifications Helper
const notifications = ref<any[]>([])
function addNotification(message: string, type: 'info' | 'success' | 'error' = 'info') {
  const id = Date.now()
  notifications.value.push({ id, message, type })
  setTimeout(() => {
    notifications.value = notifications.value.filter(n => n.id !== id)
  }, 5000)
}
</script>

<style scoped>
.profile-container {
  padding: 1.5rem;
  height: 100%;
  overflow-y: auto;
  width: 100%;
}

.profile-card {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  background: linear-gradient(135deg, rgba(15, 15, 30, 0.45), rgba(5, 5, 10, 0.65));
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 32px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 30px 100px rgba(0, 0, 0, 0.4);
}

.profile-dashboard {
  display: grid;
  grid-template-columns: 1fr;
  width: 100%;
}

@media (min-width: 1024px) {
  .profile-dashboard {
    grid-template-columns: 300px 1fr;
  }
}

.animate-page-in {
  animation: pageIn 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes pageIn {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Sidebar Styling */
.profile-sidebar {
  padding: 24px;
  background: rgba(255, 255, 255, 0.01);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

@media (min-width: 1024px) {
  .profile-sidebar {
    border-bottom: none;
    border-right: 1px solid rgba(255, 255, 255, 0.05);
  }
}

.avatar-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.avatar-wrapper {
  flex-shrink: 0;
}

.avatar-container {
  position: relative;
  width: 110px;
  height: 110px;
  border-radius: 36px;
  overflow: hidden;
  background: #000;
  border: 3px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 15px 30px rgba(0, 0, 0, 0.5);
  transition: border-color 0.3s;
}

.avatar-container:hover {
  border-color: #4edea3;
}

.user-avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.avatar-action-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.avatar-action-btn:hover {
  background: #4edea3;
  color: #000;
  transform: scale(1.08);
}

.user-identity h2 {
  margin: 0;
  font-family: 'Outfit', sans-serif;
  color: #fff;
  font-weight: 800;
  font-size: 1.35rem;
  letter-spacing: -0.4px;
  line-height: 1.2;
}

.user-role {
  display: inline-block;
  margin-top: 6px;
  font-size: 10px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.4em;
  color: #4edea3;
  opacity: 0.85;
}

.glass-panel {
  background: rgba(255, 255, 255, 0.015);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 20px;
  padding: 16px;
  transition: all 0.3s;
}

.glass-panel:hover {
  border-color: rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.025);
}

.glass-panel h4 {
  margin-top: 0;
  margin-bottom: 10px;
  font-size: 10px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  color: #94a3b8;
  display: flex;
  align-items: center;
  gap: 8px;
}

.bio-display {
  position: relative;
  padding-bottom: 20px;
}

.bio-text {
  font-size: 0.8rem;
  line-height: 1.45;
  color: #cbd5e1;
}

.edit-bio-btn {
  position: absolute;
  bottom: 0;
  right: 0;
  font-size: 9px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.3s;
}

.edit-bio-btn:hover {
  color: #4edea3;
}

.lang-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 0.8rem;
}

/* Main Content Panel Styling */
.profile-main {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* Stats Overview */
.stats-overview {
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding: 16px;
  background: rgba(255, 255, 255, 0.015);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 20px;
}

.stat-item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.stat-divider {
  width: 1px;
  height: 36px;
  background: rgba(255, 255, 255, 0.05);
}

.stat-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(78, 222, 163, 0.1);
  border-radius: 12px;
  color: #4edea3;
  font-size: 0.95rem;
}

.stat-item:last-child .stat-icon {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

.stat-value {
  font-size: 1.35rem;
  font-weight: 900;
  color: #fff;
  line-height: 1;
}

.stat-label {
  font-size: 9px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: #64748b;
  margin-top: 4px;
  display: block;
}

/* Trophies & Deeds Header */
.awards-section h3,
.history-section h3 {
  margin-top: 0;
  margin-bottom: 16px;
  font-size: 0.8rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: #94a3b8;
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Empty States */
.empty-trophy {
  padding: 32px 16px;
  text-align: center;
  background: rgba(255, 255, 255, 0.005);
  border: 1px dashed rgba(255, 255, 255, 0.03);
  border-radius: 24px;
}

.empty-icon {
  font-size: 36px;
  color: rgba(255, 255, 255, 0.02);
  margin-bottom: 12px;
  display: block;
}

.empty-trophy p, .empty-history p {
  color: #64748b;
  font-size: 0.8rem;
}

.empty-trophy .hint {
  font-size: 0.75rem;
  opacity: 0.7;
  margin-top: 4px;
}

/* Trophy Grid */
.trophy-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  width: 100%;
}

@media (min-width: 640px) {
  .trophy-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1200px) {
  .trophy-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

/* Chronicle of Deeds */
.history-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  width: 100%;
}

@media (min-width: 768px) {
  .history-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.history-entry {
  transition: all 0.3s;
}

.history-entry:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.04);
  border-radius: 10px;
}

/* Notifications Animations */
.notification-enter-active, .notification-leave-active { transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.notification-enter-from { opacity: 0; transform: translateX(50px); }
.notification-leave-to { opacity: 0; transform: scale(0.9); }
</style>
