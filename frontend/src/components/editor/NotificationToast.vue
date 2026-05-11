<script setup lang="ts">
interface Notification {
  id: number
  message: string
  type: 'error' | 'success' | 'info'
}

defineProps<{
  notifications: Notification[]
}>()

const emit = defineEmits<{
  (e: 'close', id: number): void
}>()
</script>

<template>
  <Teleport to="body">
    <div class="fixed bottom-8 right-8 z-[300] flex flex-col gap-3 pointer-events-none">
      <TransitionGroup name="notif">
        <div 
          v-for="n in notifications" 
          :key="n.id"
          :class="[
            'pointer-events-auto px-6 py-4 rounded-2xl border backdrop-blur-2xl shadow-2xl flex items-center gap-4 min-w-[320px] max-w-md animate-notif-in',
            n.type === 'error' ? 'bg-red-500/10 border-red-500/20 text-red-400' : 
            n.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' :
            'bg-blue-500/10 border-blue-500/20 text-blue-400'
          ]"
        >
          <i :class="[
            'text-lg',
            n.type === 'error' ? 'ra ra-cancel' : 
            n.type === 'success' ? 'ra ra-circle' : 'ra ra-light-bulb'
          ]"></i>
          <div class="flex-grow">
            <p class="text-xs font-black uppercase tracking-widest opacity-50">{{ n.type }}</p>
            <p class="text-xs font-bold leading-relaxed">{{ n.message }}</p>
          </div>
          <button @click="emit('close', n.id)" class="opacity-50 hover:opacity-100 transition-opacity">
            <i class="ra ra-cancel text-xs"></i>
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.notif-enter-active, .notif-leave-active { transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.notif-enter-from { opacity: 0; transform: translateX(50px) scale(0.9); }
.notif-leave-to { opacity: 0; transform: translateX(50px) scale(0.9); }

@keyframes notifIn {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}

.animate-notif-in {
  animation: notifIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
</style>
