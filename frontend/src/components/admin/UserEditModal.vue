<script setup lang="ts">
import { ref, watch } from 'vue'
import UserKeyPolicyEditor from './UserKeyPolicyEditor.vue'

const props = defineProps<{
  isOpen: boolean
  isEditingExisting: boolean
  user: any
  isSubmitting: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', user: any): void
}>()

// New accounts created by an admin are active unless unchecked.
const toEditable = (user: any) => ({ ...user, email: user?.email ?? '', is_active: user?.is_active ?? true })

const editingUser = ref(toEditable(props.user))
const showPassword = ref(false)

watch(() => props.user, (newUser) => {
  editingUser.value = toEditable(newUser)
  showPassword.value = false
}, { deep: true })

const handleSubmit = () => {
  if (!editingUser.value.username?.trim()) return
  // The backend rejects an empty string as email; null leaves it unchanged.
  emit('save', { ...editingUser.value, email: editingUser.value.email?.trim() || null })
}
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="fixed inset-0 z-[110] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/85 backdrop-blur-sm" @click="emit('close')"></div>
      <div class="relative max-h-[90vh] w-full max-w-lg overflow-y-auto bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl p-6 sm:p-8 animate-fade-in">
        <!-- Header -->
        <div class="flex items-center justify-between pb-4 mb-6 border-b border-slate-800">
          <div>
            <h2 class="text-xl font-bold text-white">
              {{ isEditingExisting ? 'Edit Realm Dweller' : 'Summon New Dweller' }}
            </h2>
            <p class="text-xs text-slate-400">Manage account credentials and role authorization.</p>
          </div>
          <button @click="emit('close')" class="p-1.5 text-slate-500 hover:text-white rounded-lg transition-colors">
            <i class="ra ra-cancel text-sm"></i>
          </button>
        </div>

        <form @submit.prevent="handleSubmit" class="space-y-5">
          <!-- Username -->
          <div class="space-y-1.5">
            <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider">
              Username <span class="text-rose-400">*</span>
            </label>
            <input 
              v-model="editingUser.username" 
              type="text" 
              required 
              minlength="3"
              placeholder="e.g. Jean"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-white text-sm outline-none focus:ring-2 focus:ring-rose-500/50" 
            />
          </div>

          <!-- Email -->
          <div class="space-y-1.5">
            <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider">Email</label>
            <input
              v-model="editingUser.email"
              type="email"
              placeholder="Optional, e.g. jean@example.com"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-white text-sm outline-none focus:ring-2 focus:ring-rose-500/50"
            />
          </div>

          <!-- Password -->
          <div class="space-y-1.5">
            <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider">
              {{ isEditingExisting ? 'Reset Password (leave empty to keep current)' : 'Master Password' }}
              <span v-if="!isEditingExisting" class="text-rose-400">*</span>
            </label>
            <div class="relative">
              <input 
                v-model="editingUser.password" 
                :type="showPassword ? 'text' : 'password'" 
                :required="!isEditingExisting" 
                placeholder="••••••••••••"
                class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-4 pr-11 py-2.5 text-white text-sm font-mono outline-none focus:ring-2 focus:ring-rose-500/50" 
              />
              <button
                type="button"
                @click="showPassword = !showPassword"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 text-xs px-1"
                :title="showPassword ? 'Hide password' : 'Show password'"
              >
                <i :class="['ra', showPassword ? 'ra-eye-shield' : 'ra-eye-slash']"></i>
              </button>
            </div>
          </div>

          <!-- Role Selector (Visual Cards) -->
          <div class="space-y-2">
            <label class="block text-xs font-bold text-slate-400 uppercase tracking-wider">Account Role</label>
            <div class="grid grid-cols-2 gap-3">
              <button
                type="button"
                @click="editingUser.role = 'user'"
                :class="[
                  'p-3.5 rounded-2xl border text-left transition-all',
                  editingUser.role === 'user'
                    ? 'bg-rose-500/10 border-rose-500/40 text-white shadow-sm'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                ]"
              >
                <div class="flex items-center gap-2 mb-1">
                  <i class="ra ra-player text-rose-400"></i>
                  <span class="text-xs font-bold text-white">Storyteller</span>
                </div>
                <p class="text-[11px] text-slate-400 leading-tight">Plays adventures and generates personal campaigns.</p>
              </button>

              <button
                type="button"
                @click="editingUser.role = 'admin'"
                :class="[
                  'p-3.5 rounded-2xl border text-left transition-all',
                  editingUser.role === 'admin'
                    ? 'bg-rose-500/10 border-rose-500/40 text-white shadow-sm'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                ]"
              >
                <div class="flex items-center gap-2 mb-1">
                  <i class="ra ra-crown text-rose-400"></i>
                  <span class="text-xs font-bold text-white">World Weaver</span>
                </div>
                <p class="text-[11px] text-slate-400 leading-tight">Full administrative access to AI models & users.</p>
              </button>
            </div>
          </div>

          <!-- Account Active -->
          <label class="flex items-start gap-3 p-3.5 rounded-2xl border border-slate-800 bg-slate-950 cursor-pointer">
            <input
              v-model="editingUser.is_active"
              type="checkbox"
              class="mt-0.5 h-4 w-4 rounded border-slate-700 bg-slate-900 accent-rose-500 cursor-pointer"
            />
            <span>
              <span class="block text-xs font-bold text-white">Account active</span>
              <span class="block text-[11px] text-slate-400 leading-tight">Inactive accounts cannot log in. Self-registered accounts stay inactive until approved.</span>
            </span>
          </label>

          <UserKeyPolicyEditor
            v-if="isEditingExisting && editingUser.id"
            :key="editingUser.id"
            :user-id="editingUser.id"
            :overrides="editingUser.api_key_policy_overrides"
            :personal-key-providers="editingUser.personal_key_providers"
          />

          <!-- Actions -->
          <div class="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button 
              type="button" 
              @click="emit('close')" 
              class="px-5 py-2.5 rounded-xl border border-slate-800 text-slate-400 hover:text-white hover:bg-slate-800 text-xs font-bold transition-all"
            >
              Cancel
            </button>
            <button 
              type="submit" 
              :disabled="isSubmitting || !editingUser.username?.trim()" 
              class="px-6 py-2.5 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-bold transition-all shadow-lg shadow-rose-900/30 disabled:opacity-50 flex items-center gap-2 cursor-pointer"
            >
              <i v-if="isSubmitting" class="ra ra-cycle animate-spin"></i>
              <i v-else class="ra ra-save"></i>
              <span>{{ isSubmitting ? 'Summoning...' : 'Save Dweller' }}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.3s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
