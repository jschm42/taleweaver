<template>
  <div v-if="isOpen" class="modal-overlay" @click.self="close">
    <div class="modal-content glassmorphism">
      <header class="modal-header">
        <div class="header-title">
          <div class="avatar-container">
            <img :src="userAvatar" class="user-avatar" alt="User" />
          </div>
          <div class="user-info">
            <h2>{{ user?.username || 'Adventurer Profile' }}</h2>
            <span class="user-role">{{ user?.role || 'Player' }}</span>
          </div>
        </div>
        <button class="close-btn" @click="close">&times;</button>
      </header>

      <div class="modal-body custom-scrollbar">
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
              <span class="stat-value">{{ uniqueAdventures }}</span>
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
            <div 
              v-for="award in earnedAwards" 
              :key="award.earned_at + award.key" 
              class="trophy-tile"
              :class="award.tier"
            >
              <div class="trophy-icon-wrapper">
                <i class="ra ra-trophy trophy-icon"></i>
              </div>
              <div class="trophy-info">
                <div class="trophy-header">
                  <span class="trophy-title">{{ award.title }}</span>
                  <span class="trophy-tier">{{ award.tier }}</span>
                </div>
                <p class="trophy-desc">{{ award.description }}</p>
                <div class="trophy-footer">
                  <span class="adventure-ref">
                    <i class="ra ra-scroll"></i> {{ award.adventure_title }}
                  </span>
                  <span class="earned-date">{{ formatDate(award.earned_at) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { authState } from '@/store/auth'

const props = defineProps<{
  isOpen: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const user = computed(() => authState.user)
const userAvatar = computed(() => {
  if (user.value?.profile_image_url) {
    const baseUrl = import.meta.env.DEV ? 'http://localhost:8000' : ''
    return user.value.profile_image_url.startsWith('http') 
      ? user.value.profile_image_url 
      : `${baseUrl}${user.value.profile_image_url}`
  }
  return `https://api.dicebear.com/7.x/avataaars/svg?seed=${user.value?.username || 'default'}`
})

const earnedAwards = computed(() => {
  return (user.value?.earned_awards || []) as any[]
})

const uniqueAdventures = computed(() => {
  const ids = new Set(earnedAwards.value.map(a => a.adventure_id))
  return ids.size
})

function close() {
  emit('close')
}

function formatDate(isoString: string) {
  if (!isoString) return ''
  const d = new Date(isoString)
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' })
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  backdrop-filter: blur(12px);
}

.modal-content {
  width: 90%;
  max-width: 800px;
  max-height: 85vh;
  background: linear-gradient(135deg, rgba(15, 15, 30, 0.98), rgba(5, 5, 10, 0.99));
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 30px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 30px 100px rgba(0, 0, 0, 0.8);
  overflow: hidden;
  animation: modal-enter 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes modal-enter {
  from { transform: scale(0.9) translateY(40px); opacity: 0; }
  to { transform: scale(1) translateY(0); opacity: 1; }
}

.modal-header {
  padding: 20px 30px;
  background: rgba(255, 255, 255, 0.02);
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 20px;
}

.avatar-container {
  position: relative;
  width: 60px;
  height: 60px;
}

.user-avatar {
  width: 100%;
  height: 100%;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 24px;
  object-fit: cover;
  border: 2px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3);
}

.user-info h2 {
  margin: 0;
  font-family: 'Outfit', sans-serif;
  color: #fff;
  font-weight: 800;
  font-size: 1.4rem;
  letter-spacing: -0.5px;
}

.user-role {
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.3em;
  color: #4edea3;
  opacity: 0.8;
}

.close-btn {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.3);
  font-size: 32px;
  cursor: pointer;
  transition: all 0.2s;
}

.close-btn:hover {
  color: #fff;
  transform: rotate(90deg);
}

.modal-body {
  padding: 20px 30px;
  overflow-y: auto;
}

.stats-overview {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-bottom: 20px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
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
  height: 30px;
  background: rgba(255, 255, 255, 0.05);
  margin: 0 10px;
}

.stat-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(78, 222, 163, 0.1);
  border-radius: 10px;
  color: #4edea3;
  font-size: 1rem;
}

.stat-details {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1.2rem;
  font-weight: 900;
  color: #fff;
  line-height: 1;
}

.stat-label {
  font-size: 8px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin-top: 2px;
}

.awards-section h3 {
  margin-top: 0;
  margin-bottom: 25px;
  font-size: 0.9rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.3em;
  color: #94a3b8;
  display: flex;
  align-items: center;
  gap: 12px;
}

.empty-trophy {
  padding: 60px 40px;
  text-align: center;
  background: rgba(255, 255, 255, 0.01);
  border: 2px dashed rgba(255, 255, 255, 0.05);
  border-radius: 30px;
}

.empty-icon {
  font-size: 64px;
  color: rgba(255, 255, 255, 0.05);
  margin-bottom: 20px;
  display: block;
}

.empty-trophy p {
  color: rgba(255, 255, 255, 0.4);
  font-weight: 600;
  margin-bottom: 5px;
}

.empty-trophy .hint {
  font-size: 0.8rem;
  opacity: 0.5;
}

.trophy-grid {
  display: grid;
  grid-template-cols: 1fr;
  gap: 15px;
}

@media (min-width: 640px) {
  .trophy-grid {
    grid-template-cols: 1fr 1fr;
  }
}

.trophy-tile {
  display: flex;
  gap: 15px;
  padding: 15px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 18px;
  transition: all 0.3s;
}

.trophy-tile:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.1);
  transform: translateY(-3px);
}

.trophy-icon-wrapper {
  width: 50px;
  height: 50px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 12px;
}

.trophy-icon {
  font-size: 24px;
}

.bronze .trophy-icon { color: #cd7f32; }
.silver .trophy-icon { color: #c0c0c0; }
.gold .trophy-icon { color: #ffd700; }

.bronze:hover { border-color: rgba(205, 127, 50, 0.3); }
.silver:hover { border-color: rgba(192, 192, 192, 0.3); }
.gold:hover { border-color: rgba(255, 215, 0, 0.3); }

.trophy-info {
  flex-grow: 1;
  min-width: 0;
}

.trophy-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.trophy-title {
  font-weight: 800;
  color: #fff;
  font-size: 0.95rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trophy-tier {
  font-size: 8px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  opacity: 0.4;
}

.trophy-desc {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.4;
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.trophy-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.adventure-ref {
  color: #7c3aed;
  opacity: 0.8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60%;
}

.earned-date {
  color: rgba(255, 255, 255, 0.3);
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
}
</style>
