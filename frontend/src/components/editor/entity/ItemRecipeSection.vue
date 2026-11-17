<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import RecipeEditorPanel from '@/components/editor/RecipeEditorPanel.vue'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import UiDisclosure from '@/components/ui/UiDisclosure.vue'
import UiField from '@/components/ui/UiField.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const ef = useEntityFormContext()
</script>

<template>
  <template v-if="ef.currentItemType === 'CONSTRUCTABLE'">
    <RecipeEditorPanel
      v-model:ingredients="ef.localForm.combination_ingredients_input"
      v-model:results="ef.localForm.result_item_ids_input"
      v-model:kept="ef.localForm.kept_ingredients_input"
      :ingredient-options="ef.recipeIngredientOptions"
      :result-options="ef.recipeResultOptions"
      :recipe-id="ef.currentEntityId || String(ef.entityId || '')"
    />

    <div class="space-y-3 border-t border-wb-line pt-6">
      <!-- Contents are created only when opened: the script editor measures itself on creation. -->
      <UiDisclosure
        v-model:open="ef.showConstructableGuard"
        label="Crafting guard"
        :hint="ef.localForm.craft_guard_expression ? 'configured' : 'optional'"
      >
        <ScriptEditor
          v-if="ef.showConstructableGuard"
          v-model="ef.localForm.craft_guard_expression"
          label="Guard expression"
          help-text="Python boolean expression checked in addition to the ingredients. If false, crafting fails."
          context="guard_expression"
          placeholder="e.g. tw.vars.get('has_hammer') == True or tw.switches.get('FORGE') == 'ON'"
          min-height="90px"
        />
      </UiDisclosure>

      <UiDisclosure
        v-model:open="ef.showConstructableTriggers"
        label="Crafting success and failure"
        :hint="ef.localForm.on_craft_success_script || ef.localForm.on_craft_failure_script ? 'configured' : 'optional'"
      >
        <div v-if="ef.showConstructableTriggers" class="space-y-4">
          <ScriptEditor
            v-model="ef.localForm.on_craft_success_script"
            label="On success script"
            help-text="Runs when this recipe is crafted."
            context="constructable_success"
            min-height="100px"
          />
          <UiField label="On success text">
            <UiTextarea
              v-model="ef.localForm.on_craft_success_text"
              :rows="2"
              placeholder="e.g. With careful precision, you forge the ingredients into a masterwork."
            />
          </UiField>
          <ScriptEditor
            v-model="ef.localForm.on_craft_failure_script"
            label="On failure script"
            help-text="Runs when crafting fails or the guard blocks it."
            context="constructable_failure"
            min-height="100px"
          />
          <UiField label="On failure text">
            <UiTextarea v-model="ef.localForm.on_craft_failure_text" :rows="2" placeholder="e.g. The forge is too cold to fuse the metal together." />
          </UiField>
        </div>
      </UiDisclosure>
    </div>
  </template>
</template>
