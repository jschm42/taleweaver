<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { ScrollText, ExternalLink, X } from 'lucide-vue-next'

type Accent = 'emerald' | 'amber'

const props = withDefaults(
  defineProps<{
    creator?: string | null
    copyright?: string | null
    license?: string | null
    licenseUrl?: string | null
    accent?: Accent
    open?: boolean
    anchorEl?: HTMLElement | null
  }>(),
  {
    accent: 'emerald' as Accent,
    open: false,
    anchorEl: null,
  },
)

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()

const popupRef = ref<HTMLElement | null>(null)
const popupStyle = ref<Record<string, string>>({})

const hasContent = computed(() => {
  return !!(props.creator || props.copyright || props.license || props.licenseUrl)
})

const accentClasses = computed(() => {
  if (props.accent === 'amber') {
    return {
      border: 'border-amber-400/30',
      headerBorder: 'border-amber-400/20',
      iconBg: 'bg-amber-500/15 border-amber-400/30',
      icon: 'text-amber-300',
      title: 'text-amber-300',
      value: 'text-amber-100',
      link: 'text-emerald-400 hover:text-emerald-300',
    }
  }
  return {
    border: 'border-emerald-400/30',
    headerBorder: 'border-emerald-400/20',
    iconBg: 'bg-emerald-500/15 border-emerald-400/30',
    icon: 'text-emerald-300',
    title: 'text-emerald-300',
    value: 'text-emerald-100',
    link: 'text-cyan-400 hover:text-cyan-300',
  }
})

const updatePopupPosition = async () => {
  const anchor = props.anchorEl
  if (!anchor) return
  await nextTick()
  const rect = anchor.getBoundingClientRect()
  const popupWidth = Math.min(320, window.innerWidth - 16)
  let left = rect.left
  if (left + popupWidth > window.innerWidth - 8) {
    left = window.innerWidth - popupWidth - 8
  }
  if (left < 8) left = 8
  popupStyle.value = {
    position: 'fixed',
    top: `${Math.round(rect.bottom + 8)}px`,
    left: `${Math.round(left)}px`,
    width: `${popupWidth}px`,
    zIndex: '9999',
  }
}

const close = () => emit('update:open', false)

const onDocumentClick = (event: MouseEvent) => {
  if (!props.open) return
  const target = event.target as Node
  if (props.anchorEl?.contains(target)) return
  if (popupRef.value?.contains(target)) return
  close()
}

const onKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && props.open) close()
}

const onResizeOrScroll = () => {
  if (props.open) void updatePopupPosition()
}

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) await updatePopupPosition()
  },
)

watch(
  () => props.anchorEl,
  () => {
    if (props.open) void updatePopupPosition()
  },
)

onMounted(() => {
  document.addEventListener('mousedown', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
  window.addEventListener('resize', onResizeOrScroll)
  window.addEventListener('scroll', onResizeOrScroll, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
  window.removeEventListener('resize', onResizeOrScroll)
  window.removeEventListener('scroll', onResizeOrScroll, true)
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-1 scale-95"
      enter-to-class="opacity-100 translate-y-0 scale-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0 scale-100"
      leave-to-class="opacity-0 -translate-y-1 scale-95"
    >
      <div
        v-if="open && hasContent"
        ref="popupRef"
        :style="popupStyle"
        class="p-4 rounded-2xl bg-slate-900/95 backdrop-blur-xl border shadow-2xl shadow-black/50"
        :class="accentClasses.border"
      >
        <div
          class="flex items-start justify-between gap-2 mb-3 pb-2 border-b"
          :class="accentClasses.headerBorder"
        >
          <div class="flex items-center gap-2">
            <div class="p-1.5 rounded-lg border" :class="accentClasses.iconBg">
              <ScrollText class="w-3.5 h-3.5" :class="accentClasses.icon" />
            </div>
            <span
              class="text-[10px] font-black uppercase tracking-[0.25em]"
              :class="accentClasses.title"
            >
              License & Credits
            </span>
          </div>
          <button
            @click="close"
            class="p-1 rounded-md text-slate-500 hover:text-white hover:bg-white/5 transition-colors"
            title="Close"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        </div>

        <dl class="space-y-2.5 text-[11px]">
          <div v-if="props.license">
            <dt class="text-[9px] font-black uppercase tracking-[0.2em] mb-0.5 text-slate-500">
              License
            </dt>
            <dd class="font-bold break-words" :class="accentClasses.value">{{ props.license }}</dd>
          </div>
          <div v-if="props.licenseUrl">
            <dt class="text-[9px] font-black uppercase tracking-[0.2em] mb-0.5 text-slate-500">
              License URL
            </dt>
            <dd>
              <a
                :href="props.licenseUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-start gap-1 hover:underline break-all transition-colors"
                :class="accentClasses.link"
              >
                <span class="break-all">{{ props.licenseUrl }}</span>
                <ExternalLink class="w-3 h-3 mt-0.5 shrink-0" />
              </a>
            </dd>
          </div>
          <div v-if="props.creator">
            <dt class="text-[9px] font-black uppercase tracking-[0.2em] mb-0.5 text-slate-500">
              Creator
            </dt>
            <dd class="text-slate-200 break-words">{{ props.creator }}</dd>
          </div>
          <div v-if="props.copyright">
            <dt class="text-[9px] font-black uppercase tracking-[0.2em] mb-0.5 text-slate-500">
              Copyright
            </dt>
            <dd class="text-slate-200 break-words">{{ props.copyright }}</dd>
          </div>
        </dl>
      </div>
    </Transition>
  </Teleport>
</template>
