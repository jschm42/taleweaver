<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import type { AdventureTemplateSummary } from '@/types'
import { MoreHorizontal } from 'lucide-vue-next'

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

const isMenuOpen = ref(false)
const menuRef = ref<HTMLElement | null>(null)

function toggleMenu() {
  isMenuOpen.value = !isMenuOpen.value
}

function handleClickOutside(event: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(event.target as Node)) {
    isMenuOpen.value = false
  }
}

onMounted(() => {
  window.addEventListener('mousedown', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('mousedown', handleClickOutside)
})

function runAction(action: 'edit' | 'adz' | 'adv' | 'delete'): void {
  if (action === 'edit') emit('edit', props.template.template_id)
  else if (action === 'adz') emit('exportAdz', props.template.template_id, props.template.title)
  else if (action === 'adv') emit('exportAdv', props.template.template_id, props.template.title)
  else if (action === 'delete') emit('delete', props.template.template_id, props.template.title)
  isMenuOpen.value = false
}

const toneLabel = computed(() => {
  const tone = props.template.selected_tone
  if (!tone) return ''
  if (typeof tone === 'string') {
    if (tone.startsWith('{')) {
      try {
        const obj = JSON.parse(tone)
        return obj.name || obj.id || tone
      } catch (e) {
        return tone
      }
    }
    return tone
  }
  return tone.name || tone.id || ''
})

function fixNewlines(text: string | null | undefined): string {
  if (!text) return ''
  return text.replace(/\\n/g, '\n')
}

</script>

<template>
  <article class="rounded-xl border border-white/10 bg-aether-surface/20 flex flex-col relative group">
    <!-- Top Cover Area -->
    <div class="aspect-[3/2] relative bg-black/30 border-b border-white/5">
      <div class="absolute inset-0 overflow-hidden rounded-t-xl">
        <img
          v-if="props.template.image_url"
          :src="props.template.image_url"
          class="w-full h-full object-cover object-top group-hover:scale-105 transition-transform duration-700"
          alt="Adventure cover"
        />
        <div v-else class="w-full h-full flex items-center justify-center text-slate-500 text-xs font-bold uppercase tracking-widest">
          No Cover
        </div>
      </div>

      <!-- Tone Badge -->
      <div v-if="props.template.selected_tone" class="absolute top-3 left-3">
        <span class="px-2.5 py-1 rounded-full bg-aether-primary/20 text-aether-primary text-xs uppercase tracking-widest font-black border border-aether-primary/20">
          {{ toneLabel }}
        </span>
      </div>

      <!-- Action Dots -->
      <div class="absolute top-3 right-3" ref="menuRef">
        <button
          @click.stop="toggleMenu"
          class="w-8 h-8 rounded-full bg-black/40 backdrop-blur-md border border-white/10 text-white hover:bg-black/60 transition-all flex items-center justify-center"
          title="Adventure options"
        >
          <MoreHorizontal class="w-5 h-5" />
        </button>

        <Transition
          enter-active-class="transition duration-100 ease-out"
          enter-from-class="transform scale-95 opacity-0"
          enter-to-class="transform scale-100 opacity-100"
          leave-active-class="transition duration-75 ease-in"
          leave-from-class="transform scale-100 opacity-100"
          leave-to-class="transform scale-95 opacity-0"
        >
          <div
            v-if="isMenuOpen"
            class="absolute right-0 top-10 z-30 w-44 bg-[#0d1117] border border-white/10 rounded-xl shadow-[0_12px_40px_rgba(0,0,0,0.6)] overflow-hidden backdrop-blur-xl"
          >
            <button
              class="w-full text-left px-4 py-2.5 text-xs font-black uppercase tracking-widest text-slate-400 hover:text-white hover:bg-white/5"
              @click="runAction('edit')"
            >
              Edit blueprint
            </button>
            <button
              class="w-full text-left px-4 py-2.5 text-xs font-black uppercase tracking-widest text-slate-400 hover:text-white hover:bg-white/5"
              @click="runAction('adz')"
            >
              Export (.adz)
            </button>
            <button
              class="w-full text-left px-4 py-2.5 text-xs font-black uppercase tracking-widest text-slate-400 hover:text-white hover:bg-white/5"
              @click="runAction('adv')"
            >
              Export (.adv)
            </button>
            <div class="h-[1px] bg-white/5 mx-2 my-1"></div>
            <button
              class="w-full text-left px-4 py-2.5 text-xs font-black uppercase tracking-widest text-red-400/60 hover:text-red-400 hover:bg-red-500/10"
              @click="runAction('delete')"
            >
              Delete world
            </button>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Content Area -->
    <div class="p-6 flex flex-col gap-4 flex-1">
      <div class="space-y-2 flex-1">
        <h3 class="text-2xl font-black text-white leading-tight line-clamp-1 tracking-tight">{{ props.template.title }}</h3>
        <p v-if="props.template.teaser" class="text-xs font-bold text-emerald-500/80 uppercase tracking-widest line-clamp-3 leading-relaxed whitespace-pre-wrap">
          {{ fixNewlines(props.template.teaser) }}
        </p>
      </div>

      <!-- Action Button -->
      <button
        class="w-full py-3.5 rounded-xl bg-emerald-500/10 text-emerald-400 text-xs font-black uppercase tracking-widest hover:bg-emerald-500/20 transition-all border border-emerald-500/20 flex items-center justify-center gap-3 shadow-lg shadow-emerald-500/5 group/btn"
        @click="emit('startSession', props.template.template_id)"
      >
        <i class="ra ra-play text-sm transition-transform group-hover/btn:scale-110"></i>
        Start New Game
      </button>
    </div>
  </article>
</template>

