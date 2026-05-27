<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'

interface MenuItem {
  label: string
  action: string
}

const props = defineProps<{
  x: number
  y: number
  items: MenuItem[]
  title?: string
}>()

const emit = defineEmits<{
  close: []
  select: [item: MenuItem]
}>()

const menuRef = ref<HTMLElement | null>(null)

const menuStyle = computed(() => {
  // Ensure menu doesn't go off screen
  const x = props.x
  const y = props.y
  const width = 180
  const height = props.items.length * 40 + (props.title ? 40 : 0)

  let left = x
  let top = y

  if (x + width > window.innerWidth) {
    left = x - width
  }
  if (y + height > window.innerHeight) {
    top = y - height
  }

  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`
  }
})

function handleClickOutside(event: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(event.target as Node)) {
    emit('close')
  }
}

onMounted(() => {
  document.addEventListener('mousedown', handleClickOutside)
  // Close on escape
  const handleEsc = (e: KeyboardEvent) => {
    if (e.key === 'Escape') emit('close')
  }
  document.addEventListener('keydown', handleEsc)
  onBeforeUnmount(() => {
    document.removeEventListener('mousedown', handleClickOutside)
    document.removeEventListener('keydown', handleEsc)
  })
})
</script>

<template>
  <div
    ref="menuRef"
    class="fixed z-[9999] bg-slate-900/95 backdrop-blur-xl border border-slate-700/50 rounded-2xl shadow-2xl overflow-hidden py-1.5 animate-in fade-in zoom-in duration-200"
    :style="menuStyle"
  >
    <div v-if="title" class="px-4 py-2 border-b border-slate-700/30 mb-1">
      <span class="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">{{ title }}</span>
    </div>
    <button
      v-for="item in items"
      :key="item.label"
      class="w-full flex items-center px-4 py-2.5 hover:bg-white/10 transition-colors text-left group"
      @click="emit('select', item)"
    >
      <span class="text-xs font-bold text-slate-200 group-hover:text-white capitalize tracking-wide">{{ item.label }}</span>
    </button>
  </div>
</template>

<style scoped>
.animate-in {
  animation: animate-in 0.2s ease-out;
}
@keyframes animate-in {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
