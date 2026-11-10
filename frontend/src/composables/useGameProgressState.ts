import { computed, ref, watch, type Ref } from 'vue'
import type { GameSettings } from '@/services/gameViewService'

type UseGameProgressStateOptions = {
  sheet: Ref<any>
  quests: Ref<any[]>
  status: Ref<string>
  isCompleted: Ref<boolean>
  pendingTerminalEpilogue: Ref<boolean>
  gameSettings: Ref<GameSettings>
  createTerminalEpilogue: () => Promise<void>
  refreshUser: () => Promise<any>
  /** While true the ending waits, e.g. until the combat dialog showed the lost fight. */
  holdEnding?: Ref<boolean>
}

export function useGameProgressState(options: UseGameProgressStateOptions) {
  const {
    sheet,
    quests,
    status,
    isCompleted,
    pendingTerminalEpilogue,
    createTerminalEpilogue,
    refreshUser,
    holdEnding,
  } = options

  const trackedQuestId = ref<string | null>(null)
  const clockTick = ref(false)

  const gameTime = computed(() => {
    if (!(sheet.value as any)?.clock_enabled) {
      return null
    }

    const elapsedMinutes = (sheet.value as any)?.in_game_time ?? 0
    const timeSystem = (sheet.value as any)?.time_system === 'units' ? 'units' : 'relative'
    const timeConfig = (sheet.value as any)?.time_config || {}
    const dayLabel = (timeConfig.day_label || 'Day').trim()

    if (timeSystem === 'units') {
      const unitName = timeConfig.unit_name || timeConfig.unit || 'Units'
      const initialVal = Number(timeConfig.initial_value ?? 0)
      const currentVal = (isNaN(initialVal) ? 0 : initialVal) + (Number(elapsedMinutes) || 0)
      const formattedVal = Number.isInteger(currentVal)
        ? currentVal.toString()
        : currentVal.toLocaleString('en-US', { maximumFractionDigits: 2 })
      return {
        isUnits: true,
        unitName,
        value: formattedVal,
        date: unitName,
        dateShort: unitName,
        time: formattedVal,
      }
    }

    const initialDay = Number(timeConfig.initial_day ?? 1) || 1
    const totalMinutes = elapsedMinutes
    let baseHour = 8
    let baseMin = 0
    if (timeConfig.start_time) {
      const [h, m] = String(timeConfig.start_time).split(':').map(Number)
      if (!isNaN(h)) baseHour = h
      if (!isNaN(m)) baseMin = m
    }

    const totalMinsCombined = baseHour * 60 + baseMin + totalMinutes
    const daysPassed = Math.floor(totalMinsCombined / (24 * 60))
    const remDayMins = ((totalMinsCombined % (24 * 60)) + (24 * 60)) % (24 * 60)
    const currentHour = Math.floor(remDayMins / 60)
    const currentMin = remDayMins % 60

    let timeStr = `${currentHour.toString().padStart(2, '0')}:${currentMin.toString().padStart(2, '0')}`
    if (timeConfig.time_format === '12h') {
      const h12 = currentHour % 12 || 12
      const ampm = currentHour >= 12 ? 'PM' : 'AM'
      timeStr = `${h12.toString().padStart(2, '0')}:${currentMin.toString().padStart(2, '0')} ${ampm}`
    }
    const currentDay = initialDay + daysPassed
    return {
      isUnits: false,
      unitName: undefined,
      value: undefined,
      date: `${dayLabel} ${currentDay}`,
      dateShort: `${dayLabel} ${currentDay}`,
      time: timeStr,
    }
  })

  watch(() => sheet.value?.in_game_time, () => {
    clockTick.value = true
    setTimeout(() => {
      clockTick.value = false
    }, 600)
  })

  watch(quests, (newQuests) => {
    if (trackedQuestId.value) {
      const tracked = newQuests.find(q => q.id === trackedQuestId.value)
      if (tracked && tracked.status === 'completed') {
        trackedQuestId.value = null
      }
    }

    if (!trackedQuestId.value && newQuests && newQuests.length > 0) {
      const firstMain = newQuests.find(q => q.is_main && q.status === 'open')
      if (firstMain) {
        trackedQuestId.value = firstMain.id
      }
    }
  }, { immediate: true })

  // The end of the adventure is told in the story: once the last stream is done, the epilogue
  // narration and the ending card (win / game over) are created right away, no modal.
  const isCreatingEpilogue = ref(false)

  async function finishAdventure(): Promise<void> {
    if (!pendingTerminalEpilogue.value || isCreatingEpilogue.value || holdEnding?.value) return
    if (status.value !== 'game_over' && !isCompleted.value) return
    if (status.value === 'connecting' || status.value === 'loading') return
    isCreatingEpilogue.value = true
    try {
      await createTerminalEpilogue()
      await refreshUser()
    } finally {
      isCreatingEpilogue.value = false
    }
  }

  watch([pendingTerminalEpilogue, status, isCompleted, () => !!holdEnding?.value], () => {
    void finishAdventure()
  }, { immediate: true })

  function setTrackedQuest(questId: string | null): void {
    trackedQuestId.value = questId
  }

  return {
    trackedQuestId,
    clockTick,
    gameTime,
    setTrackedQuest,
  }
}
