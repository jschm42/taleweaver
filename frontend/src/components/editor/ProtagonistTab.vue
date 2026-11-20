<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Download, Upload, UserX } from 'lucide-vue-next'
import SpecialAttacksEditor from '@/components/editor/SpecialAttacksEditor.vue'
import ProtagonistEquipmentPanel from '@/components/editor/protagonist/ProtagonistEquipmentPanel.vue'
import ProtagonistGeneralPanel from '@/components/editor/protagonist/ProtagonistGeneralPanel.vue'
import ProtagonistInventoryPanel from '@/components/editor/protagonist/ProtagonistInventoryPanel.vue'
import ProtagonistStatsPanel from '@/components/editor/protagonist/ProtagonistStatsPanel.vue'
import ProtagonistTriggersPanel from '@/components/editor/protagonist/ProtagonistTriggersPanel.vue'
import type { CreateItemTarget, ProtagonistData, ReferenceOption } from '@/components/editor/protagonist/protagonistTypes'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiTabs from '@/components/ui/UiTabs.vue'
import type { TtsVoiceList } from '@/types'

/** Protagonist page: one tab per part (tab in `?panel=`). Fields save as they change. */
const props = defineProps<{
  protagonist: ProtagonistData | null
  isQuickGenerating: Record<string, boolean>
  visualsCacheVersion: number
  ruleEnforcementMode: string
  isSavingText: boolean
  referenceOptions: ReferenceOption[]
  adventureId?: string
  voiceList?: TtsVoiceList | null
}>()

const emit = defineEmits<{
  'quick-regen': [kind: string, id: string]
  'open-regen-dialog': [kind: string, id: string, label: string]
  'open-upload-picker': [kind: string, id: string, label: string]
  'download-asset': [path: string, label: string]
  'save-field': [field: string | Record<string, unknown>, value?: unknown]
  'create-new-item': [target: CreateItemTarget]
  'special-attacks-saved': []
  'export-entity': [kind: 'protagonist', id: null, label: string]
  'import-entity': [kind: 'protagonist']
}>()

type PanelId = 'general' | 'stats' | 'equipment' | 'inventory' | 'combat' | 'triggers'

const route = useRoute()
const router = useRouter()

const hasRules = computed(() => props.ruleEnforcementMode !== 'chat')

const tabs = computed(() => [
  { id: 'general' as const, label: 'General' },
  ...(hasRules.value
    ? [
        { id: 'stats' as const, label: 'Stats' },
        { id: 'equipment' as const, label: 'Equipment' },
        { id: 'inventory' as const, label: 'Inventory', count: props.protagonist?.inventory?.length ?? null },
        ...(props.adventureId ? [{ id: 'combat' as const, label: 'Combat' }] : []),
      ]
    : []),
  { id: 'triggers' as const, label: 'Triggers' },
])

const panel = computed<PanelId>({
  get: () => {
    const wanted = route.query.panel
    return tabs.value.find((tab) => tab.id === wanted)?.id ?? 'general'
  },
  set: (value) => {
    void router.replace({ query: { ...route.query, panel: value === 'general' ? undefined : value } })
  },
})

const name = computed(() => props.protagonist?.name || 'protagonist')

function openRegenDialog(): void {
  if (props.protagonist) emit('open-regen-dialog', 'protagonist', props.protagonist.id, name.value)
}

function openUploadPicker(): void {
  if (props.protagonist) emit('open-upload-picker', 'protagonist', props.protagonist.id, name.value)
}

function downloadPortrait(): void {
  const image = props.protagonist?.profile_image
  if (image) emit('download-asset', image, `${name.value}_portrait`)
}
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Protagonist" description="The hero the player controls: who they are, what they can do and what they carry.">
      <template #actions>
        <UiButton size="sm" :icon="Upload" @click="emit('import-entity', 'protagonist')">Import</UiButton>
        <UiButton
          v-if="protagonist"
          size="sm"
          :icon="Download"
          @click="emit('export-entity', 'protagonist', null, name)"
        >
          Export
        </UiButton>
      </template>
    </PageHeader>

    <UiEmptyState
      v-if="!protagonist"
      :icon="UserX"
      title="No protagonist yet"
      description="Import one from a .twe file or let the World-Builder create it."
    />

    <template v-else>
      <UiTabs v-model="panel" :tabs="tabs" label="Protagonist sections" />

      <ProtagonistGeneralPanel
        v-show="panel === 'general'"
        :protagonist="protagonist"
        :is-saving-text="isSavingText"
        :is-generating="!!isQuickGenerating['protagonist_' + protagonist.id]"
        :visuals-cache-version="visualsCacheVersion"
        :reference-options="referenceOptions"
        :adventure-id="adventureId"
        :voice-list="voiceList"
        @save-field="(field, value) => emit('save-field', field, value)"
        @quick-regen="emit('quick-regen', 'protagonist', protagonist.id)"
        @open-regen-dialog="openRegenDialog"
        @open-upload-picker="openUploadPicker"
        @download-asset="downloadPortrait"
        @talents-saved="emit('special-attacks-saved')"
      />

      <template v-if="hasRules">
        <ProtagonistStatsPanel
          v-show="panel === 'stats'"
          :protagonist="protagonist"
          @save-field="(field, value) => emit('save-field', field, value)"
        />
        <ProtagonistEquipmentPanel
          v-show="panel === 'equipment'"
          :protagonist="protagonist"
          :reference-options="referenceOptions"
          @save-field="(field, value) => emit('save-field', field, value)"
          @create-new-item="emit('create-new-item', $event)"
        />
        <ProtagonistInventoryPanel
          v-show="panel === 'inventory'"
          :protagonist="protagonist"
          :reference-options="referenceOptions"
          @save-field="(field, value) => emit('save-field', field, value)"
          @create-new-item="emit('create-new-item', $event)"
        />
        <div v-if="adventureId" v-show="panel === 'combat'">
          <SpecialAttacksEditor
            :adventure-id="adventureId"
            target-type="protagonist"
            :target-id="protagonist.id"
            :owner-name="protagonist.name ?? ''"
            :attacks="protagonist.stats?.special_actions ?? []"
            :reference-options="referenceOptions"
            @saved="emit('special-attacks-saved')"
          />
        </div>
      </template>

      <ProtagonistTriggersPanel
        v-show="panel === 'triggers'"
        :protagonist="protagonist"
        :is-saving="isSavingText"
        @save-fields="emit('save-field', $event)"
      />
    </template>
  </div>
</template>
