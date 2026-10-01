<script setup lang="ts">
import { ref } from 'vue'
import { ImageIcon, Users, Sword, MapPin, Sparkles, Layers } from 'lucide-vue-next'
import InfoPopoverButton from '@/components/create-adventure/InfoPopoverButton.vue'
import { CREATE_ADVENTURE_HELP_TEXTS } from '@/constants/createAdventureHelpTexts'

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
  <div class="bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-2xl md:rounded-3xl p-3.5 sm:p-5 md:p-6 flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between gap-3 mb-3 sm:mb-4">
      <div class="flex items-center gap-2.5 sm:gap-3 min-w-0">
        <div class="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-sky-500/20 text-sky-400 flex items-center justify-center shrink-0 shadow-sm">
          <Layers class="w-4 h-4 sm:w-5 sm:h-5" />
        </div>
        <div class="min-w-0">
          <h3 class="text-xs sm:text-sm font-black text-white uppercase tracking-[0.18em] truncate">Asset Automation</h3>
          <p class="text-[10px] sm:text-xxs text-white/40 uppercase tracking-widest truncate">Procedural media generation</p>
        </div>
      </div>

      <div class="flex items-center gap-2 sm:gap-3 shrink-0">
        <InfoPopoverButton
          title="Asset Automation"
          :text="CREATE_ADVENTURE_HELP_TEXTS.assetAutomation"
        />

        <!-- Toggle Switch -->
        <button
          type="button"
          @click="toggleAllAssets"
          class="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-2.5 py-1 rounded-xl border border-white/10 bg-black/30 hover:border-white/20 transition-all cursor-pointer select-none"
          :title="automatedAssetsEnabled ? 'Automated assets enabled' : 'Automated assets disabled (manual selection)'"
        >
          <span class="text-[10px] font-black uppercase tracking-wider" :class="automatedAssetsEnabled ? 'text-sky-300' : 'text-slate-400'">
            Auto
          </span>
          <div
            :class="['w-8 h-4 sm:w-9 sm:h-4.5 rounded-full relative transition-colors shrink-0', automatedAssetsEnabled ? 'bg-sky-500' : 'bg-slate-700']"
          >
            <div :class="['absolute top-0.5 w-3 h-3 sm:w-3.5 sm:h-3.5 bg-white rounded-full transition-all shadow-sm', automatedAssetsEnabled ? 'left-4 sm:left-5' : 'left-0.5']"></div>
          </div>
        </button>
      </div>
    </div>

    <!-- Asset Buttons Grid -->
    <div class="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-3 gap-2 sm:gap-2.5">
      <button
        v-for="(asset, idx) in assetOptions"
        :key="asset.key"
        :disabled="automatedAssetsEnabled"
        @click="toggleAsset(asset.key)"
        class="p-2 sm:p-2.5 rounded-xl border transition-all flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed text-left cursor-pointer active:scale-95"
        :class="[
          modelValue[asset.key] ? 'border-sky-500/50 bg-sky-500/10 text-white shadow-sm' : 'border-white/5 bg-white/5 text-white/40 hover:border-white/10',
          idx === 4 ? 'col-span-2 md:col-span-1' : ''
        ]"
      >
        <component :is="asset.icon" class="w-3.5 h-3.5 shrink-0" />
        <span class="text-[11px] sm:text-xxs font-black uppercase tracking-wider truncate">{{ asset.label }}</span>
      </button>
    </div>
  </div>
</template>
