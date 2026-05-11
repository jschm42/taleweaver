<script setup lang="ts">
const props = defineProps<{
  usersList: any[]
}>()

const emit = defineEmits<{
  (e: 'addUser'): void
  (e: 'editUser', user: any): void
  (e: 'removeUser', user: any): void
}>()
</script>

<template>
  <div class="space-y-8 animate-fade-in">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-4xl font-extrabold text-white mb-2">User Management</h1>
        <p class="text-slate-400 text-sm">Create and manage accounts for your TaleWeaver domain.</p>
      </div>
      <button @click="emit('addUser')" class="px-6 py-3 bg-red-600 hover:bg-red-500 text-white font-bold rounded-xl shadow-lg shadow-red-900/20 flex items-center gap-2 transition-all">
        <i class="ra ra-plus"></i> Add User
      </button>
    </div>

    <div class="bg-slate-900 border border-slate-800 rounded-3xl overflow-hidden shadow-2xl">
      <table class="w-full text-left">
        <thead>
          <tr class="border-b border-slate-800 bg-slate-950/50">
            <th class="px-6 py-4 text-xxs font-black text-slate-500 uppercase tracking-widest">User</th>
            <th class="px-6 py-4 text-xxs font-black text-slate-500 uppercase tracking-widest">Role</th>
            <th class="px-6 py-4 text-xxs font-black text-slate-500 uppercase tracking-widest text-right">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-800">
          <tr v-for="user in usersList" :key="user.id" class="hover:bg-white/[0.02] transition-colors group">
            <td class="px-6 py-4">
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-full bg-white/5 border border-white/10 overflow-hidden">
                  <img v-if="user.profile_image_url" :src="user.profile_image_url" class="w-full h-full object-cover" />
                  <div v-else class="w-full h-full flex items-center justify-center text-slate-600">
                    <i class="ra ra-hood"></i>
                  </div>
                </div>
                <span class="font-bold text-white">{{ user.username }}</span>
              </div>
            </td>
            <td class="px-6 py-4">
              <span :class="['px-2 py-0.5 rounded text-xxs font-black uppercase tracking-tighter', user.role === 'admin' ? 'bg-red-500/10 text-red-400' : 'bg-blue-500/10 text-blue-400']">
                {{ user.role }}
              </span>
            </td>
            <td class="px-6 py-4 text-right">
              <div class="flex items-center justify-end gap-2">
                <button @click="emit('editUser', user)" class="p-2 text-slate-500 hover:text-white transition-colors" title="Edit">
                  <i class="ra ra-quill-ink"></i>
                </button>
                <button @click="emit('removeUser', user)" class="p-2 text-slate-500 hover:text-red-400 transition-colors" title="Delete">
                  <i class="ra ra-cancel"></i>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
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
