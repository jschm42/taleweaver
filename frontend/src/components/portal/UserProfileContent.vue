<template>
  <div class="profile-container custom-scrollbar">
    <div class="profile-card glassmorphism animate-page-in">
      <header class="profile-header">
        <div class="header-main">
          <div class="avatar-wrapper group">
            <div class="avatar-container">
              <img :src="userAvatar" class="user-avatar" alt="User" />
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
          
          <div class="user-meta">
            <div class="user-identity">
              <h2>{{ user?.username || 'Adventurer Profile' }}</h2>
              <span class="user-role">{{ user?.role || 'Player' }}</span>
            </div>
            
            <div class="bio-container">
              <div v-if="!isEditingBio" class="bio-display group">
                <p v-if="user?.bio" class="bio-text italic text-slate-400">"{{ user.bio }}"</p>
                <p v-else class="bio-text text-slate-500 italic opacity-50">No chronicle entry yet...</p>
                <button @click="startEditBio" class="edit-bio-btn opacity-0 group-hover:opacity-100 transition-opacity">
                  <i class="ra ra-quill-ink"></i> Edit Bio
                </button>
              </div>
              <div v-else class="bio-editor space-y-3">
                <textarea 
                  v-model="editBio" 
                  rows="3" 
                  class="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-slate-200 outline-none focus:border-emerald-500/50 transition-all shadow-inner"
                  placeholder="Tell your story..."
                ></textarea>
                <div class="flex justify-between items-center">
                  <button @click="generateBio" :disabled="isGeneratingBio" class="text-[9px] font-black uppercase tracking-widest text-emerald-500/60 hover:text-emerald-400 flex items-center gap-2">
                    <i :class="['ra ra-crystal-ball', { 'animate-spin': isGeneratingBio }]"></i>
                    {{ isGeneratingBio ? 'Weaving...' : 'AI Lore Weaver' }}
                  </button>
                  <div class="flex gap-3">
                    <button @click="cancelEditBio" class="text-[9px] font-black uppercase tracking-widest text-slate-500 hover:text-white">Discard</button>
                    <button @click="saveBio" :disabled="isSavingBio" class="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-black uppercase tracking-widest rounded-lg shadow-lg shadow-emerald-900/20">
                      {{ isSavingBio ? 'Saving...' : 'Save Entry' }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div class="profile-body">
        <div class="stats-overview">
          <div class="stat-item">
            <div class="stat-icon"><i class="ra ra-trophy"></i></div>
            <div class="stat-details">
              <span class="stat-value">{{ earnedAwards.length }}</span>
              <span class="stat-label">Awards Earned</span>
            </div>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <div class="stat-icon"><i class="ra ra-scroll"></i></div>
            <div class="stat-details">
              <span class="stat-value">{{ user?.adventure_count || 0 }}</span>
              <span class="stat-label">Adventures Played</span>
            </div>
          </div>
        </div>

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
              <p class="text-[10px] font-black uppercase tracking-widest opacity-50">{{ n.type }}</p>
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

const user = computed(() => authState.user)
const userAvatar = computed(() => {
  if (user.value?.profile_image_url) {
    const baseUrl = ''
    return user.value.profile_image_url.startsWith('http') 
      ? user.value.profile_image_url 
      : `${baseUrl}${user.value.profile_image_url}`
  }
  return `https://api.dicebear.com/7.x/avataaars/svg?seed=${user.value?.username || 'default'}`
})

const earnedAwards = computed(() => {
  return (user.value?.earned_awards || []) as any[]
})

// Bio Editing
const isEditingBio = ref(false)
const isSavingBio = ref(false)
const isGeneratingBio = ref(false)
const editBio = ref('')

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

// Avatar Management
const avatarInput = ref<HTMLInputElement | null>(null)
const isGeneratingAvatar = ref(false)
const canGenerateProfileImage = ref(false)

async function checkAvatarGenerationAvailability() {
  try {
    const settings = await api.getSettings()
    const t2i = (settings?.t2i_settings || {}) as any
    canGenerateProfileImage.value = !!(t2i.simple_model)
  } catch (err) {
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
    if (!res.ok) throw new Error('Upload failed')
    await refreshUser()
    addNotification('New identity visual uploaded.', 'success')
  } catch (error: any) {
    addNotification(error.message, 'error')
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
    if (!res.ok) throw new Error('Generation failed')
    await refreshUser()
    addNotification('Aether has manifested your new form.', 'success')
  } catch (error: any) {
    addNotification(error.message, 'error')
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
  padding: 2rem;
  height: 100%;
  overflow-y: auto;
  width: 100%;
}

.profile-card {
  width: 100%;
  max-width: 1300px;
  margin: 0 auto;
  background: linear-gradient(135deg, rgba(15, 15, 30, 0.4), rgba(5, 5, 10, 0.6));
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 40px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 30px 100px rgba(0, 0, 0, 0.3);
}

.animate-page-in {
  animation: pageIn 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes pageIn {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

.profile-header {
  padding: 28px;
  background: rgba(255, 255, 255, 0.01);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.header-main {
  display: flex;
  align-items: flex-start;
  gap: 40px;
}

.avatar-wrapper {
  flex-shrink: 0;
}

.avatar-container {
  position: relative;
  width: 112px;
  height: 112px;
  border-radius: 40px;
  overflow: hidden;
  background: #000;
  border: 3px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
}

.user-avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 15px;
}

.avatar-action-btn {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.1);
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
  transform: scale(1.1);
}

.user-meta {
  flex-grow: 1;
  padding-top: 10px;
}

.user-identity h2 {
  margin: 0;
  font-family: 'Outfit', sans-serif;
  color: #fff;
  font-weight: 800;
  font-size: 1.55rem;
  letter-spacing: -0.6px;
  line-height: 1;
}

.user-role {
  display: inline-block;
  margin-top: 10px;
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.5em;
  color: #4edea3;
  opacity: 0.8;
}

.bio-container {
  margin-top: 25px;
}

.bio-display {
  position: relative;
  padding-right: 100px;
}

.bio-text {
  font-size: 0.86rem;
  line-height: 1.45;
  max-width: 600px;
}

.edit-bio-btn {
  position: absolute;
  top: 0;
  right: 0;
  font-size: 9px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s;
}

.edit-bio-btn:hover {
  color: #4edea3;
}

.profile-body {
  padding: 28px;
  width: 100%;
}

.stats-overview {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-bottom: 24px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.015);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 30px;
}

.stat-item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.stat-divider {
  width: 1px;
  height: 48px;
  background: rgba(255, 255, 255, 0.05);
  margin: 0 16px;
}

.stat-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(78, 222, 163, 0.1);
  border-radius: 14px;
  color: #4edea3;
  font-size: 1rem;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 900;
  color: #fff;
  line-height: 1;
}

.stat-label {
  font-size: 10px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  color: #64748b;
  margin-top: 8px;
}

.awards-section {
  width: 100%;
}

.awards-section h3 {
  margin-top: 0;
  margin-bottom: 16px;
  font-size: 0.86rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.22em;
  color: #94a3b8;
  display: flex;
  align-items: center;
  gap: 20px;
}

.empty-trophy {
  padding: 56px 24px;
  text-align: center;
  background: rgba(255, 255, 255, 0.005);
  border: 2px dashed rgba(255, 255, 255, 0.03);
  border-radius: 50px;
}

.empty-icon {
  font-size: 56px;
  color: rgba(255, 255, 255, 0.02);
  margin-bottom: 16px;
  display: block;
}

@media (max-width: 900px) {
  .profile-header,
  .profile-body {
    padding: 24px;
  }

  .header-main {
    flex-direction: column;
    gap: 20px;
  }

  .user-identity h2 {
    font-size: 1.25rem;
  }

  .stats-overview {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
  }

  .stat-divider {
    width: 100%;
    height: 1px;
    margin: 0;
  }
}

.trophy-grid {
  display: grid !important;
  grid-template-columns: repeat(1, 1fr) !important;
  gap: 25px;
  width: 100%;
}

@media (min-width: 768px) {
  .trophy-grid {
    grid-template-columns: repeat(2, 1fr) !important;
  }
}

@media (min-width: 1200px) {
  .trophy-grid {
    grid-template-columns: repeat(3, 1fr) !important;
  }
}

.custom-scrollbar::-webkit-scrollbar {
  width: 8px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
}

/* Notifications Animations */
.notification-enter-active, .notification-leave-active { transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.notification-enter-from { opacity: 0; transform: translateX(50px); }
.notification-leave-to { opacity: 0; transform: scale(0.9); }
</style>
