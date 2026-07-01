<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { getImageUrl } from '@/utils/game_icons'

const props = defineProps<{
  open: boolean
  switchEntity: any
  inventoryItems: any[]
  busy?: boolean
}>()

const emit = defineEmits<{
  close: []
  selectState: [targetState: string]
}>()

const brokenImages = ref<Record<string, boolean>>({})
const showImage = (path?: string | null) => !!path && !brokenImages.value[path ?? '']
const handleImageError = (path: string) => { if (path) brokenImages.value[path] = true }

const resolvedMetadata = computed(() => {
  let meta = props.switchEntity?.metadata_json || {}
  if (typeof meta === 'string') {
    try { meta = JSON.parse(meta) } catch { meta = {} }
  }
  return meta
})

const switchConfig = computed(() => {
  const m = resolvedMetadata.value
  return (m.switch && typeof m.switch === 'object') ? m.switch : {}
})

const allStates = computed<string[]>(() => {
  const raw = switchConfig.value.states
  return Array.isArray(raw) ? raw.map((s: any) => String(s || '').trim()).filter(Boolean) : []
})

const currentState = computed(() => {
  return String(
    props.switchEntity?.switch_state ||
    switchConfig.value.initial_state ||
    (allStates.value[0] ?? '')
  ).trim().toUpperCase()
})

// Keyboard navigation
const focusedIndex = ref(0)
const targetStates = computed(() =>
  allStates.value.filter(s => s.toUpperCase() !== currentState.value)
)

watch(() => props.open, (isOpen) => {
  if (isOpen) focusedIndex.value = 0
})

const onKeyDown = (event: KeyboardEvent) => {
  if (!props.open || props.busy) return

  if (event.key === 'Escape') {
    emit('close')
    return
  }

  const states = targetStates.value
  if (!states.length) return

  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    event.preventDefault()
    focusedIndex.value = (focusedIndex.value + 1) % states.length
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    event.preventDefault()
    focusedIndex.value = (focusedIndex.value - 1 + states.length) % states.length
  } else if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    const state = states[focusedIndex.value]
    if (state) emit('selectState', state.toUpperCase())
  }
}

onMounted(() => window.addEventListener('keydown', onKeyDown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown))
</script>

<template>
  <Teleport to="body">
    <Transition name="sw-fade">
      <div
        v-if="open && switchEntity"
        class="fixed inset-0 z-[130] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
        @click.self="emit('close')"
      >
        <Transition name="sw-scale" appear>
          <div
            class="w-full max-w-sm bg-slate-900 border border-slate-700/60 rounded-3xl shadow-2xl overflow-hidden"
            @click.stop
          >
            <!-- Header -->
            <div class="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between gap-3">
              <div class="flex items-center gap-3">
                <!-- Switch image or icon -->
                <div class="w-11 h-11 rounded-xl overflow-hidden border border-slate-700 bg-slate-800 flex items-center justify-center shrink-0">
                  <img
                    v-if="switchEntity.image_url && showImage(switchEntity.image_url)"
                    :src="getImageUrl(switchEntity.image_url)"
                    class="w-full h-full object-cover object-top"
                    @error="handleImageError(switchEntity.image_url)"
                  />
                  <i v-else class="ra ra-lever text-2xl text-lime-400"></i>
                </div>
                <div>
                  <p class="text-[9px] uppercase tracking-[0.25em] text-lime-500 font-black">Switch</p>
                  <h3 class="text-base font-black text-white leading-tight mt-0.5">{{ switchEntity.name || 'Switch' }}</h3>
                </div>
              </div>
              <button
                class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors disabled:opacity-50 cursor-pointer"
                :disabled="busy"
                @click="emit('close')"
              >
                <i class="ra ra-cancel text-sm"></i>
              </button>
            </div>

            <!-- Body -->
            <div class="p-6 space-y-5">
              <!-- Description -->
              <p v-if="switchEntity.description" class="text-sm text-slate-400 leading-relaxed italic">
                "{{ switchEntity.description }}"
              </p>

              <!-- Current state indicator -->
              <div class="flex items-center gap-2.5">
                <span class="text-xs font-bold text-slate-500 uppercase tracking-widest">Current state:</span>
                <span class="px-2.5 py-1 bg-slate-800 border border-slate-700 rounded-lg text-xs font-black text-lime-400 font-mono tracking-wider">
                  {{ currentState }}
                </span>
              </div>

              <!-- State selection buttons -->
              <div class="space-y-2.5">
                <p class="text-xs font-black text-slate-400 uppercase tracking-widest">Select new state</p>

                <!-- All states list — current is disabled/greyed, others are clickable -->
                <div class="grid gap-2" :class="allStates.length > 3 ? 'grid-cols-2' : 'grid-cols-1'">
                  <button
                    v-for="(state, idx) in allStates"
                    :key="state"
                    :disabled="busy || state.toUpperCase() === currentState"
                    :class="[
                      'relative group flex items-center gap-3 px-4 py-3.5 rounded-2xl border font-bold text-sm transition-all duration-200',
                      state.toUpperCase() === currentState
                        ? 'bg-lime-500/10 border-lime-500/30 text-lime-400 cursor-default'
                        : focusedIndex === targetStates.indexOf(state) && targetStates.includes(state)
                          ? 'bg-lime-500 border-lime-400 text-slate-950 shadow-lg shadow-lime-500/25 cursor-pointer scale-[1.02]'
                          : 'bg-slate-800/40 border-slate-700/60 text-slate-300 hover:bg-lime-500/10 hover:border-lime-500/40 hover:text-lime-300 cursor-pointer'
                    ]"
                    @click="state.toUpperCase() !== currentState && emit('selectState', state.toUpperCase())"
                    @mouseenter="() => { const ti = targetStates.indexOf(state); if (ti !== -1) focusedIndex = ti }"
                  >
                    <!-- Current state checkmark -->
                    <span
                      v-if="state.toUpperCase() === currentState"
                      class="w-5 h-5 rounded-full bg-lime-500/20 border border-lime-500/40 flex items-center justify-center shrink-0"
                    >
                      <i class="ra ra-check text-[10px] text-lime-400"></i>
                    </span>
                    <!-- Non-current state arrow -->
                    <span
                      v-else
                      class="w-5 h-5 rounded-full border flex items-center justify-center shrink-0 transition-all"
                      :class="focusedIndex === targetStates.indexOf(state) && targetStates.includes(state)
                        ? 'bg-slate-950/30 border-slate-950/30'
                        : 'bg-slate-700/40 border-slate-600/60 group-hover:border-lime-400/60'"
                    >
                      <i class="ra ra-angle-right text-[10px] transition-colors"
                         :class="focusedIndex === targetStates.indexOf(state) && targetStates.includes(state)
                           ? 'text-slate-950'
                           : 'text-slate-400 group-hover:text-lime-400'"
                      ></i>
                    </span>

                    <span class="font-mono tracking-wider">{{ state.toUpperCase() }}</span>

                    <span
                      v-if="state.toUpperCase() === currentState"
                      class="ml-auto text-[9px] font-black uppercase tracking-widest text-lime-500/70"
                    >Active</span>
                    <span
                      v-else-if="busy"
                      class="ml-auto"
                    >
                      <i class="ra ra-hourglass text-xs animate-spin opacity-50"></i>
                    </span>
                  </button>
                </div>
              </div>

              <!-- Keyboard hint -->
              <p class="text-[10px] text-slate-600 text-center">
                Use <kbd class="px-1 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-400 font-mono text-[9px]">↑ ↓</kbd>
                to navigate,
                <kbd class="px-1 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-400 font-mono text-[9px]">Enter</kbd>
                to confirm
              </p>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.sw-fade-enter-active, .sw-fade-leave-active {
  transition: opacity 0.2s ease;
}
.sw-fade-enter-from, .sw-fade-leave-to {
  opacity: 0;
}

.sw-scale-enter-active {
  transition: opacity 0.2s ease, transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.sw-scale-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.sw-scale-enter-from {
  opacity: 0;
  transform: scale(0.92) translateY(8px);
}
.sw-scale-leave-to {
  opacity: 0;
  transform: scale(0.96) translateY(4px);
}
</style>
