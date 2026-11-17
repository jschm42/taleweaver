<script setup lang="ts">
import { ref } from 'vue'
import { Check, Copy, KeyRound, Pencil, Trash2, User, UserPlus, X } from 'lucide-vue-next'
import { api } from '@/composables/useApi'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'

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

function overrideCount(user: any): number {
  return Object.keys(user.api_key_policy_overrides || {}).length
}
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Users" description="Accounts on this server, their roles and recovery options.">
      <template #actions>
        <UiButton variant="primary" :icon="UserPlus" @click="emit('addUser')">Add user</UiButton>
      </template>
    </PageHeader>

    <div v-if="resetLink" class="space-y-3 rounded-xl border border-wb-warn/30 bg-wb-warn-soft p-4" role="status">
      <div class="flex items-start justify-between gap-4">
        <div>
          <p class="wb-subheading">Password reset link for {{ resetLink.username }}</p>
          <p class="wb-hint mt-0.5">
            Works once and expires in {{ resetLink.expiresInHours }} hours. Share it privately; it is not shown again.
          </p>
        </div>
        <UiIconButton :icon="X" label="Dismiss" size="sm" @click="resetLink = null" />
      </div>
      <div class="flex flex-col gap-2 sm:flex-row">
        <UiInput
          :model-value="resetLink.url"
          readonly
          aria-label="Password reset link"
          class="wb-mono"
          @focus="($event.target as HTMLInputElement).select()"
        />
        <UiButton :icon="copied ? Check : Copy" @click="copyResetLink">{{ copied ? 'Copied' : 'Copy link' }}</UiButton>
      </div>
    </div>
    <p v-if="resetLinkError" class="wb-body text-wb-danger-text" role="alert">{{ resetLinkError }}</p>

    <UiEmptyState v-if="usersList.length === 0" :icon="User" title="No users yet">
      <template #action>
        <UiButton variant="primary" :icon="UserPlus" @click="emit('addUser')">Add user</UiButton>
      </template>
    </UiEmptyState>

    <UiCard v-else :padded="false">
      <div class="overflow-x-auto">
        <table class="w-full text-left">
          <thead>
            <tr class="border-b border-wb-line">
              <th scope="col" class="wb-label px-5 py-3 !text-wb-muted">User</th>
              <th scope="col" class="wb-label px-5 py-3 !text-wb-muted">Role</th>
              <th scope="col" class="wb-label px-5 py-3 !text-wb-muted">Recovery codes</th>
              <th scope="col" class="wb-label px-5 py-3 !text-wb-muted" title="Personal API keys (names only) and key policy exceptions">Own keys</th>
              <th scope="col" class="px-5 py-3"><span class="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-wb-line">
            <tr v-for="user in usersList" :key="user.id" class="hover:bg-wb-raised/50">
              <td class="px-5 py-3">
                <div class="flex items-center gap-3">
                  <div class="h-8 w-8 shrink-0 overflow-hidden rounded-full border border-wb-line bg-wb-raised">
                    <img v-if="user.profile_image_url" :src="user.profile_image_url" alt="" class="h-full w-full object-cover" />
                    <User v-else class="m-2 h-4 w-4 text-wb-faint" aria-hidden="true" />
                  </div>
                  <span class="wb-body font-medium text-wb-strong">{{ user.username }}</span>
                </div>
              </td>
              <td class="px-5 py-3">
                <UiBadge :tone="user.role === 'admin' ? 'warn' : 'neutral'">{{ user.role === 'admin' ? 'Admin' : 'Player' }}</UiBadge>
              </td>
              <td class="px-5 py-3">
                <span :class="['wb-body', user.recovery_codes_remaining ? 'text-wb-body' : 'text-wb-faint']">
                  {{ user.recovery_codes_remaining ? `${user.recovery_codes_remaining} left` : 'None' }}
                </span>
              </td>
              <td class="px-5 py-3">
                <div class="flex flex-wrap items-center gap-1">
                  <UiBadge v-for="provider in user.personal_key_providers || []" :key="provider" tone="accent">{{ provider }}</UiBadge>
                  <UiBadge v-if="overrideCount(user)" tone="warn" :title="JSON.stringify(user.api_key_policy_overrides)">
                    {{ overrideCount(user) }} {{ overrideCount(user) === 1 ? 'exception' : 'exceptions' }}
                  </UiBadge>
                  <span v-if="!(user.personal_key_providers || []).length && !overrideCount(user)" class="wb-body text-wb-faint">–</span>
                </div>
              </td>
              <td class="px-5 py-3">
                <div class="flex items-center justify-end gap-1">
                  <UiIconButton :icon="Pencil" :label="`Edit ${user.username}`" size="sm" @click="emit('editUser', user)" />
                  <UiIconButton
                    :icon="KeyRound"
                    :label="`Create a password reset link for ${user.username}`"
                    size="sm"
                    :disabled="generatingFor === user.id"
                    @click="createResetLink(user)"
                  />
                  <UiIconButton :icon="Trash2" :label="`Delete ${user.username}`" size="sm" variant="danger" @click="emit('removeUser', user)" />
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </UiCard>
  </div>
</template>
