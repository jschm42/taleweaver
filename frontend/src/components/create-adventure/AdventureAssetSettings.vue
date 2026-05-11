<script setup lang="ts">
import { ref } from 'vue'
import { ImageIcon, Users, Sword, MapPin, Sparkles } from 'lucide-vue-next'

const props = defineProps<{
  modelValue: {
    automatic_cover_generation: boolean
    generate_npc_images: boolean
    generate_item_images: boolean
    generate_scene_images: boolean
    automatic_npc_voice_assignment: boolean
  }
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: any): void
}>()

const automatedAssetsEnabled = ref(true)

const assetOptions: Array<{
  key: keyof typeof props.modelValue
  label: string
  icon: any
}> = [
  { key: 'automatic_cover_generation', label: 'Cover Art', icon: ImageIcon },
  { key: 'generate_npc_images', label: 'NPC Portraits', icon: Users },
  { key: 'generate_item_images', label: 'Item Icons', icon: Sword },
  { key: 'generate_scene_images', label: 'Scene Visuals', icon: MapPin },
  { key: 'automatic_npc_voice_assignment', label: 'NPC Voices', icon: Sparkles },
]

function toggleAllAssets() {
  automatedAssetsEnabled.value = !automatedAssetsEnabled.value
  const newValue = { ...props.modelValue }
  assetOptions.forEach(opt => {
    newValue[opt.key] = automatedAssetsEnabled.value
  })
  emit('update:modelValue', newValue)
}

function toggleAsset(key: keyof typeof props.modelValue) {
  if (automatedAssetsEnabled.value) return
  emit('update:modelValue', { ...props.modelValue, [key]: !props.modelValue[key] })
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <label class="text-xxs font-black text-white/40 uppercase tracking-[0.2em]">Automated Assets</label>
      <div 
        @click="toggleAllAssets"
        :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', automatedAssetsEnabled ? 'bg-aether-primary' : 'bg-slate-700']"
      >
        <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', automatedAssetsEnabled ? 'left-6' : 'left-1']"></div>
      </div>
    </div>
    
    <div class="grid grid-cols-2 gap-4">
      <button 
        v-for="asset in assetOptions"
        :key="asset.key"
        :disabled="automatedAssetsEnabled"
        @click="toggleAsset(asset.key)"
        class="p-4 rounded-2xl border-2 transition-all flex items-center gap-3 disabled:opacity-40 disabled:cursor-not-allowed"
        :class="modelValue[asset.key] ? 'border-sky-500/50 bg-sky-500/10 text-white' : 'border-white/5 bg-white/5 text-white/40 hover:border-white/10'"
      >
        <component :is="asset.icon" class="w-4 h-4" />
        <span class="text-xxs font-black uppercase tracking-widest">{{ asset.label }}</span>
      </button>
    </div>
  </div>
</template>
