<script setup lang="ts">
/** Dialogs, tooltip and toasts shared by all editor pages. */
import { useEditor } from '@/composables/editor/editorContext'
import EntityTooltip from '@/components/editor/EntityTooltip.vue'
import ManualVisionModal from '@/components/editor/ManualVisionModal.vue'
import EditEntityModal from '@/components/editor/EditEntityModal.vue'
import ItemTypeSelectorModal from '@/components/editor/ItemTypeSelectorModal.vue'
import AddExistingItemModal from '@/components/editor/AddExistingItemModal.vue'
import MoveItemToSceneModal from '@/components/editor/MoveItemToSceneModal.vue'
import NpcCombatModal from '@/components/editor/NpcCombatModal.vue'
import EditExitModal from '@/components/editor/EditExitModal.vue'
import DataDebugModal from '@/components/editor/DataDebugModal.vue'
import { fixNewlines } from '@/utils/editor_utils'
import { formatBytes } from '@/utils/editor_utils'
import { visualService } from '@/services/visualService'

const editor = useEditor()
</script>

<template>
  <EntityTooltip 
    :hovered-entity="editor.canShowSceneRoutePanel ? null : editor.hoveredEntity"
    :active-menu-id="editor.activeMenuId"
    :mouse-pos="editor.mousePos"
    :tooltip-align-top="editor.tooltipAlignTop"
    :window-height="editor.windowHeight"
    :rule-enforcement-mode="editor.form.rule_enforcement_mode"
    :build-visual-image-url="editor.buildVisualImageUrl"
    :fix-newlines="fixNewlines"
  />

  <ManualVisionModal 
    :show="editor.showPromptDialog"
    :selected-visual="editor.selectedVisual"
    v-model:visual-prompt="editor.visualPrompt"
    v-model:use-advanced-model="editor.useAdvancedModel"
    v-model:apply-style="editor.applyStyle"
    v-model:apply-appearance="editor.applyAppearance"
    :configured-style-name="editor.configuredStyleName"
    :is-suggesting-prompt="editor.isSuggestingPrompt"
    :is-enhancing-prompt="editor.isEnhancingPrompt"
    :is-regenerating="editor.isRegenerating"
    :upload-limits="visualService.UPLOAD_LIMITS"
    :format-bytes="formatBytes"
    :fix-newlines="fixNewlines"
    @close="editor.showPromptDialog = false"
    @suggest="editor.suggestPrompt"
    @enhance="editor.enhancePrompt"
    @regenerate="editor.regenerateVisual"
    @cancel-regen="editor.cancelRegeneration"
  />

  <EditEntityModal 
    :show="editor.showEditModal"
    :context="editor.editEntityContext"
    :initial-form="editor.editForm"
    :reference-options="editor.referenceOptions"
    :rule-enforcement-mode="editor.form.rule_enforcement_mode"
    :is-saving="editor.isSavingText"
    :adventure-id="editor.adventureId"
    :is-create-entity-mode="editor.isCreateEntityMode"
    :npc-data="editor.editEntityContext?.type === 'npc' ? editor.editorNpcs.find((n: any) => n.id === editor.editEntityContext?.id) : null"
    :voice-list="editor.voiceList"
    @close="editor.closeEditEntityModal"
    @save="editor.saveEntityText"
    @combat-saved="editor.onSpecialAttacksSaved"
  />

  <ItemTypeSelectorModal
    :show="editor.showItemTypeSelector"
    :scene-label="editor.routeSceneDetails?.label || editor.routeSceneDetails?.name || editor.createEntitySceneId || ''"
    @close="editor.showItemTypeSelector = false"
    @select="editor.handleItemTypeSelected"
  />

  <ItemTypeSelectorModal
    :show="editor.showItemTypeChangeModal"
    mode="change"
    :current-item-name="editor.itemTypeChangeTarget?.name || ''"
    :current-item-type="editor.itemTypeChangeTarget?.currentItemType || ''"
    @close="editor.closeChangeItemTypeModal"
    @select="editor.confirmChangeItemType"
  />

  <AddExistingItemModal
    :show="editor.showAddExistingItemModal"
    :kind="editor.addExistingItemKind"
    :scene-label="editor.routeSceneDetails?.label || editor.routeSceneDetails?.name || editor.activeMapSceneId || ''"
    :items="editor.addExistingItemOptions"
    :visuals-cache-version="editor.visualsCacheVersion"
    @close="editor.closeAddExistingItemModal"
    @select="editor.handleAddExistingItemSelected"
  />

  <MoveItemToSceneModal
    :show="editor.showMoveItemModal"
    :entity-type="editor.moveEntityTarget?.type || 'item'"
    :item-id="editor.moveEntityTarget?.id || ''"
    :item-name="editor.moveEntityTarget?.name || ''"
    :current-scene-id="editor.moveEntityTarget?.currentSceneId || ''"
    :scene-options="editor.sceneReferenceOptions"
    :is-saving="editor.isMovingItem"
    @close="editor.closeMoveItemModal"
    @confirm="editor.confirmMoveEntityToScene"
  />

  <NpcCombatModal
    :open="!!editor.specialAttacksNpc"
    :adventure-id="editor.adventureId"
    :npc="editor.specialAttacksNpc"
    :reference-options="editor.referenceOptions"
    @close="editor.specialAttacksNpc = null"
    @saved="editor.onSpecialAttacksSaved"
  />

  <EditExitModal
    :key="`exit-modal-${editor.activeEditExitId || (editor.isCreateExitMode ? 'new' : 'closed')}`"
    :show="editor.showExitModal"
    :is-create-mode="editor.isCreateExitMode"
    :from-scene-id="editor.exitModalForm.from_scene_id || editor.activeMapSceneId || ''"
    :active-edit-exit-id="editor.activeEditExitId"
    :initial-form="editor.exitModalForm"
    :scene-reference-options="editor.sceneReferenceOptions"
    :reference-options="editor.referenceOptions"
    :is-saving-text="editor.isSavingText"
    @close="editor.closeExitEditModal"
    @save="editor.saveExitModal"
  />

  <DataDebugModal 
    :show="editor.showDebug"
    :adventure="editor.adventure"
    :debug-data="editor.debugData"
    @close="editor.showDebug = false"
  />

  <input
    :ref="(el) => (editor.uploadInput = el as HTMLInputElement | null)"
    type="file"
    accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp"
    class="hidden"
    @change="editor.uploadSelectedVisual"
  />
</template>
