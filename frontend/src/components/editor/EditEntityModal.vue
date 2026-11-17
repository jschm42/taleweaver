<script setup lang="ts">
import EntityImagePreview from '@/components/editor/EntityImagePreview.vue'
import { provideEntityForm } from '@/composables/editor/entityFormContext'
import type { EntityFormEmits, EntityFormProps } from '@/composables/editor/useEntityForm'
import EntityIdField from '@/components/editor/entity/EntityIdField.vue'
import EntityStatsSection from '@/components/editor/entity/EntityStatsSection.vue'
import ProtagonistTraitsSection from '@/components/editor/entity/ProtagonistTraitsSection.vue'
import NpcProfileSection from '@/components/editor/entity/NpcProfileSection.vue'
import NpcMovementSection from '@/components/editor/entity/NpcMovementSection.vue'
import NpcNotesSection from '@/components/editor/entity/NpcNotesSection.vue'
import NpcInventorySection from '@/components/editor/entity/NpcInventorySection.vue'
import NpcVisibilitySection from '@/components/editor/entity/NpcVisibilitySection.vue'
import ItemBasicsSection from '@/components/editor/entity/ItemBasicsSection.vue'
import ItemVisibilitySection from '@/components/editor/entity/ItemVisibilitySection.vue'
import ItemEquipmentSection from '@/components/editor/entity/ItemEquipmentSection.vue'
import ItemConsumableSection from '@/components/editor/entity/ItemConsumableSection.vue'
import ItemRecipeSection from '@/components/editor/entity/ItemRecipeSection.vue'
import ItemSwitchSection from '@/components/editor/entity/ItemSwitchSection.vue'
import ItemContainerSection from '@/components/editor/entity/ItemContainerSection.vue'
import ItemReadableSection from '@/components/editor/entity/ItemReadableSection.vue'
import EntityDescriptionSection from '@/components/editor/entity/EntityDescriptionSection.vue'
import NpcCombatPanel from '@/components/editor/entity/NpcCombatPanel.vue'
import NpcCompanionPanel from '@/components/editor/entity/NpcCompanionPanel.vue'
import ItemTriggersPanel from '@/components/editor/entity/ItemTriggersPanel.vue'
import SceneTriggersPanel from '@/components/editor/entity/SceneTriggersPanel.vue'
import NpcTriggersPanel from '@/components/editor/entity/NpcTriggersPanel.vue'

const props = defineProps<EntityFormProps>()
const emit = defineEmits<EntityFormEmits>()

const ef = provideEntityForm(props, emit)
</script>

<template>
  <Teleport to="body" :disabled="ef.isPage">
    <Transition :name="ef.isPage ? '' : 'modal'">
      <div
        v-if="ef.props.show && ef.props.context"
        :class="ef.isPage ? '' : 'fixed inset-0 z-[200] flex items-center justify-center p-6 backdrop-blur-xl bg-slate-950/60'"
      >
        <div
          :class="ef.isPage
            ? 'w-full bg-slate-900 border border-white/10 rounded-xl overflow-hidden flex flex-col'
            : 'modal-content w-full max-w-4xl bg-slate-900 border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden max-h-[92vh] flex flex-col'"
        >
          <!-- Fixed Header -->
          <div class="px-8 py-5 flex justify-between items-center border-b border-white/5">
            <div class="flex items-center gap-4">
              <EntityImagePreview :image-url="ef.entityImageUrl" :label="ef.localForm.name || ef.props.context.id" />
              <div class="space-y-1">
                <h3 class="text-xs font-black text-emerald-500 uppercase tracking-widest">{{ ef.props.isCreateEntityMode ? ('Create ' + (ef.props.context.type === 'npc' ? 'NPC' : ef.props.context.type.toUpperCase())) : ('Editing ' + ef.props.context.type) }}</h3>
                <p class="text-slate-500 text-xs uppercase font-bold tracking-tighter">{{ ef.props.isCreateEntityMode ? 'New Entity' : 'ID: ' + ef.props.context.id }}</p>
              </div>
            </div>
            <button v-if="!ef.isPage" @click="ef.emit('close')" class="text-slate-500 hover:text-white transition-colors" aria-label="Close">
              <i class="ra ra-cancel text-xl"></i>
            </button>
          </div>

          <!-- Tabs -->
          <div class="px-8 border-b border-white/5 flex gap-6">
            <button
              @click="ef.activeTab = 'simple'"
              :class="['pb-3 pt-4 text-xs font-black uppercase tracking-widest transition-colors border-b-2', ef.activeTab === 'simple' ? 'text-emerald-500 border-emerald-500' : 'text-slate-500 border-transparent hover:text-white']"
            >
              General
            </button>
            <button
              v-if="ef.props.context.type === 'npc'"
              @click="ef.activeTab = 'combat'"
              :class="['pb-3 pt-4 text-xs font-black uppercase tracking-widest transition-colors border-b-2', ef.activeTab === 'combat' ? 'text-emerald-500 border-emerald-500' : 'text-slate-500 border-transparent hover:text-white']"
            >
              Combat
            </button>
            <button
              v-if="ef.props.context.type === 'npc'"
              @click="ef.activeTab = 'companion'"
              :class="['pb-3 pt-4 text-xs font-black uppercase tracking-widest transition-colors border-b-2', ef.activeTab === 'companion' ? 'text-emerald-500 border-emerald-500' : 'text-slate-500 border-transparent hover:text-white']"
            >
              Companion
            </button>
            <button
              @click="ef.activeTab = 'advanced'"
              :class="['pb-3 pt-4 text-xs font-black uppercase tracking-widest transition-colors border-b-2', ef.activeTab === 'advanced' ? 'text-emerald-500 border-emerald-500' : 'text-slate-500 border-transparent hover:text-white']"
            >
              Advanced
            </button>
          </div>

          <!-- Scrollable Content -->
          <div :class="['px-8 py-6 space-y-6 flex-1', ef.isPage ? '' : 'overflow-y-auto']">
            <div v-show="ef.activeTab === 'simple'" class="space-y-6">
              <EntityIdField />
              <EntityStatsSection />
              <ProtagonistTraitsSection />
              <NpcProfileSection />
              <NpcMovementSection />
              <NpcNotesSection />
              <NpcInventorySection />
              <NpcVisibilitySection />

              <div v-if="ef.props.context.type === 'object'" class="p-4 bg-black/30 border border-white/10 rounded-2xl space-y-5">
                <ItemBasicsSection />
                <ItemVisibilitySection />
                <ItemEquipmentSection />
                <ItemConsumableSection />
                <ItemRecipeSection />
                <ItemSwitchSection />
                <ItemContainerSection />
                <ItemReadableSection />
              </div>
              <EntityDescriptionSection />
            </div> <!-- End simple tab -->

            <div v-if="ef.props.context.type === 'npc'" v-show="ef.activeTab === 'combat'" class="space-y-6">
              <NpcCombatPanel />

            </div> <!-- End combat tab -->

            <div v-if="ef.props.context.type === 'npc'" v-show="ef.activeTab === 'companion'" class="space-y-6">
              <NpcCompanionPanel />
            </div> <!-- End companion tab -->

            <div v-show="ef.activeTab === 'advanced'" class="space-y-6">
              <div class="space-y-2">
                <p class="text-xs font-black text-slate-500 uppercase tracking-widest">Advanced Triggers</p>
                <p class="text-[10px] text-slate-500 uppercase tracking-tighter">
                  Define scripts or text cues to execute during interaction. (Leave blank if none).
                </p>
              </div>

              <div v-if="ef.props.context.type === 'object'" class="space-y-6">
                <ItemTriggersPanel />
              </div>

              <div v-else-if="ef.props.context.type === 'scene'" class="space-y-6">
                <SceneTriggersPanel />
              </div>

              <div v-else-if="ef.props.context.type === 'npc'" class="space-y-6">
                <NpcTriggersPanel />
              </div>

            </div>
          </div>
          <div :class="['px-8 py-5 border-t border-white/5 flex justify-end gap-4 bg-slate-900/55', ef.isPage ? 'sticky bottom-0 z-20 backdrop-blur-md' : 'rounded-b-[2.5rem]']">
            <button @click="ef.emit('close')" class="px-6 py-2.5 text-slate-400 hover:text-white font-black uppercase text-xs tracking-widest transition-colors">Discard</button>
            <button @click="ef.handleSave" :disabled="ef.props.isSaving || ef.isFormInvalid" class="px-8 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-black uppercase text-xs tracking-widest rounded-xl shadow-lg shadow-emerald-900/20 disabled:opacity-50 flex items-center gap-3">
              <i v-if="ef.props.isSaving" class="ra ra-cycle animate-spin"></i>
              <span>{{ ef.props.isSaving ? 'Saving...' : (ef.props.isCreateEntityMode ? ('Create ' + (ef.props.context.type === 'npc' ? 'NPC' : ef.props.context.type.toUpperCase())) : 'Apply Changes') }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-enter-from, .modal-leave-to { opacity: 0; }

.modal-enter-active .modal-content { animation: modalScaleIn 0.5s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-leave-active .modal-content { transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); transform: scale(0.95); }

@keyframes modalScaleIn {
  from { opacity: 0; transform: scale(0.9) translateY(40px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
</style>