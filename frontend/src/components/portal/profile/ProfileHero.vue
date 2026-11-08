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
  { label: 'Awards', value: props.stats.awards, icon: 'ra ra-trophy', tone: 'text-aether-secondary' },
])
const formattedXp = computed(() => props.stats.totalXp.toLocaleString('en-US'))
const isBioExpanded = ref(false)
const isLongBio = computed(() => (user.value?.bio || '').length > 180)

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
      <div class="absolute -left-24 -top-24 h-64 w-64 rounded-full bg-aether-primary/10 blur-3xl"></div>
      <div class="absolute -right-20 top-24 h-56 w-56 rounded-full bg-aether-secondary-container/20 blur-3xl"></div>
    </div>

    <div class="relative flex flex-col gap-5 p-5 sm:flex-row sm:items-start lg:flex-col lg:items-stretch">
      <!-- Avatar -->
      <div class="group relative mx-auto h-28 w-28 shrink-0 sm:mx-0 lg:mx-auto">
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
      <div class="min-w-0 flex-1 text-center sm:text-left lg:text-center">
        <h2 class="truncate font-display text-3xl text-white" :title="user?.username">{{ user?.username || 'Adventurer' }}</h2>
        <span class="mt-1.5 inline-block rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] font-black uppercase tracking-widest text-slate-400">
          {{ user?.role === 'admin' ? 'Game Master' : 'Player' }}
        </span>

        <div v-if="!isEditingBio" class="mt-3">
          <p
            v-if="user?.bio"
            class="font-narrative text-[15px] italic leading-relaxed text-slate-300"
            :class="{ 'line-clamp-4': isLongBio && !isBioExpanded }"
          >“{{ user.bio }}”</p>
          <p v-else class="text-sm italic text-slate-500">No chronicle entry yet.</p>
          <div class="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1 sm:justify-start lg:justify-center">
            <button
              v-if="isLongBio"
              type="button"
              class="text-[11px] font-black uppercase tracking-widest text-slate-500 hover:text-white"
              :aria-expanded="isBioExpanded"
              @click="isBioExpanded = !isBioExpanded"
            >
              {{ isBioExpanded ? 'Show less' : 'Read more' }}
            </button>
            <button type="button" class="text-[11px] font-black uppercase tracking-widest text-slate-500 hover:text-aether-primary" @click="startEditBio">
              <i class="ra ra-quill-ink"></i> {{ user?.bio ? 'Edit biography' : 'Write biography' }}
            </button>
          </div>
        </div>

        <div v-else class="mt-3 space-y-2 text-left">
          <textarea
            v-model="bioDraft"
            rows="5"
            maxlength="1000"
            class="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-aether-primary/50"
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
    <div class="relative border-t border-white/5 p-4">
      <div class="mb-3 flex items-baseline justify-between rounded-2xl border border-aether-primary/20 bg-aether-primary/5 px-4 py-3">
        <span class="text-[10px] font-black uppercase tracking-widest text-slate-400"><i class="ra ra-lightning-bolt text-aether-primary"></i> Total XP</span>
        <span class="font-display text-2xl leading-none text-white tabular-nums">{{ formattedXp }}</span>
      </div>
      <div class="grid grid-cols-4 gap-2 lg:grid-cols-2">
        <div v-for="tile in statTiles" :key="tile.label" class="flex flex-col items-center gap-1 rounded-xl bg-white/[0.03] px-2 py-2.5 lg:flex-row lg:gap-2.5 lg:px-3">
          <i :class="[tile.icon, tile.tone, 'text-base']"></i>
          <div class="min-w-0 text-center lg:text-left">
            <p class="font-display text-xl leading-none text-white tabular-nums">{{ tile.value }}</p>
            <p class="mt-1 truncate text-[9px] font-black uppercase tracking-widest text-slate-500">{{ tile.label }}</p>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>
