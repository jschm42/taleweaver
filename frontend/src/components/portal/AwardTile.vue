<template>
  <div class="award-tile glassmorphism group" :class="award.tier">
    <div class="award-visual">
      <img :src="icon" class="award-svg" :alt="award.title" />
      <div class="award-glow"></div>
    </div>
    
    <div class="award-content">
      <div class="award-header">
        <h4 class="award-title">{{ award.title }}</h4>
        <span class="award-tier-badge">{{ award.tier }}</span>
      </div>
      
      <p class="award-description">{{ award.description }}</p>
      
      <div class="award-footer">
        <div class="adventure-source">
          <i class="ra ra-scroll"></i>
          <span>{{ award.adventure_title }}</span>
        </div>
        <div class="award-date">
          {{ formatDate(award.earned_at) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import bronzeTrophy from '@/assets/svg/bronze-award-trophy.svg'
import silverTrophy from '@/assets/svg/silver-award-trophy.svg'
import goldTrophy from '@/assets/svg/gold-award-trophy.svg'

const props = defineProps<{
  award: {
    key: string
    title: string
    description: string
    tier: string
    adventure_title: string
    earned_at?: string
  }
}>()

const icon = computed(() => {
  const t = (props.award.tier || '').toLowerCase()
  if (t === 'gold') return goldTrophy
  if (t === 'silver') return silverTrophy
  return bronzeTrophy
})

function formatDate(isoString?: string) {
  if (!isoString) return ''
  const d = new Date(isoString)
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' })
}
</script>

<style scoped>
.award-tile {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 30px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
  overflow: hidden;
}

.award-tile:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.1);
  transform: translateY(-8px);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
}

.award-visual {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.award-svg {
  width: 90px;
  height: 90px;
  object-fit: contain;
  filter: drop-shadow(0 0 15px rgba(0, 0, 0, 0.5));
  z-index: 1;
  transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.award-tile:hover .award-svg {
  transform: scale(1.1) rotate(5deg);
}

.award-glow {
  position: absolute;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  filter: blur(40px);
  opacity: 0.2;
  z-index: 0;
  transition: opacity 0.4s;
}

.gold .award-glow { background: #fbbf24; }
.silver .award-glow { background: #cbd5e1; }
.bronze .award-glow { background: #c2410c; }

.award-tile:hover .award-glow {
  opacity: 0.4;
}

.award-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.award-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 800;
  color: #fff;
  letter-spacing: -0.5px;
  line-height: 1.2;
}

.award-tier-badge {
  font-size: 8px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.gold .award-tier-badge { background: rgba(251, 191, 36, 0.1); color: #fbbf24; border-color: rgba(251, 191, 36, 0.2); }
.silver .award-tier-badge { background: rgba(203, 213, 225, 0.1); color: #cbd5e1; border-color: rgba(203, 213, 225, 0.2); }
.bronze .award-tier-badge { background: rgba(194, 65, 12, 0.1); color: #ea580c; border-color: rgba(194, 65, 12, 0.2); }

.award-description {
  font-size: 0.85rem;
  color: #94a3b8;
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.award-footer {
  margin-top: auto;
  padding-top: 15px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.adventure-source {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 9px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.award-date {
  font-size: 9px;
  font-weight: 600;
  color: #475569;
}
</style>

