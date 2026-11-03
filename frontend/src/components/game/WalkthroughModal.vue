<script setup lang="ts">
import { computed } from 'vue'
import { useDialogSkin } from '@/skins/dialogSkin'
import { formatEntityRefs } from '@/utils/entityRefs'

type WorldEntity = {
  id?: string
  name?: string
  description?: string
  entity_type?: string
  [key: string]: unknown
}

type WalkthroughPart =
  | { type: 'text'; text: string }
  | { type: 'item'; item: WorldEntity; label: string }

const props = defineProps<{
  open: boolean
  data: any | null
  entities?: WorldEntity[]
}>()

const emit = defineEmits<{
  close: []
  reveal: []
  itemHover: [item: WorldEntity, event: MouseEvent]
  itemLeave: []
}>()

const { activeSkin, skinStyle } = useDialogSkin()

const itemTokenRegex = /\[\[ITEM:([A-Z0-9_]+)\|([^\]]+)\]\]/g

const itemById = computed(() => {
  const map = new Map<string, WorldEntity>()
  const source = props.entities ?? []
  for (const entity of source) {
    if (!entity || entity.entity_type !== 'OBJECT' || !entity.id) continue
    map.set(entity.id.toUpperCase(), entity)
  }
  return map
})

const knownItemIds = computed(() => {
  return [...itemById.value.keys()].sort((a, b) => b.length - a.length)
})

const escapeRegex = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const replaceLegacyIdsInText = (text: string): WalkthroughPart[] => {
  if (!text || knownItemIds.value.length === 0) {
    return text ? [{ type: 'text', text }] : []
  }

  const idPattern = new RegExp(`\\b(${knownItemIds.value.map(escapeRegex).join('|')})\\b`, 'g')
  const parts: WalkthroughPart[] = []
  let lastIndex = 0

  text.replace(idPattern, (match, id, offset) => {
    if (offset > lastIndex) {
      parts.push({ type: 'text', text: text.slice(lastIndex, offset) })
    }

    const item = itemById.value.get(String(id).toUpperCase())
    if (item) {
      parts.push({ type: 'item', item, label: item.name || match })
    } else {
      parts.push({ type: 'text', text: match })
    }

    lastIndex = offset + match.length
    return match
  })

  if (lastIndex < text.length) {
    parts.push({ type: 'text', text: text.slice(lastIndex) })
  }

  return parts.length ? parts : [{ type: 'text', text }]
}

const parseWalkthroughContent = (content: string): WalkthroughPart[] => {
  const parts: WalkthroughPart[] = []
  let lastIndex = 0

  content.replace(itemTokenRegex, (match, rawId, rawLabel, offset) => {
    if (offset > lastIndex) {
      parts.push(...replaceLegacyIdsInText(content.slice(lastIndex, offset)))
    }

    const itemId = String(rawId || '').toUpperCase()
    const tokenLabel = String(rawLabel || '').trim()
    const item = itemById.value.get(itemId)
    if (item) {
      parts.push({ type: 'item', item, label: tokenLabel || item.name || itemId })
    } else {
      parts.push({ type: 'text', text: tokenLabel || itemId || match })
    }

    lastIndex = offset + match.length
    return match
  })

  if (lastIndex < content.length) {
    parts.push(...replaceLegacyIdsInText(content.slice(lastIndex)))
  }

  return parts.length ? parts : [{ type: 'text', text: content }]
}
function fixNewlines(text: string | null | undefined): string {
  if (!text) return ''
  return text.replace(/\\n/g, '\n')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="tw-skin tw-dialog-backdrop fixed inset-0 z-[220] flex items-center justify-center p-4"
        :data-skin="activeSkin"
        :style="skinStyle"
        @click.self="emit('close')"
      >
        <div class="tw-dialog w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col" role="dialog" aria-modal="true" aria-label="Walkthrough">
          <header class="tw-dialog-header px-5 py-4 flex items-center justify-between">
            <div>
              <p class="tw-dialog-eyebrow text-xs">Secret Utility</p>
              <h2 class="tw-dialog-title text-2xl mt-0.5">Walkthrough</h2>
            </div>
            <button type="button" class="tw-dialog-button tw-dialog-button--ghost" @click="emit('close')">Close</button>
          </header>

          <div class="tw-dialog-scroll p-5 overflow-y-auto space-y-4">
            <div class="tw-card p-4">
              <div class="flex items-center justify-between gap-3 flex-wrap">
                <p class="tw-panel-title tw-muted">XP</p>
                <p class="text-lg font-black tabular-nums">{{ data?.current_xp ?? 0 }}</p>
              </div>
              <p class="mt-3 text-sm leading-relaxed whitespace-pre-wrap" v-html="formatEntityRefs(data?.preview || data?.message || 'No walkthrough available.')"></p>
            </div>

            <div v-if="!data?.available" class="tw-dialog-slot p-4 text-sm">
              No walkthrough available for this adventure yet.
            </div>

            <div v-else-if="data?.can_reveal" class="tw-card p-4 border-l-4 !border-l-[var(--tw-accent)]">
              <p class="text-sm mb-3">
                The walkthrough for the current chapter<span v-if="data?.current_chapter_title"> ({{ data.current_chapter_title }})</span>
                is sealed. Each chapter is unlocked separately, and only the chapter you are in can be unlocked.
              </p>
              <button type="button" class="tw-dialog-button" @click="emit('reveal')">
                Unlock Current Chapter ({{ data?.reveal_cost ?? 150 }} XP)
              </button>
            </div>

            <div v-if="data?.available" class="space-y-3">
              <p v-if="data?.steps?.length" class="tw-dialog-eyebrow text-sm">Unlocked Chapters</p>

              <ol v-if="data?.steps && data.steps.length > 0" class="space-y-2">
                <li v-for="(step, index) in data.steps" :key="index" class="tw-card p-3">
                  <p class="tw-muted text-xxs uppercase tracking-widest font-black">Chapter {{ step.chapter ?? index + 1 }}</p>
                  <p v-if="step.title" class="text-sm font-bold mt-1">{{ step.title }}</p>
                  <p class="text-sm mt-1 leading-relaxed whitespace-pre-wrap">
                    <template v-for="(part, partIndex) in parseWalkthroughContent(step.content || '')" :key="`${index}-${partIndex}`">
                      <span v-if="part.type === 'text'">{{ fixNewlines(part.text) }}</span>
                      <span
                        v-else
                        class="tw-dialog-link"
                        @mouseenter="emit('itemHover', part.item, $event)"
                        @mousemove="emit('itemHover', part.item, $event)"
                        @mouseleave="emit('itemLeave')"
                      >
                        {{ part.label }}
                      </span>
                    </template>
                  </p>
                </li>
              </ol>

              <div v-else-if="data?.walkthrough" class="tw-card p-4 text-sm leading-relaxed whitespace-pre-wrap">
                <template v-for="(part, partIndex) in parseWalkthroughContent(data.walkthrough)" :key="`raw-${partIndex}`">
                  <span v-if="part.type === 'text'">{{ fixNewlines(part.text) }}</span>
                  <span
                    v-else
                    class="tw-dialog-link"
                    @mouseenter="emit('itemHover', part.item, $event)"
                    @mousemove="emit('itemHover', part.item, $event)"
                    @mouseleave="emit('itemLeave')"
                  >
                    {{ part.label }}
                  </span>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
