<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '@/composables/useApi'
import { authState, refreshUser } from '@/store/auth'

export interface ProfileStats {
  adventures: number
  victories: number
  defeats: number
  totalXp: number
  awards: number
}

const props = defineProps<{ stats: ProfileStats, canGenerateAvatar: boolean }>()
const emit = defineEmits<{ (e: 'notify', message: string, type: 'success' | 'error'): void }>()

const user = computed(() => authState.user)
const avatarUrl = computed(() => {
  const url = (user.value?.profile_image_url || '').replace(/\\/g, '/')
  return url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(user.value?.username || 'default')}`
})

const statTiles = computed(() => [
  { label: 'Adventures', value: props.stats.adventures, icon: 'ra ra-scroll-unfurled', tone: 'text-sky-300' },
  { label: 'Victories', value: props.stats.victories, icon: 'ra ra-crown', tone: 'text-amber-300' },
  { label: 'Defeats', value: props.stats.defeats, icon: 'ra ra-skull', tone: 'text-red-300' },
  { label: 'Total XP', value: props.stats.totalXp, icon: 'ra ra-lightning-bolt', tone: 'text-aether-primary' },
  { label: 'Awards', value: props.stats.awards, icon: 'ra ra-trophy', tone: 'text-aether-secondary' },
])

// --- Avatar ---
const avatarInput = ref<HTMLInputElement | null>(null)
const isGeneratingAvatar = ref(false)

async function onAvatarSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    await api.uploadProfileImage(file)
    await refreshUser()
    emit('notify', 'Profile image updated.', 'success')
  } catch (err: any) {
    emit('notify', err?.message || 'Failed to upload profile image.', 'error')
  } finally {
    input.value = ''
  }
}

async function generateAvatar() {
  isGeneratingAvatar.value = true
  try {
    await api.generateMyProfileImage(user.value?.bio || undefined)
    await refreshUser()
    emit('notify', 'A new portrait has been woven.', 'success')
  } catch (err: any) {
    emit('notify', err?.message || 'Portrait generation failed. Check the admin image settings.', 'error')
  } finally {
    isGeneratingAvatar.value = false
  }
}

// --- Bio ---
const isEditingBio = ref(false)
const isSavingBio = ref(false)
const isGeneratingBio = ref(false)
const bioDraft = ref('')

function startEditBio() {
  bioDraft.value = user.value?.bio || ''
  isEditingBio.value = true
}

async function saveBio() {
  isSavingBio.value = true
  try {
    await api.updateMyBio(bioDraft.value)
    await refreshUser()
    isEditingBio.value = false
    emit('notify', 'Biography saved.', 'success')
  } catch (err: any) {
    emit('notify', err?.message || 'Failed to save biography.', 'error')
  } finally {
    isSavingBio.value = false
  }
}

async function generateBio() {
  isGeneratingBio.value = true
  try {
    bioDraft.value = (await api.generateMyBio()).bio
  } catch (err: any) {
    emit('notify', err?.message || 'Biography generation failed.', 'error')
  } finally {
    isGeneratingBio.value = false
  }
}
</script>

<template>
  <header class="relative overflow-hidden rounded-3xl border border-white/10 bg-[#0a1120]">
    <!-- Decorative backdrop -->
    <div class="pointer-events-none absolute inset-0">
      <div class="absolute -left-24 -top-24 h-72 w-72 rounded-full bg-aether-primary/10 blur-3xl"></div>
      <div class="absolute -right-16 top-10 h-64 w-64 rounded-full bg-aether-secondary-container/20 blur-3xl"></div>
      <div class="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-aether-primary/40 to-transparent"></div>
    </div>

    <div class="relative flex flex-col gap-6 p-5 sm:p-8 lg:flex-row lg:items-center">
      <!-- Avatar -->
      <div class="group relative mx-auto h-32 w-32 shrink-0 lg:mx-0">
        <img :src="avatarUrl" alt="Profile portrait" class="h-full w-full rounded-full border-2 border-aether-primary/40 object-cover shadow-ambient-emerald" />
        <div v-if="isGeneratingAvatar" class="absolute inset-0 flex items-center justify-center rounded-full bg-black/60">
          <i class="ra ra-crystal-ball animate-spin text-3xl text-white"></i>
        </div>
        <div class="absolute -bottom-1 left-1/2 flex -translate-x-1/2 gap-1.5 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100">
          <button type="button" class="flex h-8 w-8 items-center justify-center rounded-full border border-white/15 bg-[#0a1120] text-slate-300 hover:text-white" title="Upload portrait" @click="avatarInput?.click()">
            <i class="ra ra-quill-ink text-sm"></i>
          </button>
          <button
            v-if="canGenerateAvatar"
            type="button"
            :disabled="isGeneratingAvatar"
            class="flex h-8 w-8 items-center justify-center rounded-full border border-white/15 bg-[#0a1120] text-slate-300 hover:text-white disabled:opacity-50"
            title="Generate portrait with AI"
            @click="generateAvatar"
          >
            <i class="ra ra-crystal-ball text-sm"></i>
          </button>
        </div>
        <input ref="avatarInput" type="file" accept="image/*" class="hidden" @change="onAvatarSelected" />
      </div>

      <!-- Identity & bio -->
      <div class="min-w-0 flex-1 text-center lg:text-left">
        <div class="flex flex-wrap items-center justify-center gap-3 lg:justify-start">
          <h2 class="truncate font-display text-3xl text-white sm:text-4xl">{{ user?.username || 'Adventurer' }}</h2>
          <span class="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] font-black uppercase tracking-widest text-slate-400">
            {{ user?.role === 'admin' ? 'Game Master' : 'Player' }}
          </span>
        </div>

        <div v-if="!isEditingBio" class="mt-3">
          <p v-if="user?.bio" class="font-narrative text-base italic leading-relaxed text-slate-300">“{{ user.bio }}”</p>
          <p v-else class="text-sm italic text-slate-500">No chronicle entry yet.</p>
          <button type="button" class="mt-2 text-[11px] font-black uppercase tracking-widest text-slate-500 hover:text-aether-primary" @click="startEditBio">
            <i class="ra ra-quill-ink"></i> {{ user?.bio ? 'Edit biography' : 'Write biography' }}
          </button>
        </div>

        <div v-else class="mt-3 space-y-2 text-left">
          <textarea
            v-model="bioDraft"
            rows="3"
            maxlength="1000"
            class="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-slate-200 outline-none focus:border-aether-primary/50"
            placeholder="Tell your story..."
          ></textarea>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <button type="button" :disabled="isGeneratingBio" class="text-[11px] font-black uppercase tracking-widest text-aether-primary/70 hover:text-aether-primary disabled:opacity-50" @click="generateBio">
              <i :class="['ra ra-crystal-ball', { 'animate-spin': isGeneratingBio }]"></i>
              {{ isGeneratingBio ? 'Weaving...' : 'Suggest with AI' }}
            </button>
            <div class="flex gap-2">
              <button type="button" class="px-3 py-1.5 text-[11px] font-black uppercase tracking-widest text-slate-500 hover:text-white" @click="isEditingBio = false">Cancel</button>
              <button type="button" :disabled="isSavingBio" class="rounded-lg bg-aether-primary px-3 py-1.5 text-[11px] font-black uppercase tracking-widest text-[#081425] hover:bg-emerald-300 disabled:opacity-50" @click="saveBio">Save</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Stats -->
    <div class="relative grid grid-cols-2 border-t border-white/5 sm:grid-cols-5">
      <div
        v-for="tile in statTiles"
        :key="tile.label"
        class="flex items-center gap-3 border-white/5 px-5 py-4 [&:not(:last-child)]:border-b sm:[&:not(:last-child)]:border-b-0 sm:[&:not(:last-child)]:border-r"
      >
        <i :class="[tile.icon, tile.tone, 'text-xl']"></i>
        <div>
          <p class="font-display text-2xl leading-none text-white tabular-nums">{{ tile.value }}</p>
          <p class="mt-1 text-[10px] font-black uppercase tracking-widest text-slate-500">{{ tile.label }}</p>
        </div>
      </div>
    </div>
  </header>
</template>
