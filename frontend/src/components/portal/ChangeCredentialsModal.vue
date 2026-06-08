<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { authState, setToken } from '@/store/auth'
import { api } from '@/composables/useApi'

const props = defineProps<{
  isOpen: boolean
}>()

const emit = defineEmits(['close'])

const currentPassword = ref('')
const newUsername = ref('')
const newPassword = ref('')
const confirmPassword = ref('')

const error = ref('')
const success = ref('')
const isSubmitting = ref(false)

// Reset / Initialize fields when modal opens
watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      newUsername.value = authState.user?.username || ''
      currentPassword.value = ''
      newPassword.value = ''
      confirmPassword.value = ''
      error.value = ''
      success.value = ''
    }
  }
)

const hasChanges = computed(() => {
  const usernameChanged = newUsername.value.trim() !== authState.user?.username
  const passwordFilled = newPassword.value.length > 0
  return usernameChanged || passwordFilled
})

const isFormValid = computed(() => {
  if (!currentPassword.value) return false
  if (!hasChanges.value) return false
  if (newPassword.value && newPassword.value !== confirmPassword.value) return false
  if (newPassword.value && newPassword.value.length < 4) return false
  if (newUsername.value && !newUsername.value.trim()) return false
  return true
})

async function handleSubmit() {
  if (!isFormValid.value) return

  isSubmitting.value = true
  error.value = ''
  success.value = ''

  try {
    const payload: { current_password: string; username?: string; password?: string } = {
      current_password: currentPassword.value,
    }

    if (newUsername.value.trim() !== authState.user?.username) {
      payload.username = newUsername.value.trim()
    }

    if (newPassword.value) {
      payload.password = newPassword.value
    }

    const response = await api.updateMyCredentials(payload)

    if (response.access_token) {
      setToken(response.access_token)
    }

    authState.user = response.user
    
    success.value = 'Credentials changed successfully!'
    
    // Auto close after 1.5 seconds
    setTimeout(() => {
      emit('close')
    }, 1500)
  } catch (err: any) {
    console.error('Failed to update credentials:', err)
    error.value = err.message || 'Failed to change credentials.'
  } finally {
    isSubmitting.value = false
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
    <div v-if="isOpen" class="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-[#02060c]/80 backdrop-blur-sm">
      <div 
        class="w-full max-w-md bg-[#0a111c] border border-white/10 rounded-2xl shadow-2xl overflow-hidden relative"
        @click.stop
      >
        <!-- Decoration top border -->
        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-aether-primary/50 via-purple-500/50 to-aether-primary/50"></div>
        
        <!-- Header -->
        <div class="px-8 pt-8 pb-4 flex items-center gap-3">
          <div class="p-2.5 rounded-xl bg-white/5 border border-white/10 text-aether-primary">
            <i class="ra ra-gear text-lg"></i>
          </div>
          <div>
            <h2 class="text-xl font-black text-white font-display tracking-tight">Change Credentials</h2>
            <p class="text-[11px] text-slate-500 font-bold uppercase tracking-wider">Manage Account Security</p>
          </div>
        </div>

        <!-- Form Content -->
        <form @submit.prevent="handleSubmit" class="px-8 pb-8 pt-2 space-y-4">
          
          <!-- Current Password -->
          <div class="space-y-1.5">
            <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest">Current Password</label>
            <div class="relative">
              <i class="ra ra-hood absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm"></i>
              <input 
                v-model="currentPassword"
                type="password"
                required
                autocomplete="current-password"
                placeholder="Enter current password..."
                class="w-full bg-white/5 border border-white/10 rounded-xl py-2.5 pl-10 pr-4 text-xs text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
              />
            </div>
          </div>

          <div class="border-t border-white/5 my-4"></div>

          <!-- New Username -->
          <div class="space-y-1.5">
            <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest">New Username</label>
            <div class="relative">
              <i class="ra ra-person absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm"></i>
              <input 
                v-model="newUsername"
                type="text"
                placeholder="New username..."
                class="w-full bg-white/5 border border-white/10 rounded-xl py-2.5 pl-10 pr-4 text-xs text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
              />
            </div>
          </div>

          <!-- New Password -->
          <div class="space-y-1.5">
            <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest">New Password (optional)</label>
            <div class="relative">
              <i class="ra ra-hood absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm"></i>
              <input 
                v-model="newPassword"
                type="password"
                autocomplete="new-password"
                placeholder="New password (min. 4 characters)..."
                class="w-full bg-white/5 border border-white/10 rounded-xl py-2.5 pl-10 pr-4 text-xs text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
              />
            </div>
          </div>

          <!-- Confirm Password -->
          <div v-if="newPassword" class="space-y-1.5">
            <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest">Confirm New Password</label>
            <div class="relative">
              <i class="ra ra-hood absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm"></i>
              <input 
                v-model="confirmPassword"
                type="password"
                autocomplete="new-password"
                placeholder="Confirm password..."
                class="w-full bg-white/5 border border-white/10 rounded-xl py-2.5 pl-10 pr-4 text-xs text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all"
              />
            </div>
            <p v-if="newPassword && confirmPassword && newPassword !== confirmPassword" class="text-[10px] text-red-400 font-bold">
              Passwords do not match.
            </p>
          </div>

          <!-- Error / Success messages -->
          <Transition
            enter-active-class="transition duration-200 ease-out"
            enter-from-class="transform -translate-y-2 opacity-0"
            enter-to-class="transform translate-y-0 opacity-100"
          >
            <div v-if="error" class="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-bold text-center">
              {{ error }}
            </div>
            <div v-else-if="success" class="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-aether-primary text-xs font-bold text-center">
              {{ success }}
            </div>
          </Transition>

          <!-- Footer Buttons -->
          <div class="pt-4 flex items-center justify-end gap-3">
            <button 
              type="button"
              @click="emit('close')"
              class="px-5 py-2.5 rounded-xl bg-white/5 border border-white/10 text-xxs font-black text-slate-300 uppercase tracking-widest hover:bg-white/10 hover:border-white/20 transition-all"
            >
              Cancel
            </button>
            <button 
              type="submit"
              :disabled="!isFormValid || isSubmitting"
              class="px-5 py-2.5 rounded-xl bg-aether-primary border border-aether-primary/20 text-xxs font-black text-[#081425] uppercase tracking-widest hover:bg-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-[0_0_15px_rgba(78,222,163,0.3)] flex items-center gap-1.5"
            >
              <i v-if="isSubmitting" class="ra ra-cycle animate-spin text-xs"></i>
              <span>Save</span>
            </button>
          </div>

        </form>
      </div>

      <!-- Backdrop click -->
      <div class="absolute inset-0 z-[-1]" @click="emit('close')"></div>
    </div>
  </Transition>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }
.ra { font-family: 'rpgawesome' !important; }
</style>
