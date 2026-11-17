<script setup lang="ts">
import { computed } from 'vue'
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const ef = useEntityFormContext()

/** A reveal rule from before the guard (other than "script"); the engine ignores it for characters. */
const legacyRule = computed(() => {
  const rule = String(ef.localForm.reveal_rule || '').trim()
  return rule.toLowerCase() === 'script' ? '' : rule
})
</script>

<template>
  <UiSection v-if="ef.type === 'npc'" title="Visibility" class="border-t border-wb-line pt-6">
    <UiToggle
      v-model="ef.localForm.is_hidden"
      label="Start hidden"
      description="Appears only when its reveal guard holds or a script reveals it."
    />
    <template v-if="ef.localForm.is_hidden">
      <UiField label="Hiding place" hint="Used by the narrator when describing the scene.">
        <UiInput v-model="ef.localForm.spatial_position" maxlength="255" placeholder="e.g. hiding in the cellar behind the wine barrels" />
      </UiField>
      <ScriptEditor
        v-model="ef.localForm.reveal_guard_expression"
        label="Reveal guard"
        help-text="Python condition checked after every player message while the protagonist is in this scene. When it is True, the character appears. Empty: only scripts (tw.npcs.reveal) reveal it."
        context="guard_expression"
        placeholder="e.g. tw.player.has_item('LANTERN') or tw.vars.get('bell_rung') == True"
        min-height="70px"
      />
      <UiNotice v-if="legacyRule" tone="warn">
        The old reveal rule “{{ legacyRule }}” is no longer used: the Game Master does not discover hidden characters.
        Express it as a reveal guard or reveal the character from a script.
      </UiNotice>
    </template>
  </UiSection>
</template>
