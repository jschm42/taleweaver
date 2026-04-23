<template>
  <div v-if="isOpen" class="quests-modal-overlay" @click.self="close">
    <div class="quests-modal-content glassmorphism">
      <header class="modal-header">
        <div class="header-title">
          <img src="@/assets/svg/fantasy-spellbook.svg" alt="Quests" class="header-icon" />
          <h2>Quest Log</h2>
        </div>
        <button class="close-btn" @click="close">&times;</button>
      </header>

      <div class="modal-tabs">
        <button 
          :class="['tab-btn', { active: activeTab === 'quests' }]" 
          @click="activeTab = 'quests'"
        >
          Quests
        </button>
        <button 
          :class="['tab-btn', { active: activeTab === 'awards' }]" 
          @click="activeTab = 'awards'"
        >
          Awards
        </button>
      </div>

      <div class="quests-body">
        <template v-if="activeTab === 'quests'">
          <div class="quests-section">
            <h3><span class="section-icon">📜</span> Main Quests</h3>
            <div v-if="mainQuests.length === 0" class="empty-state">No main quests available.</div>
            <div v-for="quest in mainQuests" :key="quest.id" :class="['quest-card', quest.status]">
              <div class="quest-info">
                <div class="quest-header">
                  <div class="title-group">
                    <i v-if="quest.status === 'completed'" class="ra ra-circle section-icon text-emerald-500 mr-2"></i>
                    <span class="quest-title">{{ quest.title }}</span>
                  </div>
                  <span class="quest-reward">{{ quest.exp_reward }} EXP</span>
                </div>
                <p class="quest-desc">{{ quest.description }}</p>
                <div class="quest-footer">
                  <div class="status-badge" :class="quest.status">
                    <span class="status-dot"></span>
                    {{ (quest.status || 'open').toUpperCase() }}
                  </div>
                  <button 
                    v-if="!quest.status || quest.status === 'open'" 
                    class="track-btn" 
                    :class="{ active: trackedQuestId === quest.id }"
                    @click="toggleTrack(quest.id)"
                  >
                    {{ trackedQuestId === quest.id ? 'Tracking' : 'Track' }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="quests-section">
            <h3><span class="section-icon">⚔️</span> Side Quests</h3>
            <div v-if="sideQuests.length === 0" class="empty-state">No side quests available.</div>
            <div v-for="quest in sideQuests" :key="quest.id" :class="['quest-card', quest.status]">
              <div class="quest-info">
                <div class="quest-header">
                  <div class="title-group">
                    <i v-if="quest.status === 'completed'" class="ra ra-circle section-icon text-emerald-500 mr-2"></i>
                    <span class="quest-title">{{ quest.title }}</span>
                  </div>
                  <span class="quest-reward">{{ quest.exp_reward }} EXP</span>
                </div>
                <p class="quest-desc">{{ quest.description }}</p>
                <div class="quest-footer">
                  <div class="status-badge" :class="quest.status">
                    <span class="status-dot"></span>
                    {{ (quest.status || 'open').toUpperCase() }}
                  </div>
                  <button 
                    v-if="!quest.status || quest.status === 'open'" 
                    class="track-btn" 
                    :class="{ active: trackedQuestId === quest.id }"
                    @click="toggleTrack(quest.id)"
                  >
                    {{ trackedQuestId === quest.id ? 'Tracking' : 'Track' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </template>

        <template v-else-if="activeTab === 'awards'">
          <div class="awards-grid">
            <div v-if="awards.length === 0" class="empty-state">No awards defined for this adventure.</div>
            <div v-for="award in awards" :key="award.key" :class="['award-tile', award.tier, { earned: award.is_earned, locked: !award.is_earned }]">
              <div class="award-icon-wrapper">
                <i class="ra ra-trophy award-icon"></i>
                <div v-if="award.is_earned" class="earned-check">
                  <i class="ra ra-circle"></i>
                </div>
              </div>
              <div class="award-content">
                <div class="award-header">
                  <span class="award-title">{{ award.title }}</span>
                  <span class="award-tier">{{ award.tier }}</span>
                </div>
                <p class="award-desc">{{ award.description }}</p>
                <div v-if="!award.is_earned" class="award-requirement">
                  <span class="req-label">Requirement:</span>
                  <span class="req-text">{{ award.requirement }}</span>
                </div>
                <div v-else class="earned-label">EARNED</div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "QuestsModal",
  props: {
    isOpen: Boolean,
    quests: {
      type: Array,
      default: () => []
    },
    awards: {
      type: Array,
      default: () => []
    },
    trackedQuestId: String
  },
  emits: ["close", "track-quest"],
  data() {
    return {
      activeTab: 'quests'
    };
  },
  computed: {
    mainQuests() {
      return this.quests.filter(q => q.is_main);
    },
    sideQuests() {
      return this.quests.filter(q => !q.is_main);
    }
  },
  methods: {
    close() {
      this.$emit("close");
    },
    toggleTrack(questId) {
      this.$emit("track-quest", questId === this.trackedQuestId ? null : questId);
    }
  }
};
</script>

<style scoped>
.quests-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  backdrop-filter: blur(8px);
}

.quests-modal-content {
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  background: linear-gradient(135deg, rgba(30, 30, 45, 0.95), rgba(15, 15, 25, 0.98));
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
  overflow: hidden;
  animation: modal-enter 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes modal-enter {
  from { transform: scale(0.9) translateY(30px); opacity: 0; }
  to { transform: scale(1) translateY(0); opacity: 1; }
}

.modal-header {
  padding: 20px 25px;
  background: rgba(255, 255, 255, 0.03);
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 15px;
}

.header-icon {
  width: 32px;
  height: 32px;
  filter: drop-shadow(0 0 8px rgba(124, 58, 237, 0.5));
}

.modal-header h2 {
  margin: 0;
  font-family: 'Outfit', sans-serif;
  color: #fff;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.close-btn {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.5);
  font-size: 28px;
  cursor: pointer;
  transition: color 0.2s;
}

.close-btn:hover {
  color: #fff;
}

.quests-body {
  padding: 25px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.quests-section h3 {
  margin-top: 0;
  margin-bottom: 15px;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: rgba(255, 255, 255, 0.4);
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-icon {
  font-style: normal;
  opacity: 0.8;
}

.empty-state {
  padding: 20px;
  text-align: center;
  color: rgba(255, 255, 255, 0.2);
  border: 1px dashed rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  font-style: italic;
}

.quest-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 15px;
  padding: 18px;
  margin-bottom: 15px;
  transition: all 0.2s;
}

.quest-card:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.1);
}

.quest-card.completed {
  opacity: 0.6;
  background: rgba(0, 0, 0, 0.2);
}

.title-group {
  display: flex;
  align-items: center;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 1px;
  padding: 4px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.3);
}

.status-badge.completed {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 8px currentColor;
}

.quest-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}

.quest-title {
  font-weight: 600;
  color: #e2e8f0;
  font-size: 1.1rem;
}

.quest-reward {
  font-size: 0.85rem;
  background: rgba(124, 58, 237, 0.2);
  color: #a78bfa;
  padding: 4px 10px;
  border-radius: 20px;
  font-weight: 600;
}

.quest-desc {
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.95rem;
  line-height: 1.5;
  margin: 0 0 15px 0;
}

.quest-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.track-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #fff;
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.track-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.track-btn.active {
  background: #7c3aed;
  border-color: #7c3aed;
  box-shadow: 0 0 15px rgba(124, 58, 237, 0.4);
}

.modal-tabs {
  display: flex;
  padding: 0 25px;
  background: rgba(255, 255, 255, 0.02);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.tab-btn {
  padding: 12px 20px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: rgba(255, 255, 255, 0.4);
  font-size: 9px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
}

.tab-btn:hover {
  color: rgba(255, 255, 255, 0.8);
}

.tab-btn.active {
  color: #7c3aed;
  border-bottom-color: #7c3aed;
}

.awards-grid {
  display: grid;
  grid-template-cols: 1fr;
  gap: 20px;
}

.award-tile {
  display: flex;
  gap: 20px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 15px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.award-tile:hover {
  background: rgba(255, 255, 255, 0.05);
  transform: translateY(-2px);
}

.award-tile.earned {
  border-color: rgba(16, 185, 129, 0.3);
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.05), rgba(16, 185, 129, 0.02));
}

.award-tile.locked {
  opacity: 0.6;
  filter: grayscale(0.45);
}

.award-tile.locked .award-title,
.award-tile.locked .award-desc,
.award-tile.locked .award-tier,
.award-tile.locked .req-text {
  color: rgba(255, 255, 255, 0.55);
}

.award-icon-wrapper {
  position: relative;
  width: 60px;
  height: 60px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
}

.award-icon {
  font-size: 32px;
}

.bronze .award-icon { color: #cd7f32; filter: drop-shadow(0 0 10px rgba(205, 127, 50, 0.4)); }
.silver .award-icon { color: #c0c0c0; filter: drop-shadow(0 0 10px rgba(192, 192, 192, 0.4)); }
.gold .award-icon { color: #ffd700; filter: drop-shadow(0 0 10px rgba(255, 215, 0, 0.4)); }

.earned-check {
  position: absolute;
  top: -5px;
  right: -5px;
  width: 20px;
  height: 20px;
  background: #10b981;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  box-shadow: 0 0 10px rgba(16, 185, 129, 0.5);
}

.award-content {
  flex-grow: 1;
}

.award-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.award-title {
  font-weight: 600;
  color: #fff;
  font-size: 1.1rem;
}

.award-tier {
  font-size: 0.7rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  opacity: 0.5;
}

.award-desc {
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.9rem;
  margin-bottom: 12px;
}

.award-requirement {
  font-size: 0.8rem;
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.req-label {
  color: rgba(255, 255, 255, 0.3);
  margin-right: 8px;
  font-weight: 600;
}

.req-text {
  color: rgba(255, 255, 255, 0.7);
}

.earned-label {
  display: inline-block;
  padding: 4px 12px;
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
  border-radius: 20px;
  font-size: 0.7rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

/* Custom Scrollbar */
.quests-body::-webkit-scrollbar {
  width: 6px;
}

.quests-body::-webkit-scrollbar-track {
  background: transparent;
}

.quests-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 10px;
}

.quests-body::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
