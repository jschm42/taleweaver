<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import TimeTab from '@/components/editor/TimeTab.vue'

const editor = useEditor()
</script>

<template>
  <TimeTab
    :form="editor.form"
    :adventure="editor.adventure"
    :is-saving="editor.isSaving"
    @update:pacing="editor.form.time_per_turn = $event"
    @update:max-time-per-turn="editor.form.max_time_per_turn = $event"
    @update:gm-time-control="editor.form.gm_time_control = $event"
    @update:clock-enabled="editor.form.clock_enabled = $event"
    @update:time-system="editor.form.time_system = $event"
    @update:start-date="editor.form.time_config = { ...(editor.form.time_config || {}), start_date: $event }"
    @update:start-time="editor.form.time_config = { ...(editor.form.time_config || {}), start_time: $event }"
    @update:day-label="editor.form.time_config = { ...(editor.form.time_config || {}), day_label: $event }"
    @update:initial-day="editor.form.time_config = { ...(editor.form.time_config || {}), initial_day: $event }"
    @update:time-format="editor.form.time_config = { ...(editor.form.time_config || {}), time_format: $event }"
    @update:unit-name="editor.form.time_config = { ...(editor.form.time_config || {}), unit_name: $event }"
    @update:initial-value="editor.form.time_config = { ...(editor.form.time_config || {}), initial_value: $event }"
    @update:calendar-pacing-value="editor.form.time_config = { ...(editor.form.time_config || {}), calendar_pacing_value: $event }"
    @update:calendar-pacing-unit="editor.form.time_config = { ...(editor.form.time_config || {}), calendar_pacing_unit: $event }"
    @update:calendar-max-value="editor.form.time_config = { ...(editor.form.time_config || {}), calendar_max_value: $event }"
    @update:calendar-max-unit="editor.form.time_config = { ...(editor.form.time_config || {}), calendar_max_unit: $event }"
    @save-changes="editor.saveChanges"
  />
</template>
