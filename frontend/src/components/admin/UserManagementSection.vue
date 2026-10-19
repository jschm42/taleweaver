<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/composables/useApi'

defineProps<{
  usersList: any[]
}>()

const emit = defineEmits<{
  (e: 'addUser'): void
  (e: 'editUser', user: any): void
  (e: 'removeUser', user: any): void
}>()

type ResetLink = { username: string, url: string, expiresInHours: number }
const resetLink = ref<ResetLink | null>(null)
const resetLinkError = ref('')
const generatingFor = ref<string | null>(null)
const copied = ref(false)

async function createResetLink(user: any) {
  generatingFor.value = user.id
  resetLinkError.value = ''
  copied.value = false
  try {
    const { token, expires_in_hours } = await api.createPasswordResetLink(user.id)
    const url = new URL(`${import.meta.env.BASE_URL}reset-password`, window.location.origin)
    url.searchParams.set('token', token)
    resetLink.value = { username: user.username, url: url.toString(), expiresInHours: expires_in_hours }
  } catch (err: any) {
    resetLinkError.value = err?.message || 'Failed to create reset link.'
  } finally {
    generatingFor.value = null
  }
}

async function copyResetLink() {
  if (!resetLink.value) return
  try {
    await navigator.clipboard.writeText(resetLink.value.url)
    copied.value = true
  } catch {
    copied.value = false
  }
}
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

    <div v-if="resetLink" class="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-5 space-y-3">
      <div class="flex items-start justify-between gap-4">
        <div>
          <p class="text-sm font-bold text-amber-300">Password reset link for {{ resetLink.username }}</p>
          <p class="text-xs text-slate-400">
            Works once and expires in {{ resetLink.expiresInHours }} hours. Share it privately; it is not shown again.
          </p>
        </div>
        <button class="text-slate-500 hover:text-white" title="Dismiss" @click="resetLink = null">
          <i class="ra ra-cancel"></i>
        </button>
      </div>
      <div class="flex flex-col sm:flex-row gap-2">
        <input
          :value="resetLink.url"
          readonly
          class="flex-1 min-w-0 rounded-xl border border-white/10 bg-black/40 px-3 py-2 font-mono text-xs text-slate-200"
          @focus="($event.target as HTMLInputElement).select()"
        />
        <button class="rounded-xl bg-amber-500/20 px-4 py-2 text-xs font-bold text-amber-200 hover:bg-amber-500/30" @click="copyResetLink">
          {{ copied ? 'Copied' : 'Copy link' }}
        </button>
      </div>
    </div>
    <p v-if="resetLinkError" class="text-sm text-red-400">{{ resetLinkError }}</p>

    <div class="bg-slate-900 border border-slate-800 rounded-3xl overflow-hidden shadow-2xl">
      <table class="w-full text-left">
        <thead>
          <tr class="border-b border-slate-800 bg-slate-950/50">
            <th class="px-6 py-4 text-xxs font-black text-slate-500 uppercase tracking-widest">User</th>
            <th class="px-6 py-4 text-xxs font-black text-slate-500 uppercase tracking-widest">Role</th>
            <th class="px-6 py-4 text-xxs font-black text-slate-500 uppercase tracking-widest">Recovery codes</th>
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
            <td class="px-6 py-4">
              <span :class="['text-xs font-bold', user.recovery_codes_remaining ? 'text-emerald-400' : 'text-slate-600']">
                {{ user.recovery_codes_remaining ? `${user.recovery_codes_remaining} left` : 'None' }}
              </span>
            </td>
            <td class="px-6 py-4 text-right">
              <div class="flex items-center justify-end gap-2">
                <button @click="emit('editUser', user)" class="p-2 text-slate-500 hover:text-white transition-colors" title="Edit">
                  <i class="ra ra-quill-ink"></i>
                </button>
                <button
                  :disabled="generatingFor === user.id"
                  class="p-2 text-slate-500 hover:text-amber-400 transition-colors disabled:opacity-40"
                  title="Create password reset link"
                  @click="createResetLink(user)"
                >
                  <i :class="generatingFor === user.id ? 'ra ra-cycle animate-spin' : 'ra ra-key'"></i>
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
