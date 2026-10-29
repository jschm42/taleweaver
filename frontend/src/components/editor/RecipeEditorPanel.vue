<script setup lang="ts">
import { computed } from 'vue'
import EntityReferenceCombobox, { type ReferenceOption } from '@/components/editor/EntityReferenceCombobox.vue'

/**
 * Editor for a CONSTRUCTABLE recipe: the ingredients to combine (each optionally kept instead of
 * consumed) and the separate result items that crafting reveals. Results start hidden.
 */
const props = withDefaults(defineProps<{
  ingredients?: string[]
  results?: string[]
  kept?: string[]
  ingredientOptions: ReferenceOption[]
  resultOptions: ReferenceOption[]
}>(), {
  ingredients: () => [],
  results: () => [],
  kept: () => [],
})

const emit = defineEmits<{
  (e: 'update:ingredients', value: string[]): void
  (e: 'update:results', value: string[]): void
  (e: 'update:kept', value: string[]): void
}>()

const keptIds = computed(() => new Set(props.kept.map((id) => String(id).toUpperCase())))

function isKept(id: string): boolean {
  return Boolean(id) && keptIds.value.has(String(id).toUpperCase())
}

function setIngredient(idx: number, value: string) {
  const previous = props.ingredients[idx]
  emit('update:ingredients', props.ingredients.map((id, i) => (i === idx ? value : id)))
  if (previous && isKept(previous)) {
    emit('update:kept', props.kept.filter((id) => id.toUpperCase() !== previous.toUpperCase()))
  }
}

function removeIngredient(idx: number) {
  const removed = props.ingredients[idx]
  emit('update:ingredients', props.ingredients.filter((_, i) => i !== idx))
  if (removed && isKept(removed)) {
    emit('update:kept', props.kept.filter((id) => id.toUpperCase() !== removed.toUpperCase()))
  }
}

function toggleKept(id: string) {
  if (!id) return
  const next = isKept(id)
    ? props.kept.filter((k) => k.toUpperCase() !== id.toUpperCase())
    : [...props.kept, id]
  emit('update:kept', next)
}

function setResult(idx: number, value: string) {
  emit('update:results', props.results.map((id, i) => (i === idx ? value : id)))
}
</script>

<template>
  <div class="space-y-5">
    <div class="px-3 py-2 rounded-lg border border-orange-500/30 bg-orange-500/5 text-[11px] text-orange-200/90 leading-relaxed flex items-start gap-2">
      <i class="ra ra-hammer text-orange-400 mt-0.5 shrink-0"></i>
      <span>
        A CONSTRUCTABLE is a meta item: it never appears in the game. When the player combines ALL ingredients (min. 2),
        the engine consumes them (except the kept ones) and reveals the result items. Results can be any item type
        and are set to hidden automatically.
      </span>
    </div>

    <!-- Ingredients -->
    <div class="space-y-2">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Ingredients</label>
      <div v-for="(ing, idx) in ingredients" :key="`ing-${idx}`" class="flex items-center gap-2">
        <EntityReferenceCombobox
          :model-value="ing"
          :options="ingredientOptions"
          placeholder="Select ingredient item"
          :enable-search="true"
          @update:model-value="setIngredient(idx, $event)"
        />
        <button
          type="button"
          :disabled="!ing"
          :title="isKept(ing) ? 'Kept: this ingredient survives crafting' : 'Consumed: this ingredient is used up'"
          @click="toggleKept(ing)"
          :class="[
            'shrink-0 px-2 py-1.5 rounded-lg border text-[10px] font-bold uppercase tracking-widest transition-all disabled:opacity-40',
            isKept(ing)
              ? 'border-emerald-500/40 text-emerald-300 bg-emerald-500/10'
              : 'border-white/10 text-slate-400 hover:bg-white/5',
          ]"
        >
          {{ isKept(ing) ? 'Kept' : 'Consumed' }}
        </button>
        <button
          type="button"
          @click="removeIngredient(idx)"
          class="shrink-0 px-2 py-1.5 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 text-[10px] font-bold uppercase tracking-widest transition-all"
        >
          <i class="ra ra-cancel"></i>
        </button>
      </div>
      <button
        type="button"
        @click="emit('update:ingredients', [...ingredients, ''])"
        class="w-full py-2 bg-violet-500/5 border border-violet-500/10 hover:bg-violet-500/10 hover:border-violet-500/30 rounded-xl text-[10px] font-black text-violet-400 uppercase tracking-widest transition-all"
      >
        + Add Ingredient
      </button>
      <p class="text-[10px] text-slate-500 uppercase tracking-wider">
        Select ALL items that must be combined (min. 2). Mark tools as "Kept" so they are not used up.
      </p>
    </div>

    <!-- Results -->
    <div class="space-y-2">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Result Items</label>
      <div v-for="(res, idx) in results" :key="`res-${idx}`" class="flex items-center gap-2">
        <EntityReferenceCombobox
          :model-value="res"
          :options="resultOptions"
          placeholder="Select result item"
          :enable-search="true"
          @update:model-value="setResult(idx, $event)"
        />
        <button
          type="button"
          @click="emit('update:results', results.filter((_, i) => i !== idx))"
          class="shrink-0 px-2 py-1.5 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 text-[10px] font-bold uppercase tracking-widest transition-all"
        >
          <i class="ra ra-cancel"></i>
        </button>
      </div>
      <button
        type="button"
        @click="emit('update:results', [...results, ''])"
        class="w-full py-2 bg-orange-500/5 border border-orange-500/10 hover:bg-orange-500/10 hover:border-orange-500/30 rounded-xl text-[10px] font-black text-orange-300 uppercase tracking-widest transition-all"
      >
        + Add Result Item
      </button>
      <p class="text-[10px] text-slate-500 uppercase tracking-wider">
        At least one result. It lands in the inventory when all ingredients were carried, otherwise in the current
        scene. A result with its own reveal rule can also be found without crafting.
      </p>
    </div>
  </div>
</template>
