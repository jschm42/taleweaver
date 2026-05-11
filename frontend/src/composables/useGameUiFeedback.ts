import { watch, type Ref } from 'vue'

type UseGameUiFeedbackOptions = {
  sheet: Ref<any>
  nodes: Ref<Record<string, any>>
  quests: Ref<any[]>
  inventoryGlow: Ref<boolean>
  mapGlow: Ref<boolean>
  questGlow: Ref<boolean>
}

const GLOW_DURATION_MS = 3000

function triggerGlow(target: Ref<boolean>): void {
  target.value = true
  setTimeout(() => {
    target.value = false
  }, GLOW_DURATION_MS)
}

export function useGameUiFeedback(options: UseGameUiFeedbackOptions): void {
  const {
    sheet,
    nodes,
    quests,
    inventoryGlow,
    mapGlow,
    questGlow,
  } = options

  watch(() => sheet.value?.inventory, (newInv, oldInv) => {
    if (oldInv && newInv && newInv.length > oldInv.length) {
      triggerGlow(inventoryGlow)
    }
  }, { deep: true })

  watch(() => nodes.value, (newNodes, oldNodes) => {
    if (oldNodes && newNodes && newNodes.length > oldNodes.length) {
      triggerGlow(mapGlow)
    }
  }, { deep: true })

  watch(() => quests.value, (newQuests, oldQuests) => {
    if (oldQuests && newQuests) {
      const newActive = newQuests.filter(q => q.status === 'active').length
      const oldActive = oldQuests.filter(q => q.status === 'active').length
      if (newActive > oldActive) {
        triggerGlow(questGlow)
      }
    }
  }, { deep: true })
}
