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
}

export function useGameProgressState(options: UseGameProgressStateOptions) {
  const {
    sheet,
    quests,
    status,
    isCompleted,
    pendingTerminalEpilogue,
    gameSettings,
    createTerminalEpilogue,
    refreshUser,
  } = options

  const showSuccess = ref(false)
  const showGameOver = ref(false)
  const trackedQuestId = ref<string | null>(null)
  const clockTick = ref(false)

  const gameTime = computed(() => {
    if (!(sheet.value as any)?.start_datetime && (sheet.value as any)?.time_system !== 'relative') return null

    const timeSystem = (sheet.value as any)?.time_system || 'calendar'
    const timeConfig = (sheet.value as any)?.time_config || {}
    const dayLabel = timeConfig.day_label || 'Day'
    const elapsedMinutes = (sheet.value as any)?.in_game_time ?? 0

    if (timeSystem === 'relative') {
      const totalMinutes = elapsedMinutes
      let baseHour = 8
      if (timeConfig.start_time) {
        const [h] = timeConfig.start_time.split(':').map(Number)
        if (!isNaN(h)) baseHour = h
      }

      const totalHours = Math.floor(totalMinutes / 60)
      const extraMinutes = totalMinutes % 60
      const currentHour = (baseHour + totalHours) % 24
      const daysPassed = Math.floor((baseHour + totalHours) / 24)

      const timeStr = `${currentHour.toString().padStart(2, '0')}:${extraMinutes.toString().padStart(2, '0')}`
      return {
        date: `${dayLabel} ${1 + daysPassed}`,
        dateShort: `${dayLabel} ${1 + daysPassed}`,
        time: timeStr,
      }
    }

    const start = new Date((sheet.value as any).start_datetime || 0)
    if (Number.isNaN(start.getTime())) return null

    const current = new Date(start.getTime() + elapsedMinutes * 60_000)

    const date = current.toLocaleDateString('de-DE', {
      weekday: 'long',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    })

    const dateShort = (() => {
      const d = current.getDate().toString().padStart(2, '0')
      const m = (current.getMonth() + 1).toString().padStart(2, '0')
      const y = current.getFullYear().toString()
      const yShort = y.slice(-2)

      switch (gameSettings.value.date_format) {
        case 'MM/DD/YY':
          return `${m}/${d}/${yShort}`
        case 'YY-MM-DD':
          return `${yShort}-${m}-${d}`
        default:
          return `${d}.${m}.${y}`
      }
    })()

    const time = current.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: !gameSettings.value.clock_24h,
    }).replace(/^0/, '')

    const time24 = current.toLocaleTimeString('de-DE', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })

    return {
      date,
      dateShort,
      time: gameSettings.value.clock_24h ? time24 : time,
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

  watch(isCompleted, (val) => {
    if (val && pendingTerminalEpilogue.value) {
      showSuccess.value = true
    }
  })

  watch(status, async (val) => {
    if (val === 'game_over' && pendingTerminalEpilogue.value) {
      showGameOver.value = true
      await refreshUser()
    } else if (isCompleted.value && pendingTerminalEpilogue.value) {
      showSuccess.value = true
      await refreshUser()
    }
  })

  watch(pendingTerminalEpilogue, async (pending) => {
    if (!pending) {
      showSuccess.value = false
      showGameOver.value = false
      return
    }

    if (status.value === 'game_over') {
      showGameOver.value = true
    } else if (isCompleted.value) {
      showSuccess.value = true
    }

    await refreshUser()
  })

  async function continueCompletedGame(): Promise<void> {
    showSuccess.value = false
    await createTerminalEpilogue()
    await refreshUser()
  }

  async function continueGameOverReadOnly(): Promise<void> {
    showGameOver.value = false
    await createTerminalEpilogue()
    await refreshUser()
  }

  function setTrackedQuest(questId: string | null): void {
    trackedQuestId.value = questId
  }

  return {
    showSuccess,
    showGameOver,
    trackedQuestId,
    clockTick,
    gameTime,
    continueCompletedGame,
    continueGameOverReadOnly,
    setTrackedQuest,
  }
}
