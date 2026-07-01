<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { Lock, Key, Unlock, AlertCircle, Check } from 'lucide-vue-next'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'

const brokenImages = ref<Record<string, boolean>>({})
const showImage = (path?: string | null) => {
  return !!path && !brokenImages.value[path]
}
const handleImageError = (path: string) => {
  if (path) brokenImages.value[path] = true
}

const props = defineProps<{
  open: boolean
  switchEntity: any
  targetState: string
  inventoryItems: any[]
  busy?: boolean
  errorMessage?: string
}>()

const emit = defineEmits<{
  close: []
  submitCode: [code: string]
  useKeyItem: [itemId: string]
}>()

const codeInput = ref('')
const selectedItemId = ref<string>('')

const resolvedMetadata = computed(() => {
  let meta = props.switchEntity?.metadata_json || {}
  if (typeof meta === 'string') {
    try {
      meta = JSON.parse(meta)
    } catch {
      meta = {}
    }
  }
  return meta
})

const activeTransition = computed(() => {
  const config = resolvedMetadata.value.switch || {}
  const transitions = config.transitions || []
  if (!Array.isArray(transitions)) return null

  const states = Array.isArray(config.states) ? config.states : []
  const configuredCurrent = config.initial_state || ''
  const currentState = String(props.switchEntity.switch_state || configuredCurrent).trim().toUpperCase()
  const targetState = String(props.targetState || '').trim().toUpperCase()

  return transitions.find((t: any) => {
    const fromVal = String(t.from || '').trim().toUpperCase()
    const toVal = String(t.to || '').trim().toUpperCase()
    return fromVal === currentState && toVal === targetState
  }) || null
})

const gates = computed(() => {
  return activeTransition.value?.gates || {}
})

const requiredCode = computed(() => {
  return String(gates.value.code || '').trim()
})

const requiredItemId = computed(() => {
  return String(gates.value.item || '').trim().toUpperCase()
})

const requiredRule = computed(() => {
  return String(gates.value.rule || '').trim()
})

// Filter inventory: only usable items (exclude switches/containers) for the unlock grid
const usableItems = computed(() => {
  return (props.inventoryItems || []).filter((item: any) => {
    if (!item) return false
    const type = String(item.item_type || '').trim().toUpperCase()
    if (type === 'SWITCH') return false
    if (type === 'CONTAINER') return false
    if (item.is_portable === false) return false
    return true
  })
})

const selectedItem = computed(() => {
  if (!selectedItemId.value) return null
  return usableItems.value.find((it: any) => String(it.id || '') === selectedItemId.value) || null
})

const hasSelection = computed(() => !!selectedItem.value)

const selectItem = (itemId: string) => {
  if (props.busy) return
  selectedItemId.value = itemId
}

const handleCodeSubmit = () => {
  if (!codeInput.value.trim() || props.busy) return
  emit('submitCode', codeInput.value.trim())
}

const handleActivate = () => {
  if (!hasSelection.value || props.busy) return
  emit('useKeyItem', selectedItem.value.id)
}

const onKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && props.open && !props.busy) {
    emit('close')
  }
}

// Reset state on open
watch(() => props.open, (isOpen) => {
  if (isOpen) {
    codeInput.value = ''
    selectedItemId.value = ''
  }
})

onMounted(() => window.addEventListener('keydown', onKeyDown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown))
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open && switchEntity"
        class="fixed inset-0 z-[130] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
        @click.self="emit('close')"
      >
        <div class="w-full max-w-md bg-slate-900 border border-slate-700/60 rounded-3xl shadow-2xl overflow-hidden" @click.stop>

          <!-- Header -->
          <div class="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between">
            <div class="flex items-center gap-2.5">
              <div class="w-8 h-8 rounded-lg bg-lime-500/10 border border-lime-500/20 flex items-center justify-center">
                <Lock class="w-4 h-4 text-lime-400" />
              </div>
              <div>
                <p class="text-[9px] uppercase tracking-[0.25em] text-lime-500 font-black">Locked Transition</p>
                <h3 class="text-lg font-black text-white leading-tight mt-0.5">{{ switchEntity.name || 'Switch' }}</h3>
              </div>
            </div>
            <button
              class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors disabled:opacity-50"
              :disabled="busy"
              @click="emit('close')"
            >
              <i class="ra ra-cancel text-sm"></i>
            </button>
          </div>

          <!-- Body -->
          <div class="p-6 space-y-5">
            <!-- Switch Description -->
            <p v-if="switchEntity.description" class="text-sm text-slate-400 leading-relaxed italic">
              "{{ switchEntity.description }}"
            </p>

            <div class="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
              <span>Flipping to state:</span>
              <span class="px-2 py-0.5 bg-lime-500/10 text-lime-400 border border-lime-500/20 rounded font-mono font-bold">{{ targetState }}</span>
            </div>

            <!-- Error message -->
            <div v-if="errorMessage" class="flex gap-2 p-3.5 rounded-xl border border-red-500/20 bg-red-500/5 text-sm text-red-300">
              <AlertCircle class="w-4 h-4 mt-0.5 shrink-0" />
              <span>{{ errorMessage }}</span>
            </div>

            <!-- CODE REQUIREMENT -->
            <div v-if="requiredCode" class="space-y-3">
              <label class="block text-xs font-black text-slate-400 uppercase tracking-widest">
                Enter Combination Code
              </label>
              <form @submit.prevent="handleCodeSubmit" class="flex gap-2">
                <input
                  v-model="codeInput"
                  type="text"
                  placeholder="Enter code..."
                  maxlength="32"
                  :disabled="busy"
                  class="flex-1 bg-slate-950/60 border border-slate-800 focus:border-lime-500/60 rounded-xl px-4 py-3 text-white placeholder-slate-600 outline-none transition-all font-mono font-bold tracking-wider"
                  autofocus
                />
                <button
                  type="submit"
                  :disabled="busy || !codeInput.trim()"
                  class="px-5 bg-lime-500 hover:bg-lime-400 disabled:bg-slate-800 text-slate-950 disabled:text-slate-600 font-bold rounded-xl transition-all flex items-center justify-center gap-1.5 cursor-pointer shadow-lg shadow-lime-500/10"
                >
                  <Unlock class="w-4.5 h-4.5" />
                  <span>Unlock</span>
                </button>
              </form>
            </div>

            <!-- ITEM REQUIREMENT -->
            <div v-else-if="requiredItemId" class="space-y-4">
              <div class="p-4 rounded-2xl bg-slate-950/40 border border-slate-800/80 flex items-start gap-3">
                <div class="w-9 h-9 rounded-lg bg-lime-500/15 border border-lime-500/30 flex items-center justify-center shrink-0 mt-0.5">
                  <Key class="w-4.5 h-4.5 text-lime-400" />
                </div>
                <div class="space-y-1">
                  <p class="text-xs font-black uppercase tracking-wider text-lime-400">Item Required</p>
                  <p class="text-sm text-slate-300">
                    Select an item from your inventory and press <span class="text-lime-300 font-bold">Activate</span> to flip this switch.
                  </p>
                </div>
              </div>

              <!-- Item selection grid -->
              <div>
                <label class="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">
                  Choose an Item
                </label>

                <div v-if="usableItems.length === 0" class="w-full text-center text-xs font-bold text-slate-500 uppercase tracking-widest border border-slate-800 py-6 rounded-xl bg-slate-950/20">
                  Your inventory contains no usable items
                </div>

                <div v-else class="grid grid-cols-4 gap-2 max-h-64 overflow-y-auto p-1">
                  <button
                    v-for="item in usableItems"
                    :key="item.id"
                    type="button"
                    :disabled="busy"
                    @click="selectItem(item.id)"
                    class="relative aspect-square rounded-xl border bg-slate-950/40 transition-all overflow-hidden group focus:outline-none cursor-pointer"
                    :class="selectedItemId === item.id
                      ? 'border-lime-500/70 ring-2 ring-lime-500/40 shadow-lg shadow-lime-500/10'
                      : 'border-slate-800/60 hover:border-slate-600 hover:bg-slate-900/60'"
                    :title="item.name || item.id"
                  >
                    <div class="absolute inset-0 flex items-center justify-center">
                      <img
                        v-if="item.image_url && showImage(item.image_url)"
                        :src="getImageUrl(item.image_url)"
                        class="w-full h-full object-cover object-top"
                        @error="handleImageError(item.image_url)"
                      />
                      <div v-else class="w-full h-full flex items-center justify-center bg-slate-800/40">
                        <i :class="['ra text-2xl', getItemIcon(item.item_type ?? undefined), getTypeColor(item.item_type ?? undefined)]"></i>
                      </div>
                    </div>
                    <div
                      v-if="selectedItemId === item.id"
                      class="absolute top-1 right-1 w-5 h-5 rounded-full bg-lime-500 border-2 border-slate-900 flex items-center justify-center shadow-md"
                    >
                      <Check class="w-3 h-3 text-slate-950" stroke-width="3" />
                    </div>
                    <div class="absolute bottom-0 inset-x-0 px-1 py-1 bg-gradient-to-t from-slate-950/95 to-slate-950/0">
                      <p class="text-[10px] font-bold text-slate-200 truncate leading-tight text-center">
                        {{ item.name || item.id }}
                      </p>
                    </div>
                  </button>
                </div>
              </div>

              <div class="pt-1">
                <button
                  @click="handleActivate"
                  :disabled="busy || !hasSelection"
                  class="w-full py-3 bg-lime-500 hover:bg-lime-400 disabled:bg-slate-800 text-slate-950 disabled:text-slate-600 font-black uppercase tracking-wider text-xs rounded-xl shadow-lg shadow-lime-500/10 transition-colors flex items-center justify-center gap-2 cursor-pointer disabled:cursor-not-allowed"
                >
                  <Unlock class="w-4 h-4" />
                  <span>Activate</span>
                </button>
                <p v-if="!hasSelection" class="text-[11px] text-slate-500 text-center mt-2 italic">
                  Pick an item from your inventory to enable the activation.
                </p>
              </div>
            </div>

            <!-- RULE/PUZZLE REQUIREMENT -->
            <div v-else-if="requiredRule" class="p-4 rounded-2xl bg-slate-950/40 border border-slate-800/80 flex items-start gap-3">
              <div class="w-9 h-9 rounded-lg bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center shrink-0 mt-0.5">
                <Lock class="w-4.5 h-4.5 text-cyan-400" />
              </div>
              <div class="space-y-1">
                <p class="text-xs font-black uppercase tracking-wider text-cyan-400">Locked by Event/Puzzle</p>
                <p class="text-sm text-slate-300 leading-relaxed">
                  This switch transition cannot be triggered directly. You must satisfy a condition or solve a puzzle in the world first.
                </p>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="px-6 py-4 bg-slate-950/30 border-t border-slate-800/80 flex items-center justify-end gap-3">
            <button
              class="px-5 py-2 rounded-xl border border-slate-700 text-slate-300 text-sm font-bold hover:bg-slate-800 transition-colors disabled:opacity-50 cursor-pointer"
              :disabled="busy"
              @click="emit('close')"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1); }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>