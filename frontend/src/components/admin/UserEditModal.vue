<script setup lang="ts">
import { ref, watch } from 'vue'

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

const editingUser = ref({ ...props.user })

watch(() => props.user, (newUser) => {
  editingUser.value = { ...newUser }
}, { deep: true })

const handleSubmit = () => {
  emit('save', editingUser.value)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="fixed inset-0 z-[110] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/90 backdrop-blur-md" @click="emit('close')"></div>
      <div class="relative w-full max-w-lg bg-[#0a111c] border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden animate-fade-in">
        <div class="p-10">
          <h2 class="text-2xl font-black text-white font-display mb-8">
            {{ isEditingExisting ? 'Edit Domain Dweller' : 'Summon New Dweller' }}
          </h2>

          <form @submit.prevent="handleSubmit" class="space-y-6">
            <div class="space-y-2">
              <label class="text-xxs font-black text-slate-500 uppercase tracking-widest">Username</label>
              <input v-model="editingUser.username" type="text" required class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white outline-none focus:border-red-500/50" />
            </div>

            <div class="space-y-2">
              <label class="text-xxs font-black text-slate-500 uppercase tracking-widest">
                {{ isEditingExisting ? 'Reset Password (optional)' : 'Master Password' }}
              </label>
              <input v-model="editingUser.password" type="password" :required="!isEditingExisting" class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white outline-none focus:border-red-500/50" />
            </div>

            <div class="space-y-2">
              <label class="text-xxs font-black text-slate-500 uppercase tracking-widest">Role</label>
              <select v-model="editingUser.role" class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white outline-none focus:border-red-500/50">
                <option value="user">User (Storyteller)</option>
                <option value="admin">Admin (World Weaver)</option>
              </select>
            </div>

            <div class="flex gap-4 pt-4">
              <button type="button" @click="emit('close')" class="flex-1 py-3 text-slate-500 font-bold hover:text-white transition-colors">Cancel</button>
              <button type="submit" :disabled="isSubmitting" class="flex-[2] btn-primary !bg-red-600 hover:!bg-red-500 shadow-red-900/20">
                {{ isSubmitting ? 'Weaving...' : 'Save Soul' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.4s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
