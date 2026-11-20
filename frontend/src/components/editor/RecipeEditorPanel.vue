<script setup lang="ts">
import { computed } from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'
import UiButton from '@/components/ui/UiButton.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import EntityReferenceCombobox, { type ReferenceOption } from '@/components/editor/EntityReferenceCombobox.vue'

/**
 * Editor for a CONSTRUCTABLE recipe: the ingredients to combine (each optionally kept instead of
 * consumed) and the separate result items that crafting reveals. Results start hidden.
 *
 * Every picker lists items by scene (editor scene order, then items outside any scene) and hides
 * items already used as an ingredient or result of this recipe, and the recipe itself.
 */
const props = withDefaults(defineProps<{
  ingredients?: string[]
  results?: string[]
  kept?: string[]
  ingredientOptions: RecipeOption[]
  resultOptions: RecipeOption[]
  /** ID of the recipe being edited; never offered as its own ingredient or result. */
  recipeId?: string
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

type RecipeOption = ReferenceOption & { sceneLabel?: string; sceneOrder?: number }

const upper = (id: unknown) => String(id || '').trim().toUpperCase()
const NO_SCENE = Number.MAX_SAFE_INTEGER

function byLocation(a: RecipeOption, b: RecipeOption): number {
  const scene = (a.sceneOrder ?? NO_SCENE) - (b.sceneOrder ?? NO_SCENE)
  return scene || String(a.name || a.id).localeCompare(String(b.name || b.id))
}

function sortedByLocation(options: RecipeOption[]): ReferenceOption[] {
  return [...options]
    .filter((option) => upper(option.id) !== upper(props.recipeId))
    .sort(byLocation)
    .map((option) => ({ ...option, subtitle: option.sceneLabel || 'No scene' }))
}

const sortedIngredientOptions = computed(() => sortedByLocation(props.ingredientOptions))
const sortedResultOptions = computed(() => sortedByLocation(props.resultOptions))
const assignedIds = computed(() => new Set([...props.ingredients, ...props.results].map(upper).filter(Boolean)))

/** Options for one picker: everything not yet assigned, plus the picker's own current item. */
function available(options: ReferenceOption[], current: string): ReferenceOption[] {
  const own = upper(current)
  return options.filter((option) => upper(option.id) === own || !assignedIds.value.has(upper(option.id)))
}

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
  <div class="space-y-6">
    <UiNotice>
      A recipe never appears in the game. When the player combines all ingredients (at least 2), they are used up
      (except the kept ones) and the result items are revealed. Results can be any item type and start hidden.
    </UiNotice>

    <div class="space-y-2">
      <p class="wb-label">Ingredients</p>
      <div v-for="(ing, idx) in ingredients" :key="`ing-${idx}`" class="flex items-center gap-2">
        <EntityReferenceCombobox
          :model-value="ing"
          :options="available(sortedIngredientOptions, ing)"
          placeholder="Select ingredient item"
          :enable-search="true"
          @update:model-value="setIngredient(idx, $event)"
        />
        <UiButton
          size="sm"
          :variant="isKept(ing) ? 'secondary' : 'ghost'"
          :disabled="!ing"
          :aria-pressed="isKept(ing)"
          class="w-28 shrink-0"
          @click="toggleKept(ing)"
        >
          {{ isKept(ing) ? 'Kept' : 'Consumed' }}
        </UiButton>
        <UiIconButton :icon="Trash2" label="Remove ingredient" size="sm" variant="danger" @click="removeIngredient(idx)" />
      </div>
      <UiButton size="sm" :icon="Plus" @click="emit('update:ingredients', [...ingredients, ''])">Add ingredient</UiButton>
      <p class="wb-hint">All items that must be combined. Mark tools as "Kept" so they are not used up.</p>
    </div>

    <div class="space-y-2">
      <p class="wb-label">Result items</p>
      <div v-for="(res, idx) in results" :key="`res-${idx}`" class="flex items-center gap-2">
        <EntityReferenceCombobox
          :model-value="res"
          :options="available(sortedResultOptions, res)"
          placeholder="Select result item"
          :enable-search="true"
          @update:model-value="setResult(idx, $event)"
        />
        <UiIconButton
          :icon="Trash2"
          label="Remove result"
          size="sm"
          variant="danger"
          @click="emit('update:results', results.filter((_, i) => i !== idx))"
        />
      </div>
      <UiButton size="sm" :icon="Plus" @click="emit('update:results', [...results, ''])">Add result item</UiButton>
      <p class="wb-hint">
        At least one. It lands in the inventory when all ingredients were carried, otherwise in the current scene. A
        result with its own reveal rule can also be found without crafting.
      </p>
    </div>
  </div>
</template>
