<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import type { AdventureTemplateSummary } from '@/types'

const props = defineProps<{
  template: AdventureTemplateSummary
}>()

const emit = defineEmits<{
  (e: 'startSession', templateId: string): void
  (e: 'edit', templateId: string): void
  (e: 'exportAdz', templateId: string, title: string): void
  (e: 'exportAdv', templateId: string, title: string): void
  (e: 'delete', templateId: string, title: string): void
}>()

const showDropdown = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)

function toggleDropdown() {
  showDropdown.value = !showDropdown.value
}

function handleClickOutside(event: MouseEvent) {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target as Node)) {
    showDropdown.value = false
  }
}

onMounted(() => {
  window.addEventListener('mousedown', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('mousedown', handleClickOutside)
})
</script>

<template>
  <article class="rounded-xl border border-white/10 bg-aether-surface/20 p-4 flex flex-col gap-4 relative group">
    <div class="aspect-[3/2] rounded-lg overflow-hidden bg-black/30 border border-white/5">
      <img
        v-if="props.template.image_url"
        :src="props.template.image_url"
        class="w-full h-full object-cover"
        alt="Adventure cover"
      />
      <div v-else class="w-full h-full flex items-center justify-center text-slate-500 text-xs uppercase tracking-widest">
        No Cover
      </div>
    </div>

    <div class="space-y-1">
      <h3 class="text-xl font-black text-white line-clamp-1">{{ props.template.title }}</h3>
      <p v-if="props.template.teaser" class="text-xs text-slate-400 line-clamp-2 min-h-[2.5rem] leading-relaxed">
        {{ props.template.teaser }}
      </p>
    </div>

    <div class="flex gap-2">
      <button
        class="flex-1 px-3 py-2.5 rounded-lg bg-emerald-500/20 text-emerald-300 text-xs font-bold uppercase tracking-widest hover:bg-emerald-500/30 transition-colors border border-emerald-500/20"
        @click="emit('startSession', props.template.template_id)"
      >
        Start New Game
      </button>
      
      <div class="relative" ref="dropdownRef">
        <button
          class="h-full px-3 rounded-lg bg-white/5 text-slate-400 hover:text-white hover:bg-white/10 transition-all border border-white/10 flex items-center justify-center font-bold text-lg"
          @click="toggleDropdown"
          title="Adventure Options"
        >
          &bull;&bull;&bull;
        </button>

        <!-- Dropdown Menu -->
        <Transition
          enter-active-class="transition duration-100 ease-out"
          enter-from-class="transform scale-95 opacity-0"
          enter-to-class="transform scale-100 opacity-100"
          leave-active-class="transition duration-75 ease-in"
          leave-from-class="transform scale-100 opacity-100"
          leave-to-class="transform scale-95 opacity-0"
        >
          <div 
            v-if="showDropdown"
            class="absolute right-0 bottom-full mb-3 w-52 bg-[#0d1117] border border-white/10 rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.5)] z-50 overflow-hidden backdrop-blur-xl"
          >
            <div class="p-2 space-y-1">
              <button
                class="w-full px-4 py-2.5 text-left text-[10px] font-black uppercase tracking-widest text-slate-400 hover:text-white hover:bg-white/5 rounded-xl transition-all"
                @click="emit('edit', props.template.template_id); showDropdown = false"
              >
                Edit blueprint
              </button>
              <button
                class="w-full px-4 py-2.5 text-left text-[10px] font-black uppercase tracking-widest text-slate-400 hover:text-white hover:bg-white/5 rounded-xl transition-all"
                @click="emit('exportAdz', props.template.template_id, props.template.title); showDropdown = false"
              >
                Export (.adz)
              </button>
              <button
                class="w-full px-4 py-2.5 text-left text-[10px] font-black uppercase tracking-widest text-slate-400 hover:text-white hover:bg-white/5 rounded-xl transition-all"
                @click="emit('exportAdv', props.template.template_id, props.template.title); showDropdown = false"
              >
                Export (.adv)
              </button>
              
              <div class="h-[1px] bg-white/5 mx-2 my-1"></div>
              
              <button
                class="w-full px-4 py-2.5 text-left text-[10px] font-black uppercase tracking-widest text-red-400/60 hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-all"
                @click="emit('delete', props.template.template_id, props.template.title); showDropdown = false"
              >
                Archive world
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </div>
  </article>
</template>
