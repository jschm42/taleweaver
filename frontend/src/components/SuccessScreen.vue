<template>
  <div v-if="show" class="success-screen-overlay">
    <div class="success-content glassmorphism">
      <div class="particles">
        <div v-for="n in 20" :key="n" class="particle"></div>
      </div>
      
      <div class="trophy-container">
        <div class="trophy-glow"></div>
        <img src="@/assets/svg/fantasy-spellbook.svg" alt="Victory" class="victory-icon" />
      </div>

      <h1>Adventure Completed!</h1>
      <p class="congrats-text">Congratulations, hero! You have successfully navigated the challenges of this tale and achieved all major objectives.</p>

      <div class="stats-summary">
        <div class="stat-item">
          <span class="stat-label">TOTAL EXPERIENCE</span>
          <span class="stat-value">{{ totalExp }} EXP</span>
        </div>
      </div>

      <div class="action-buttons">
        <button class="primary-btn" @click="$emit('close')">Back to Menu</button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "SuccessScreen",
  props: {
    show: Boolean,
    totalExp: Number
  },
  emits: ["close"]
};
</script>

<style scoped>
.success-screen-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
  backdrop-filter: blur(15px);
}

.success-content {
  width: 90%;
  max-width: 500px;
  background: radial-gradient(circle at top, rgba(124, 58, 237, 0.2), transparent),
              rgba(20, 20, 30, 0.8);
  border: 1px solid rgba(124, 58, 237, 0.3);
  border-radius: 30px;
  padding: 50px 40px;
  text-align: center;
  position: relative;
  overflow: hidden;
  box-shadow: 0 0 100px rgba(124, 58, 237, 0.2);
  animation: content-pop 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes content-pop {
  from { transform: scale(0.5); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

.trophy-container {
  position: relative;
  width: 120px;
  height: 120px;
  margin: 0 auto 30px;
}

.trophy-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 150%;
  height: 150%;
  background: radial-gradient(circle, rgba(124, 58, 237, 0.6), transparent 70%);
  animation: pulse-glow 2s infinite ease-in-out;
}

@keyframes pulse-glow {
  0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.5; }
  50% { transform: translate(-50%, -50%) scale(1.2); opacity: 0.8; }
}

.victory-icon {
  position: relative;
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 0 20px rgba(124, 58, 237, 0.8));
  animation: float-icon 3s infinite ease-in-out;
}

@keyframes float-icon {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-15px); }
}

h1 {
  font-family: 'Outfit', sans-serif;
  font-size: 2.5rem;
  color: #fff;
  margin: 0 0 15px 0;
  background: linear-gradient(to bottom, #fff, #a78bfa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.congrats-text {
  color: rgba(255, 255, 255, 0.7);
  font-size: 1.1rem;
  line-height: 1.6;
  margin-bottom: 35px;
}

.stats-summary {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 20px;
  padding: 25px;
  margin-bottom: 40px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-label {
  font-size: 0.75rem;
  letter-spacing: 2px;
  color: rgba(255, 255, 255, 0.4);
}

.stat-value {
  font-size: 2rem;
  font-weight: 800;
  color: #7c3aed;
  text-shadow: 0 0 20px rgba(124, 58, 237, 0.5);
}

.primary-btn {
  background: #7c3aed;
  color: #fff;
  border: none;
  padding: 16px 40px;
  border-radius: 12px;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 10px 25px rgba(124, 58, 237, 0.3);
}

.primary-btn:hover {
  background: #6d28d9;
  transform: translateY(-2px);
  box-shadow: 0 15px 30px rgba(124, 58, 237, 0.5);
}

/* Particles */
.particles {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.particle {
  position: absolute;
  width: 4px;
  height: 4px;
  background: #7c3aed;
  border-radius: 50%;
  opacity: 0;
  animation: particle-rise 4s infinite linear;
}

@keyframes particle-rise {
  0% { transform: translateY(100%) translateX(0); opacity: 0; }
  20% { opacity: 0.6; }
  80% { opacity: 0.6; }
  100% { transform: translateY(-20%) translateX(100px); opacity: 0; }
}

/* Randomize particle positions and timing */
.particle:nth-child(1) { left: 10%; animation-delay: 0s; }
.particle:nth-child(2) { left: 20%; animation-delay: 0.5s; }
.particle:nth-child(3) { left: 30%; animation-delay: 1.2s; }
.particle:nth-child(4) { left: 40%; animation-delay: 1.8s; }
.particle:nth-child(5) { left: 50%; animation-delay: 2.5s; }
.particle:nth-child(6) { left: 60%; animation-delay: 3.1s; }
.particle:nth-child(7) { left: 70%; animation-delay: 3.7s; }
.particle:nth-child(8) { left: 80%; animation-delay: 4.2s; }
.particle:nth-child(9) { left: 90%; animation-delay: 4.8s; }
.particle:nth-child(10) { left: 15%; animation-delay: 0.2s; }
</style>
