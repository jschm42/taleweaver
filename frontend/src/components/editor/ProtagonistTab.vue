<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Plus, Trash2, Hammer } from 'lucide-vue-next'
import { formatObjectIds } from '@/utils/editor_utils'
import InlineEditableField from '@/components/editor/InlineEditableField.vue'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'

const props = defineProps<{
  debugData: any
  isQuickGenerating: Record<string, boolean>
  activeMenuId: string | null
  visualsCacheVersion: number
  ruleEnforcementMode: string
  isSavingText: boolean
  referenceOptions: any[]
}>()

const emit = defineEmits<{
  (e: 'quick-regen', kind: string, id: string): void
  (e: 'open-regen-dialog', kind: string, id: string, label: string): void
  (e: 'open-upload-picker', kind: string, id: string, label: string): void
  (e: 'download-asset', path: string, label: string): void
  (e: 'toggle-menu', id: string, event: MouseEvent): void
  (e: 'save-field', field: string, value: any): void
  (e: 'create-new-item', target: { type: 'equipment' | 'inventory'; key?: string; index?: number }): void
}>()

const activeEditId = ref<string | null>(null)

function buildVisualImageUrl(imagePath?: string | null) {
  if (!imagePath) return ''
  return `${imagePath}?v=${props.visualsCacheVersion}`
}

const objectOptions = computed(() => {
  return (props.referenceOptions || []).filter((opt: any) => opt.type === 'OBJECT')
})

const equipmentSlots = [
  { key: 'Head', label: 'Head Gear', icon: 'ra ra-knight-helmet' },
  { key: 'Neck', label: 'Necklace / Amulet', icon: 'ra ra-gem-pendant' },
  { key: 'Chest', label: 'Armor / Chest', icon: 'ra ra-torso' },
  { key: 'Arms', label: 'Bracers / Arms', icon: 'ra ra-bracers' },
  { key: 'Hands', label: 'Gloves / Hands', icon: 'ra ra-gloves' },
  { key: 'Legs', label: 'Greaves / Legs', icon: 'ra ra-layered-armor' },
  { key: 'Feet', label: 'Boots / Feet', icon: 'ra ra-boot-prints' },
  { key: 'Ring_1', label: 'Left Ring', icon: 'ra ra-double-ring' },
  { key: 'Ring_2', label: 'Right Ring', icon: 'ra ra-double-ring' },
  { key: 'MainHand', label: 'Main Hand Weapon', icon: 'ra ra-sword-brandish' },
  { key: 'OffHand', label: 'Off Hand Shield/Weapon', icon: 'ra ra-shield' },
]

const localInventory = ref<string[]>([])

watch(() => props.debugData?.protagonist?.inventory, (newVal) => {
  if (newVal) {
    localInventory.value = newVal.map((item: any) => {
      if (typeof item === 'string') return item
      return item?.id || ''
    })
  } else {
    localInventory.value = []
  }
}, { immediate: true })

function addInventoryItem() {
  localInventory.value.push('')
}

function updateInventoryItem(index: number, itemId: string) {
  localInventory.value[index] = itemId
  saveInventory()
}

function removeInventoryItem(index: number) {
  localInventory.value.splice(index, 1)
  saveInventory()
}

function saveInventory() {
  emit('save-field', 'inventory', localInventory.value.filter(id => id !== ''))
}

function getEquipmentSlotItemId(slotKey: string): string {
  const item = props.debugData?.protagonist?.equipment?.[slotKey]
  if (!item) return ''
  if (typeof item === 'string') return item
  return item.id || ''
}

function saveEquipmentSlot(slotKey: string, itemId: string) {
  const currentEquipment = props.debugData?.protagonist?.equipment || {}
  const updatedEquipment = Object.entries(currentEquipment).reduce((acc: any, [k, v]: [string, any]) => {
    acc[k] = v ? (typeof v === 'string' ? v : (v?.id || null)) : null
    return acc
  }, {})
  updatedEquipment[slotKey] = itemId || null
  emit('save-field', 'equipment', updatedEquipment)
}
</script>

<template>
  <div class="space-y-8 animate-page-in">
    <section v-if="debugData?.protagonist" class="space-y-4 bg-slate-900/40 p-8 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">The Protagonist</h3>
      </div>

      <div class="bg-black/20 border border-white/5 rounded-3xl p-6 flex flex-col md:flex-row gap-6 backdrop-blur-md shadow-inner">
        <div class="shrink-0 relative group">
          <div class="w-full md:w-56 h-72 md:h-80 rounded-2xl overflow-hidden bg-slate-800 border border-white/10 shadow-lg relative">
            <img
              v-if="debugData.protagonist.profile_image"
              :src="buildVisualImageUrl(debugData.protagonist.profile_image)"
              class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
            />
            <div v-else class="absolute inset-0 flex items-center justify-center text-slate-600">
              <i class="ra ra-person text-4xl"></i>
            </div>
            <div v-if="isQuickGenerating['protagonist_' + debugData.protagonist.id]" class="absolute inset-0 bg-slate-950/70 backdrop-blur-sm flex items-center justify-center z-10">
              <i class="ra ra-cycle animate-spin text-2xl text-emerald-500"></i>
            </div>
          </div>
          <div class="absolute top-1.5 right-1.5 z-40">
            <button @click="emit('toggle-menu', debugData.protagonist.id, $event)" class="w-6 h-6 rounded-full bg-black/70 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg">
              <div class="flex flex-col gap-[3px]">
                <div class="w-[3px] h-[3px] bg-white rounded-full"></div>
                <div class="w-[3px] h-[3px] bg-white rounded-full"></div>
                <div class="w-[3px] h-[3px] bg-white rounded-full"></div>
              </div>
            </button>
            <div v-if="activeMenuId === debugData.protagonist.id" class="absolute right-0 mt-1.5 w-52 bg-slate-900 border border-white/20 rounded-xl shadow-2xl overflow-hidden py-1.5 z-[200] animate-fade-in ring-1 ring-white/5">
              <button @click="emit('quick-regen', 'protagonist', debugData.protagonist.id)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regenerate Portrait</button>
              <button @click="emit('open-regen-dialog', 'protagonist', debugData.protagonist.id, debugData.protagonist.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regenerate (Prompt)</button>
              <button @click="emit('open-upload-picker', 'protagonist', debugData.protagonist.id, debugData.protagonist.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Portrait</button>
              <button v-if="debugData.protagonist.profile_image" @click="emit('download-asset', debugData.protagonist.profile_image, `${debugData.protagonist.name || 'protagonist'}_portrait`)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Portrait</button>
            </div>
          </div>
        </div>

        <div class="flex-grow min-w-0 space-y-4">
          <div class="space-y-1">
            <InlineEditableField
              :value="debugData.protagonist.name"
              type="text"
              :maxlength="50"
              required
              :is-saving="isSavingText"
              edit-id="name"
              :active-edit-id="activeEditId"
              display-class="group cursor-pointer bg-black/10 hover:bg-black/30 border border-white/5 hover:border-emerald-500/30 rounded-xl px-3 py-1.5 transition-all duration-300 shadow-inner flex justify-between items-center w-full min-h-[40px]"
              @save="emit('save-field', 'name', $event)"
              @start-edit="activeEditId = $event"
            >
              <template #default="{ value }">
                <h4 class="text-xl font-black text-white tracking-tight">{{ value }}</h4>
              </template>
            </InlineEditableField>
            <p class="text-sm font-bold text-emerald-400/70 uppercase tracking-widest mt-0.5 px-3">{{ debugData.protagonist.role || 'Protagonist' }}</p>
          </div>

          <!-- RPG & Status Stats Grid -->
          <div v-if="ruleEnforcementMode !== 'chat'" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
            <!-- HP -->
            <div class="space-y-1">
              <span class="text-xs font-black text-slate-400 uppercase tracking-widest px-1">Hit Points</span>
              <InlineEditableField
                :value="debugData.protagonist.hp ?? 20"
                type="number"
                :min="0"
                :max="999"
                required
                :is-saving="isSavingText"
                edit-id="hp"
                :active-edit-id="activeEditId"
                display-class="group cursor-pointer bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center w-full min-h-[46px]"
                input-class="flex-grow min-w-0 bg-black/60 border border-emerald-500/50 rounded px-2 py-0.5 text-base font-bold text-white outline-none animate-fade-in"
                @save="emit('save-field', 'hp', $event)"
                @start-edit="activeEditId = $event"
              >
                <template #default="{ value }">
                  <div class="flex items-center justify-between w-full">
                    <div class="flex items-center gap-1.5 text-red-400">
                      <i class="ra ra-heart text-[14px]"></i>
                      <span class="text-xs font-black">HP</span>
                    </div>
                    <span class="text-base font-black text-white">{{ value ?? '-' }}</span>
                  </div>
                </template>
              </InlineEditableField>
            </div>

            <!-- STM -->
            <div class="space-y-1">
              <span class="text-xs font-black text-slate-400 uppercase tracking-widest px-1">Stamina</span>
              <InlineEditableField
                :value="debugData.protagonist.stamina ?? 20"
                type="number"
                :min="0"
                :max="999"
                required
                :is-saving="isSavingText"
                edit-id="stamina"
                :active-edit-id="activeEditId"
                display-class="group cursor-pointer bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center w-full min-h-[46px]"
                input-class="flex-grow min-w-0 bg-black/60 border border-emerald-500/50 rounded px-2 py-0.5 text-base font-bold text-white outline-none animate-fade-in"
                @save="emit('save-field', 'stamina', $event)"
                @start-edit="activeEditId = $event"
              >
                <template #default="{ value }">
                  <div class="flex items-center justify-between w-full">
                    <div class="flex items-center gap-1.5 text-emerald-400">
                      <i class="ra ra-muscle-up text-[14px]"></i>
                      <span class="text-xs font-black">STM</span>
                    </div>
                    <span class="text-base font-black text-white">{{ value ?? '-' }}</span>
                  </div>
                </template>
              </InlineEditableField>
            </div>

            <!-- MAN -->
            <div class="space-y-1">
              <span class="text-xs font-black text-slate-400 uppercase tracking-widest px-1">Mana</span>
              <InlineEditableField
                :value="debugData.protagonist.mana ?? 20"
                type="number"
                :min="0"
                :max="999"
                required
                :is-saving="isSavingText"
                edit-id="mana"
                :active-edit-id="activeEditId"
                display-class="group cursor-pointer bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center w-full min-h-[46px]"
                input-class="flex-grow min-w-0 bg-black/60 border border-emerald-500/50 rounded px-2 py-0.5 text-base font-bold text-white outline-none animate-fade-in"
                @save="emit('save-field', 'mana', $event)"
                @start-edit="activeEditId = $event"
              >
                <template #default="{ value }">
                  <div class="flex items-center justify-between w-full">
                    <div class="flex items-center gap-1.5 text-blue-400">
                      <i class="ra ra-crystal-ball text-[14px]"></i>
                      <span class="text-xs font-black">MAN</span>
                    </div>
                    <span class="text-base font-black text-white">{{ value ?? '-' }}</span>
                  </div>
                </template>
              </InlineEditableField>
            </div>

            <!-- STR -->
            <div class="space-y-1">
              <span class="text-xs font-black text-slate-400 uppercase tracking-widest px-1">Strength</span>
              <InlineEditableField
                :value="debugData.protagonist.strength ?? 10"
                type="number"
                :min="1"
                :max="99"
                required
                :is-saving="isSavingText"
                edit-id="strength"
                :active-edit-id="activeEditId"
                display-class="group cursor-pointer bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center w-full min-h-[46px]"
                input-class="flex-grow min-w-0 bg-black/60 border border-emerald-500/50 rounded px-2 py-0.5 text-base font-bold text-white outline-none animate-fade-in"
                @save="emit('save-field', 'strength', $event)"
                @start-edit="activeEditId = $event"
              >
                <template #default="{ value }">
                  <div class="flex items-center justify-between w-full">
                    <div class="flex items-center gap-1.5 text-amber-400">
                      <i class="ra ra-sword-brandish text-[14px]"></i>
                      <span class="text-xs font-black">STR</span>
                    </div>
                    <span class="text-base font-black text-white">{{ value ?? '-' }}</span>
                  </div>
                </template>
              </InlineEditableField>
            </div>

            <!-- DEX -->
            <div class="space-y-1">
              <span class="text-xs font-black text-slate-400 uppercase tracking-widest px-1">Dexterity</span>
              <InlineEditableField
                :value="debugData.protagonist.dexterity ?? 10"
                type="number"
                :min="1"
                :max="99"
                required
                :is-saving="isSavingText"
                edit-id="dexterity"
                :active-edit-id="activeEditId"
                display-class="group cursor-pointer bg-teal-500/10 hover:bg-teal-500/20 border border-teal-500/20 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center w-full min-h-[46px]"
                input-class="flex-grow min-w-0 bg-black/60 border border-emerald-500/50 rounded px-2 py-0.5 text-base font-bold text-white outline-none animate-fade-in"
                @save="emit('save-field', 'dexterity', $event)"
                @start-edit="activeEditId = $event"
              >
                <template #default="{ value }">
                  <div class="flex items-center justify-between w-full">
                    <div class="flex items-center gap-1.5 text-teal-400">
                      <i class="ra ra-arrow-flight text-[14px]"></i>
                      <span class="text-xs font-black">DEX</span>
                    </div>
                    <span class="text-base font-black text-white">{{ value ?? '-' }}</span>
                  </div>
                </template>
              </InlineEditableField>
            </div>

            <!-- INT -->
            <div class="space-y-1">
              <span class="text-xs font-black text-slate-400 uppercase tracking-widest px-1">Intelligence</span>
              <InlineEditableField
                :value="debugData.protagonist.intelligence ?? 10"
                type="number"
                :min="1"
                :max="99"
                required
                :is-saving="isSavingText"
                edit-id="intelligence"
                :active-edit-id="activeEditId"
                display-class="group cursor-pointer bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center w-full min-h-[46px]"
                input-class="flex-grow min-w-0 bg-black/60 border border-emerald-500/50 rounded px-2 py-0.5 text-base font-bold text-white outline-none animate-fade-in"
                @save="emit('save-field', 'intelligence', $event)"
                @start-edit="activeEditId = $event"
              >
                <template #default="{ value }">
                  <div class="flex items-center justify-between w-full">
                    <div class="flex items-center gap-1.5 text-indigo-400">
                      <i class="ra ra-brain text-[14px]"></i>
                      <span class="text-xs font-black">INT</span>
                    </div>
                    <span class="text-base font-black text-white">{{ value ?? '-' }}</span>
                  </div>
                </template>
              </InlineEditableField>
            </div>

            <!-- WIS -->
            <div class="space-y-1">
              <span class="text-xs font-black text-slate-400 uppercase tracking-widest px-1">Wisdom</span>
              <InlineEditableField
                :value="debugData.protagonist.wisdom ?? 10"
                type="number"
                :min="1"
                :max="99"
                required
                :is-saving="isSavingText"
                edit-id="wisdom"
                :active-edit-id="activeEditId"
                display-class="group cursor-pointer bg-fuchsia-500/10 hover:bg-fuchsia-500/20 border border-fuchsia-500/20 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center w-full min-h-[46px]"
                input-class="flex-grow min-w-0 bg-black/60 border border-emerald-500/50 rounded px-2 py-0.5 text-base font-bold text-white outline-none animate-fade-in"
                @save="emit('save-field', 'wisdom', $event)"
                @start-edit="activeEditId = $event"
              >
                <template #default="{ value }">
                  <div class="flex items-center justify-between w-full">
                    <div class="flex items-center gap-1.5 text-fuchsia-400">
                      <i class="ra ra-eye-shield text-[14px]"></i>
                      <span class="text-xs font-black">WIS</span>
                    </div>
                    <span class="text-base font-black text-white">{{ value ?? '-' }}</span>
                  </div>
                </template>
              </InlineEditableField>
            </div>

            <!-- CHA -->
            <div class="space-y-1">
              <span class="text-xs font-black text-slate-400 uppercase tracking-widest px-1">Charisma</span>
              <InlineEditableField
                :value="debugData.protagonist.charisma ?? 10"
                type="number"
                :min="1"
                :max="99"
                required
                :is-saving="isSavingText"
                edit-id="charisma"
                :active-edit-id="activeEditId"
                display-class="group cursor-pointer bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center w-full min-h-[46px]"
                input-class="flex-grow min-w-0 bg-black/60 border border-emerald-500/50 rounded px-2 py-0.5 text-base font-bold text-white outline-none animate-fade-in"
                @save="emit('save-field', 'charisma', $event)"
                @start-edit="activeEditId = $event"
              >
                <template #default="{ value }">
                  <div class="flex items-center justify-between w-full">
                    <div class="flex items-center gap-1.5 text-rose-400">
                      <i class="ra ra-crowned-heart text-[14px]"></i>
                      <span class="text-xs font-black">CHA</span>
                    </div>
                    <span class="text-base font-black text-white">{{ value ?? '-' }}</span>
                  </div>
                </template>
              </InlineEditableField>
            </div>

            <!-- AC -->
            <div class="space-y-1">
              <span class="text-xs font-black text-slate-400 uppercase tracking-widest px-1">Armor Class</span>
              <InlineEditableField
                :value="debugData.protagonist.armor_class ?? 10"
                type="number"
                :min="1"
                :max="99"
                required
                :is-saving="isSavingText"
                edit-id="armor_class"
                :active-edit-id="activeEditId"
                display-class="group cursor-pointer bg-slate-500/10 hover:bg-slate-500/20 border border-slate-500/20 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center w-full min-h-[46px]"
                input-class="flex-grow min-w-0 bg-black/60 border border-emerald-500/50 rounded px-2 py-0.5 text-base font-bold text-white outline-none animate-fade-in"
                @save="emit('save-field', 'armor_class', $event)"
                @start-edit="activeEditId = $event"
              >
                <template #default="{ value }">
                  <div class="flex items-center justify-between w-full">
                    <div class="flex items-center gap-1.5 text-slate-400">
                      <i class="ra ra-shield text-[14px]"></i>
                      <span class="text-xs font-black">AC</span>
                    </div>
                    <span class="text-base font-black text-white">{{ value ?? '-' }}</span>
                  </div>
                </template>
              </InlineEditableField>
            </div>

            <!-- EXP -->
            <div class="space-y-1">
              <span class="text-xs font-black text-slate-400 uppercase tracking-widest px-1">Experience</span>
              <InlineEditableField
                :value="debugData.protagonist.exp ?? 0"
                type="number"
                :min="0"
                required
                :is-saving="isSavingText"
                edit-id="exp"
                :active-edit-id="activeEditId"
                display-class="group cursor-pointer bg-yellow-500/10 hover:bg-yellow-500/20 border border-yellow-500/20 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center w-full min-h-[46px]"
                input-class="flex-grow min-w-0 bg-black/60 border border-emerald-500/50 rounded px-2 py-0.5 text-base font-bold text-white outline-none animate-fade-in"
                @save="emit('save-field', 'exp', $event)"
                @start-edit="activeEditId = $event"
              >
                <template #default="{ value }">
                  <div class="flex items-center justify-between w-full">
                    <div class="flex items-center gap-1.5 text-yellow-400">
                      <i class="ra ra-player-king text-[14px]"></i>
                      <span class="text-xs font-black">EXP</span>
                    </div>
                    <span class="text-base font-black text-white">{{ value ?? '-' }}</span>
                  </div>
                </template>
              </InlineEditableField>
            </div>
          </div>

          <div class="grid grid-cols-1 gap-3">
            <div class="space-y-1">
              <span class="text-xs font-black text-slate-500 uppercase tracking-widest px-1">Bio</span>
              <InlineEditableField
                :value="debugData.protagonist.description ?? ''"
                type="textarea"
                :maxlength="1000"
                required
                :use-references="true"
                :reference-options="referenceOptions"
                :is-saving="isSavingText"
                edit-id="description"
                :active-edit-id="activeEditId"
                empty-text="No biography set. Click to describe your character."
                display-class="group cursor-pointer bg-black/10 hover:bg-black/30 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-3 transition-all duration-300 shadow-inner flex justify-between items-start w-full min-h-[50px]"
                @save="emit('save-field', 'description', $event)"
                @start-edit="activeEditId = $event"
              >
                <template #default="{ value }">
                  <p class="text-sm text-slate-200 leading-relaxed" v-html="formatObjectIds(String(value))"></p>
                </template>
              </InlineEditableField>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div class="space-y-1">
                <span class="text-xs font-black text-slate-500 uppercase tracking-widest px-1">Motivation</span>
                <InlineEditableField
                  :value="debugData.protagonist.goal ?? ''"
                  type="textarea"
                  :maxlength="200"
                  :use-references="true"
                  :reference-options="referenceOptions"
                  :is-saving="isSavingText"
                  edit-id="goal"
                  :active-edit-id="activeEditId"
                  empty-text="No motivation set. Click to add details."
                  display-class="group cursor-pointer bg-black/10 hover:bg-black/30 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-3 transition-all duration-300 shadow-inner flex justify-between items-start w-full min-h-[50px]"
                  @save="emit('save-field', 'goal', $event)"
                  @start-edit="activeEditId = $event"
                >
                  <template #default="{ value }">
                    <p class="text-sm text-slate-200 leading-relaxed" v-html="formatObjectIds(String(value))"></p>
                  </template>
                </InlineEditableField>
              </div>

              <div class="space-y-1">
                <span class="text-xs font-black text-slate-500 uppercase tracking-widest px-1">Traits</span>
                <InlineEditableField
                  :value="debugData.protagonist.character ?? ''"
                  type="textarea"
                  :maxlength="200"
                  :use-references="true"
                  :reference-options="referenceOptions"
                  :is-saving="isSavingText"
                  edit-id="character"
                  :active-edit-id="activeEditId"
                  empty-text="No traits set. Click to add details."
                  display-class="group cursor-pointer bg-black/10 hover:bg-black/30 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-3 transition-all duration-300 shadow-inner flex justify-between items-start w-full min-h-[50px]"
                  @save="emit('save-field', 'character', $event)"
                  @start-edit="activeEditId = $event"
                >
                  <template #default="{ value }">
                    <p class="text-sm text-slate-200 leading-relaxed" v-html="formatObjectIds(String(value))"></p>
                  </template>
                </InlineEditableField>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Equipment & Starting Inventory Sections -->
    <section v-if="debugData?.protagonist && ruleEnforcementMode !== 'chat'" class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6 animate-page-in">
      <!-- Starting Equipment Slots -->
      <div class="bg-slate-900/40 p-8 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl flex flex-col space-y-4">
        <div class="flex items-center gap-2 border-b border-white/5 pb-3">
          <i class="ra ra-knight-helmet text-xl text-emerald-400"></i>
          <h4 class="text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Starting Equipment Slots</h4>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div v-for="slot in equipmentSlots" :key="slot.key" class="bg-black/20 p-4 rounded-2xl border border-white/5 flex flex-col space-y-2">
            <div class="flex items-center gap-2 text-xs font-bold text-slate-400">
              <i :class="[slot.icon, 'text-emerald-500/80 text-sm']"></i>
              <span>{{ slot.label }}</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="flex-grow min-w-0">
                <EntityReferenceCombobox
                  :model-value="getEquipmentSlotItemId(slot.key)"
                  :options="objectOptions"
                  placeholder="Empty Slot"
                  @update:model-value="saveEquipmentSlot(slot.key, $event)"
                />
              </div>
              <button
                type="button"
                @click="emit('create-new-item', { type: 'equipment', key: slot.key })"
                class="p-2 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 hover:border-emerald-500/40 text-emerald-400 rounded-xl transition-all shrink-0 flex items-center justify-center"
                title="Create a Brand New Item Template for this Slot"
              >
                <Hammer class="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Starting Inventory Backpack -->
      <div class="bg-slate-900/40 p-8 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl flex flex-col space-y-4">
        <div class="flex items-center justify-between border-b border-white/5 pb-3">
          <div class="flex items-center gap-2">
            <i class="ra ra-backpack text-xl text-emerald-400"></i>
            <h4 class="text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Starting Inventory</h4>
          </div>
          <div class="flex gap-2">
            <button
              @click="addInventoryItem"
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 text-xs font-bold text-emerald-400 transition-all"
              title="Add a slot to select an existing item"
            >
              <Plus class="w-3.5 h-3.5" />
              <span>Select Item</span>
            </button>
            <button
              @click="emit('create-new-item', { type: 'inventory' })"
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 text-xs font-bold text-emerald-400 transition-all"
              title="Create a brand new item template and add to inventory"
            >
              <Hammer class="w-3.5 h-3.5" />
              <span>Create New</span>
            </button>
          </div>
        </div>

        <div class="space-y-3 max-h-[600px] overflow-y-auto pr-1">
          <div
            v-for="(itemId, index) in localInventory"
            :key="index"
            class="bg-black/20 p-4 rounded-2xl border border-white/5 flex items-center gap-3"
          >
            <span class="text-xs font-bold text-slate-500 w-6 shrink-0">#{{ index + 1 }}</span>
            <div class="flex-grow min-w-0 flex items-center gap-2">
              <div class="flex-grow min-w-0">
                <EntityReferenceCombobox
                  :model-value="itemId"
                  :options="objectOptions"
                  placeholder="Select item to add..."
                  @update:model-value="updateInventoryItem(index, $event)"
                />
              </div>
              <button
                type="button"
                @click="emit('create-new-item', { type: 'inventory', index })"
                class="p-2 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 hover:border-emerald-500/40 text-emerald-400 rounded-xl transition-all shrink-0 flex items-center justify-center"
                title="Create a Brand New Item Template and assign to this Slot"
              >
                <Hammer class="w-4 h-4" />
              </button>
            </div>
            <button
              @click="removeInventoryItem(index)"
              class="p-2.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 hover:border-red-500/40 text-red-400 rounded-xl transition-all"
              title="Remove from Inventory"
            >
              <Trash2 class="w-4 h-4" />
            </button>
          </div>

          <div v-if="localInventory.length === 0" class="text-center py-12 text-slate-500 text-xs italic">
            Backpack is empty. Click "Select Item" or "Create New" to add starting items.
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.animate-page-in { animation: pageIn 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes pageIn { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
</style>
