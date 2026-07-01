<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { Lock, Key, Unlock, AlertCircle } from 'lucide-vue-next'
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
  container: any
  inventoryItems: any[]
  busy?: boolean
  errorMessage?: string
  kind?: 'container' | 'exit'
  headerLabel?: string
  title?: string
  accentColor?: 'amber' | 'cyan'
  icon?: 'Lock' | 'Key'
}>()

const emit = defineEmits<{
  close: []
  submitCode: [code: string]
  useKeyItem: [itemId: string]
}>()

const codeInput = ref('')

const resolvedMetadata = computed(() => {
  let meta: any = props.container?.metadata_json
  if (typeof meta === 'string') {
    try {
      meta = JSON.parse(meta)
    } catch {
      meta = {}
    }
  }
  return meta && typeof meta === 'object' ? meta : {}
})

const requiredCode = computed(() => {
  return String(
    props.container?.code_to_unlock
    || resolvedMetadata.value.code_to_unlock
    || props.container?.metadata?.code_to_unlock
    || ''
  ).trim()
})

const requiredItemId = computed(() => {
  return String(
    props.container?.item_to_unlock
    || resolvedMetadata.value.item_to_unlock
    || props.container?.metadata?.item_to_unlock
    || ''
  ).trim().toUpperCase()
})

const requiredRule = computed(() => {
  return String(
    props.container?.rule_to_unlock
    || resolvedMetadata.value.rule_to_unlock
    || props.container?.metadata?.rule_to_unlock
    || ''
  ).trim()
})

const effectiveKind = computed(() => props.kind || (props.container?.exit_type ? 'exit' : 'container'))
const effectiveTitle = computed(() => props.title || props.container?.name || props.container?.label || (effectiveKind.value === 'exit' ? 'Exit' : 'Container'))
const effectiveHeader = computed(() => props.headerLabel || (effectiveKind.value === 'exit' ? 'Locked Exit' : 'Locked Container'))
const effectiveAccent = computed(() => props.accentColor || (effectiveKind.value === 'exit' ? 'cyan' : 'amber'))

const accentColorClass = computed(() => {
  if (effectiveAccent.value === 'cyan') {
    return { text: 'text-cyan-400', bg: 'bg-cyan-500/10', border: 'border-cyan-500/20', label: 'text-cyan-500' }
  }
  return { text: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20', label: 'text-amber-500' }
})

const effectiveDescription = computed(() => {
  return String(props.container?.description || props.container?.lock_description || '').trim()
})

const entityNoun = computed(() => (effectiveKind.value === 'exit' ? 'exit' : 'container'))

// Helper to format ID to readable name (e.g. BRONZE_KEY -> Bronze Key)
const formatIdToName = (id: string): string => {
  if (!id) return ''
  return id
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

// Find matching key item in inventory
const matchingInventoryKey = computed(() => {
  if (!requiredItemId.value) return null
  return props.inventoryItems.find(item => {
    const itemId = String(item?.id || '').trim().toUpperCase()
    const itemName = String(item?.name || '').trim().toUpperCase()
    return itemId === requiredItemId.value || itemName === requiredItemId.value
  })
})

const hasRequiredKey = computed(() => !!matchingInventoryKey.value)

const keyNameDisplay = computed(() => {
  if (matchingInventoryKey.value) {
    return matchingInventoryKey.value.name || matchingInventoryKey.value.id
  }
  return formatIdToName(requiredItemId.value)
})

const handleCodeSubmit = () => {
  if (!codeInput.value.trim() || props.busy) return
  emit('submitCode', codeInput.value.trim())
}

const handleUseKey = () => {
  if (!hasRequiredKey.value || props.busy) return
  const itemId = matchingInventoryKey.value.id || requiredItemId.value
  emit('useKeyItem', itemId)
}

const onKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && props.open && !props.busy) {
    emit('close')
  }
}

// Clear input on open
watch(() => props.open, (isOpen) => {
  if (isOpen) {
    codeInput.value = ''
  }
})

onMounted(() => window.addEventListener('keydown', onKeyDown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown))
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open && container"
        class="fixed inset-0 z-[130] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
        @click.self="emit('close')"
      >
        <div class="w-full max-w-md bg-slate-900 border border-slate-700/60 rounded-3xl shadow-2xl overflow-hidden" @click.stop>
          
          <!-- Header -->
          <div class="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between">
            <div class="flex items-center gap-2.5">
              <div :class="['w-8 h-8 rounded-lg flex items-center justify-center', accentColorClass.bg, accentColorClass.border]">
                <Lock :class="['w-4 h-4', accentColorClass.text]" />
              </div>
              <div>
                <p :class="['text-[9px] uppercase tracking-[0.25em] font-black', accentColorClass.label]">{{ effectiveHeader }}</p>
                <h3 class="text-lg font-black text-white leading-tight mt-0.5">{{ effectiveTitle }}</h3>
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
            <!-- Container/Exit Description -->
            <p v-if="effectiveDescription" class="text-sm text-slate-400 leading-relaxed italic">
              "{{ effectiveDescription }}"
            </p>

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
                  :class="['flex-1 bg-slate-950/60 border border-slate-800 rounded-xl px-4 py-3 text-white placeholder-slate-600 outline-none transition-all font-mono font-bold tracking-wider', accentColorClass.border.replace('border-', 'focus:border-')]"
                  autofocus
                />
                <button
                  type="submit"
                  :disabled="busy || !codeInput.trim()"
                  :class="['px-5 disabled:bg-slate-800 text-slate-950 disabled:text-slate-600 font-bold rounded-xl transition-all flex items-center justify-center gap-1.5 cursor-pointer shadow-lg',
                    effectiveAccent === 'cyan' ? 'bg-cyan-500 hover:bg-cyan-400 shadow-cyan-500/10' : 'bg-amber-500 hover:bg-amber-400 shadow-amber-500/10']"
                >
                  <Unlock class="w-4.5 h-4.5" />
                  <span>Unlock</span>
                </button>
              </form>
            </div>

            <!-- ITEM REQUIREMENT -->
            <div v-else-if="requiredItemId" class="space-y-4">
              <div class="p-4 rounded-2xl bg-slate-950/40 border border-slate-800/80 flex items-start gap-3">
                <div class="w-9 h-9 rounded-lg border flex items-center justify-center shrink-0 mt-0.5"
                     :class="hasRequiredKey ? 'bg-emerald-500/15 border-emerald-500/30' : 'bg-rose-500/15 border-rose-500/30'">
                  <Key class="w-4.5 h-4.5" :class="hasRequiredKey ? 'text-emerald-400' : 'text-rose-400'" />
                </div>
                <div class="space-y-1">
                  <p class="text-xs font-black uppercase tracking-wider" :class="hasRequiredKey ? 'text-emerald-400' : 'text-rose-400'">
                    {{ hasRequiredKey ? 'Item Available' : 'Item Required' }}
                  </p>
                  <p class="text-sm text-slate-300">
                    This {{ entityNoun }} requires a special item to unlock.
                  </p>
                </div>
              </div>

              <!-- Hydrated Item Card -->
              <div v-if="hasRequiredKey && matchingInventoryKey" class="flex items-center gap-4 p-3.5 bg-slate-950/60 border border-slate-800/60 rounded-2xl">
                <div class="w-14 h-14 rounded-xl overflow-hidden border border-slate-800 bg-slate-900 flex items-center justify-center shrink-0">
                  <img
                    v-if="matchingInventoryKey.image_url && showImage(matchingInventoryKey.image_url)"
                    :src="getImageUrl(matchingInventoryKey.image_url)"
                    class="w-full h-full object-cover object-top"
                    @error="handleImageError(matchingInventoryKey.image_url)"
                  />
                  <div v-else class="w-full h-full flex items-center justify-center bg-slate-800/30">
                    <i :class="['ra text-xl', getItemIcon(matchingInventoryKey.item_type ?? undefined), getTypeColor(matchingInventoryKey.item_type ?? undefined)]"></i>
                  </div>
                </div>
                <div class="flex-1 min-w-0 text-left">
                  <h4 class="text-xs font-black text-amber-400 uppercase tracking-wider truncate">
                    {{ matchingInventoryKey.name || matchingInventoryKey.id }}
                  </h4>
                  <p class="text-[11px] text-slate-400 mt-1 leading-normal line-clamp-2">
                    {{ matchingInventoryKey.description || 'A special item carried in your inventory.' }}
                  </p>
                </div>
              </div>

              <div class="flex justify-end pt-1">
                <button
                  v-if="hasRequiredKey"
                  @click="handleUseKey"
                  :disabled="busy"
                  class="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-black uppercase tracking-wider text-xs rounded-xl shadow-lg shadow-emerald-500/10 transition-colors flex items-center justify-center gap-2 cursor-pointer"
                >
                  <Unlock class="w-4 h-4" />
                  <span>Use Item</span>
                </button>
                <div v-else class="w-full text-center text-xs font-bold text-slate-500 uppercase tracking-widest border border-slate-800 py-3 rounded-xl bg-slate-950/20">
                  You do not possess the required item
                </div>
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
                  This container cannot be opened directly. You must satisfy a condition or solve a puzzle in the world first.
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
