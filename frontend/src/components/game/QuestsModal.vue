<template>
  <div
    v-if="isOpen"
    class="quests-modal-overlay tw-skin tw-dialog-backdrop"
    :data-skin="activeSkin"
    :style="skinStyle"
    @click.self="close"
  >
    <div class="quests-modal-content tw-dialog" role="dialog" aria-modal="true" aria-label="Quest Log">
      <header class="modal-header tw-dialog-header">
        <div class="header-title">
          <img src="@/assets/svg/fantasy-spellbook.svg" alt="" class="header-icon" />
          <h3 class="tw-dialog-title text-xl md:text-3xl">Quest Log</h3>
        </div>
        <button type="button" class="tw-dialog-icon-button p-2" aria-label="Close" @click="close">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
          </svg>
        </button>
      </header>

      <div class="modal-tabs tw-dialog-divider" role="tablist">
        <button
          type="button"
          role="tab"
          :aria-selected="activeTab === 'quests'"
          :class="['tw-tab', { 'tw-tab--active': activeTab === 'quests' }]"
          @click="activeTab = 'quests'"
        >
          Quests
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="activeTab === 'awards'"
          :class="['tw-tab', { 'tw-tab--active': activeTab === 'awards' }]"
          @click="activeTab = 'awards'"
        >
          Awards
        </button>

        <label class="tw-muted ml-auto flex items-center gap-2 cursor-pointer text-xxs md:text-xs font-bold uppercase tracking-wider select-none pr-2">
          <input
            type="checkbox"
            :checked="!trackerHidden"
            @change="$emit('toggle-tracker', !$event.target.checked)"
            class="tracker-checkbox w-3.5 h-3.5 cursor-pointer"
          />
          Tracker on Screen
        </label>
      </div>

      <div class="quests-body tw-dialog-scroll">
        <template v-if="activeTab === 'quests'">
          <div class="quests-section" v-if="activeSequence">
            <h3><span class="section-icon">📜</span> Current Chapter</h3>
            <div class="quest-card tw-card open">
              <div class="quest-info">
                <div class="quest-header">
                  <div class="title-group">
                    <span class="quest-title">{{ activeSequence.title }}</span>
                  </div>
                </div>
                <p class="quest-desc" v-html="formatEntityRefs(activeSequence.description)"></p>
                <div class="quest-footer">
                  <div class="status-badge open">
                    <span class="status-dot"></span>
                    ACTIVE
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="quests-section">
            <h3><span class="section-icon">⚔️</span> Quests</h3>
            <div v-if="quests.length === 0" class="empty-state tw-dialog-slot">No quests available.</div>
            <div v-for="quest in quests" :key="quest.id" :class="['quest-card', 'tw-card', quest.status]">
              <div class="quest-info">
                <div class="quest-header">
                  <div class="title-group">
                    <i v-if="quest.status === 'completed'" class="ra ra-circle section-icon text-emerald-500 mr-2"></i>
                    <span class="quest-title">{{ quest.title }}</span>
                  </div>
                  <span class="quest-reward">{{ quest.exp_reward }} EXP</span>
                </div>
                <p class="quest-desc" v-html="formatEntityRefs(quest.description || quest.goal)"></p>
                <div class="quest-footer">
                  <div class="status-badge" :class="quest.status">
                    <span class="status-dot"></span>
                    {{ (quest.status || 'open').toUpperCase() }}
                  </div>
                  <button 
                    v-if="!quest.status || quest.status === 'open'" 
                    class="tw-dialog-button"
                    :class="{ 'tw-dialog-button--ghost': trackedQuestId !== quest.id }"
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
            <div v-if="awards.length === 0" class="empty-state tw-dialog-slot">No awards defined for this adventure.</div>
            <div v-for="award in awards" :key="award.key" :class="['award-tile', 'tw-card', award.tier, { earned: award.is_earned, locked: !award.is_earned }]">
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
                <p class="award-desc" v-html="formatEntityRefs(award.description)"></p>
                <div v-if="award.is_earned" class="earned-label">EARNED</div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import { formatEntityRefs } from '@/utils/entityRefs'
import { useDialogSkin } from '@/skins/dialogSkin'

export default {
  name: "QuestsModal",
  props: {
    isOpen: Boolean,
    quests: {
      type: Array,
      default: () => []
    },
    activeSequence: {
      type: Object,
      default: null
    },
    awards: {
      type: Array,
      default: () => []
    },
    trackedQuestId: String,
    trackerHidden: Boolean
  },
  emits: ["close", "track-quest", "toggle-tracker"],
  setup() {
    return useDialogSkin();
  },
  data() {
    return {
      activeTab: 'quests'
    };
  },
  computed: {
  },
  methods: {
    formatEntityRefs(text) {
      return formatEntityRefs(text);
    },
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
  inset: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.quests-modal-content {
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: modal-enter 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes modal-enter {
  from { transform: scale(0.9) translateY(30px); opacity: 0; }
  to { transform: scale(1) translateY(0); opacity: 1; }
}

.modal-header {
  padding: 20px 25px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 15px;
}

.header-icon {
  width: 64px;
  height: 64px;
  filter: drop-shadow(0 0 8px color-mix(in srgb, var(--tw-accent) 50%, transparent));
}

.modal-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 25px;
  border-bottom-width: 1px;
}

.tracker-checkbox {
  accent-color: var(--tw-accent);
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
  font-family: var(--tw-tab-font);
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: var(--tw-panel-muted);
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
  font-style: italic;
}

.quest-card {
  padding: 18px;
  margin-bottom: 15px;
}

.quest-card.open {
  border-left: 4px solid var(--tw-accent);
}

.quest-card.completed {
  opacity: 0.6;
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
  background: color-mix(in srgb, currentColor 10%, transparent);
  color: var(--tw-card-muted);
}

.status-badge.open {
  color: var(--tw-accent);
}

.status-badge.completed {
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
  gap: 12px;
  margin-bottom: 10px;
}

.quest-title {
  font-family: var(--tw-font-overlay-title);
  font-weight: 600;
  font-size: 1.15rem;
}

.quest-reward {
  flex-shrink: 0;
  font-size: 0.85rem;
  background: color-mix(in srgb, var(--tw-accent) 18%, transparent);
  color: var(--tw-accent);
  padding: 4px 10px;
  border-radius: 20px;
  font-weight: 700;
}

.quest-desc {
  color: var(--tw-card-ink);
  font-family: var(--tw-font-body);
  font-size: 1.05rem;
  line-height: 1.6;
  margin: 0 0 15px 0;
  opacity: 0.9;
}

.quest-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.awards-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.award-tile {
  display: flex;
  gap: 20px;
  padding: 20px;
}

.award-tile:hover {
  transform: translateY(-2px);
}

.award-tile.earned {
  border-color: rgba(16, 185, 129, 0.5);
}

.award-tile.locked {
  opacity: 0.6;
  filter: grayscale(0.45);
}

.award-icon-wrapper {
  position: relative;
  width: 60px;
  height: 60px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--tw-card-ink) 8%, transparent);
  border-radius: 12px;
}

.award-icon {
  font-size: 32px;
}

.bronze .award-icon { color: #cd7f32; filter: drop-shadow(0 0 10px rgba(205, 127, 50, 0.4)); }
.silver .award-icon { color: #a8a8a8; filter: drop-shadow(0 0 10px rgba(192, 192, 192, 0.4)); }
.gold .award-icon { color: #e6b800; filter: drop-shadow(0 0 10px rgba(255, 215, 0, 0.4)); }
.negative .award-icon { color: #ef4444; filter: drop-shadow(0 0 10px rgba(239, 68, 68, 0.5)); }

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
  min-width: 0;
}

.award-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.award-title {
  font-family: var(--tw-font-overlay-title);
  font-weight: 600;
  font-size: 1.1rem;
}

.award-tier {
  font-size: 0.7rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--tw-card-muted);
}

.award-desc {
  color: var(--tw-card-muted);
  font-size: 0.9rem;
  margin-bottom: 12px;
}

.earned-label {
  display: inline-block;
  padding: 4px 12px;
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border-radius: 20px;
  font-size: 0.7rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}
</style>
