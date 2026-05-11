<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  gameForm: any
  isSubmitting: boolean
}>()

const emit = defineEmits<{
  (e: 'save', payload: any): void
}>()

const localForm = ref({ ...props.gameForm })

watch(() => props.gameForm, (newVal) => {
  localForm.value = { ...newVal }
}, { deep: true })
</script>

<template>
  <div class="space-y-8 animate-fade-in">
    <div>
      <h1 class="text-4xl font-extrabold text-white mb-2">Game Preferences</h1>
      <p class="text-slate-400">Configure global interface and gameplay options.</p>
    </div>

    <div class="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
      <div class="p-6 bg-slate-950/40 border border-slate-800/40 rounded-2xl space-y-6">
        <!-- Clock Settings -->
        <div class="flex items-center justify-between p-4 bg-slate-900/60 rounded-xl border border-white/5">
          <div>
            <div class="text-sm font-bold text-white">24-Hour Format</div>
            <div class="text-xs text-slate-500">Enable to use 24h clock, otherwise 12h (AM/PM) is used.</div>
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input type="checkbox" v-model="localForm.clock_24h" class="sr-only peer">
            <div class="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
          </label>
        </div>

        <!-- Date Format Settings -->
        <div class="flex items-center justify-between p-4 bg-slate-900/60 rounded-xl border border-white/5">
          <div>
            <div class="text-sm font-bold text-white">Date Format</div>
            <div class="text-xs text-slate-500">Choose how the in-game date is presented.</div>
          </div>
          <select 
            v-model="localForm.date_format"
            class="bg-slate-950 border border-slate-800 text-white text-xs rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block p-2 px-4"
          >
            <option value="DD.MM.YY">DD.MM.YY (e.g. 24.12.26)</option>
            <option value="MM/DD/YY">MM/DD/YY (e.g. 12/24/26)</option>
            <option value="YY-MM-DD">YY-MM-DD (e.g. 26-12-24)</option>
          </select>
        </div>
      </div>

      <button type="button" @click="emit('save', localForm)" :disabled="isSubmitting" class="w-full py-4 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl disabled:opacity-50 shadow-lg shadow-blue-500/20">
        {{ isSubmitting ? 'Saving...' : 'Update Configuration' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.4s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
