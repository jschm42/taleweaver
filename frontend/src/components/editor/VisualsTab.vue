<script setup lang="ts">
const props = defineProps<{
  form: any
  adventure: any
  imageStylesCatalog: any[]
}>()

const emit = defineEmits<{
  (e: 'update:style', val: string): void
  (e: 'save-changes'): void
}>()
</script>

<template>
  <div class="space-y-8 animate-page-in">
    <section v-if="imageStylesCatalog.length" class="space-y-6 bg-slate-900/40 p-8 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
     <div class="flex items-center justify-between">
        <div class="flex items-center gap-4">
           <div class="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
              <i class="ra ra-eye-shield text-emerald-500"></i>
           </div>
           <div>
              <h3 class="text-sm font-black text-white uppercase tracking-[0.2em]">Visual Atmosphere</h3>
              <p class="text-xs font-bold text-slate-500 uppercase tracking-widest">Select the aesthetic direction for generated images</p>
           </div>
        </div>
        <div v-if="form.selected_style_id !== (adventure?.selected_image_styles?.[0]?.id || '')" class="flex gap-4 animate-fade-in">
           <button @click="$emit('update:style', adventure?.selected_image_styles?.[0]?.id || '')" class="px-4 py-2 rounded-xl bg-slate-800 text-xs font-black text-slate-400 uppercase tracking-widest hover:text-white transition-all">Discard</button>
           <button @click="$emit('save-changes')" class="px-6 py-2 rounded-xl bg-emerald-600 text-xs font-black text-white uppercase tracking-widest hover:bg-emerald-500 transition-all shadow-lg shadow-emerald-900/40">Apply Style</button>
        </div>
     </div>
     <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
        <button 
          v-for="style in imageStylesCatalog" 
          :key="style.id" 
          @click="$emit('update:style', style.id)"
          class="relative aspect-4-5 rounded-2xl overflow-hidden border-2 transition-all duration-500 group"
          :class="form.selected_style_id === style.id ? 'border-emerald-500 ring-4 ring-emerald-500/20' : 'border-transparent hover:border-white/10'"
        >
          <img :src="style.image_url" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" />
          <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80 group-hover:opacity-40 transition-opacity"></div>
          <div class="absolute bottom-3 left-3 right-3">
            <p class="text-[10px] font-black text-white uppercase tracking-tighter truncate">{{ style.name }}</p>
          </div>
          <div v-if="form.selected_style_id === style.id" class="absolute top-2 right-2 w-5 h-5 bg-emerald-500 rounded-full flex items-center justify-center shadow-lg">
            <i class="ra ra-checkmark text-[10px] text-white"></i>
          </div>
        </button>
     </div>
    </section>
  </div>
</template>

<style scoped>
.aspect-4-5 { aspect-ratio: 4/5; }
.animate-page-in { animation: pageIn 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes pageIn { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
</style>
