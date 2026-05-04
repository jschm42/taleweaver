<template>
  <div v-if="show" class="game-over-overlay">
    <div class="game-over-content glassmorphism">
      <div class="vignette"></div>
      
      <div class="icon-container">
        <div class="skull-glow"></div>
        <div class="skull-icon">💀</div>
      </div>

      <h1>GAME OVER</h1>
      <p class="reason-text">{{ reason || 'Your journey has come to an end.' }}</p>

      <div class="action-buttons">
        <button class="continue-btn" @click="$emit('continue')">
          <span class="btn-text">Continue Anyway</span>
          <span class="btn-subtext">Fate is not set in stone</span>
        </button>
        <button class="menu-btn" @click="$emit('close')">Back to Menu</button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "GameOverScreen",
  props: {
    show: Boolean,
    reason: String
  },
  emits: ["close", "continue"]
};
</script>

<style scoped>
.game-over-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(20, 0, 0, 0.95);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 3000;
  backdrop-filter: blur(10px);
  animation: fade-in 1s ease-out;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.game-over-content {
  width: 90%;
  max-width: 550px;
  background: linear-gradient(135deg, rgba(40, 10, 10, 0.9), rgba(20, 5, 5, 0.95));
  border: 2px solid rgba(239, 68, 68, 0.3);
  border-radius: 40px;
  padding: 60px 40px;
  text-align: center;
  position: relative;
  overflow: hidden;
  box-shadow: 0 0 100px rgba(220, 38, 38, 0.3);
  animation: content-pop 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.vignette {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: radial-gradient(circle, transparent 40%, rgba(0,0,0,0.8) 100%);
  pointer-events: none;
}

@keyframes content-pop {
  from { transform: scale(0.8) translateY(20px); opacity: 0; }
  to { transform: scale(1) translateY(0); opacity: 1; }
}

.icon-container {
  position: relative;
  width: 100px;
  height: 100px;
  margin: 0 auto 30px;
}

.skull-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 140%;
  height: 140%;
  background: radial-gradient(circle, rgba(220, 38, 38, 0.4), transparent 70%);
  animation: pulse-red 3s infinite ease-in-out;
}

@keyframes pulse-red {
  0%, 100% { opacity: 0.4; transform: translate(-50%, -50%) scale(1); }
  50% { opacity: 0.8; transform: translate(-50%, -50%) scale(1.3); }
}

.skull-icon {
  font-size: 80px;
  position: relative;
  filter: drop-shadow(0 0 15px rgba(220, 38, 38, 0.8));
  animation: shake 4s infinite ease-in-out;
}

@keyframes shake {
  0%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(-5deg); }
  75% { transform: rotate(5deg); }
}

h1 {
  font-family: 'Outfit', sans-serif;
  font-size: 3.5rem;
  font-weight: 900;
  letter-spacing: 8px;
  color: #ef4444;
  margin: 0 0 20px 0;
  text-shadow: 0 0 30px rgba(239, 68, 68, 0.6);
}

.reason-text {
  color: rgba(255, 255, 255, 0.8);
  font-size: 1.2rem;
  line-height: 1.6;
  margin-bottom: 50px;
  font-style: italic;
  max-width: 400px;
  margin-left: auto;
  margin-right: auto;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 15px;
  position: relative;
  z-index: 2;
}

.continue-btn {
  background: linear-gradient(135deg, #ef4444, #991b1b);
  color: #fff;
  border: none;
  padding: 14px 40px;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  flex-direction: column;
  align-items: center;
  box-shadow: 0 10px 20px rgba(239, 68, 68, 0.3);
}

.continue-btn:hover {
  transform: translateY(-3px);
  box-shadow: 0 15px 30px rgba(239, 68, 68, 0.5);
  filter: brightness(1.1);
}

.btn-text {
  font-size: 1.2rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.btn-subtext {
  font-size: 0.8rem;
  opacity: 0.7;
  font-weight: 400;
}

.menu-btn {
  background: transparent;
  color: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 12px;
  border-radius: 12px;
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.3s;
}

.menu-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.4);
}
</style>

