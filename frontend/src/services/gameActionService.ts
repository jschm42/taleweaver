import type { Ref } from 'vue'

type SendMessage = (content: string) => Promise<void>

function normalizeEntityKey(item: any): string | null {
  const key = (item?.id || item?.name || '').toString().trim()
  return key || null
}

async function runInFlightGuard(inFlight: Ref<boolean>, task: () => Promise<void>): Promise<void> {
  if (inFlight.value) return
  inFlight.value = true
  try {
    await task()
  } finally {
    inFlight.value = false
  }
}

async function runInFlightGuardWithResult(inFlight: Ref<boolean>, task: () => Promise<void>): Promise<boolean> {
  if (inFlight.value) return false
  inFlight.value = true
  try {
    await task()
    return true
  } finally {
    inFlight.value = false
  }
}

export const gameActionService = {
  async sendIfUnlocked(isBlocked: boolean, sendMessage: SendMessage, command: string): Promise<void> {
    if (isBlocked) return
    await sendMessage(command)
  },

  shouldRunRulePass(isBlocked: boolean, ruleMode?: string): boolean {
    return !isBlocked && ruleMode !== 'chat'
  },

  async runCombatCommand(inFlight: Ref<boolean>, sendMessage: SendMessage, command: string): Promise<boolean> {
    return await runInFlightGuardWithResult(inFlight, async () => {
      await sendMessage(command)
    })
  },

  async runLootCommand(inFlight: Ref<boolean>, sendMessage: SendMessage, action: 'take' | 'leave', item: any): Promise<void> {
    const key = normalizeEntityKey(item)
    if (!key) return

    await runInFlightGuard(inFlight, async () => {
      await sendMessage(`/loot ${action} ${key}`)
    })
  },

  async runLootDone(
    inFlight: Ref<boolean>,
    sendMessage: SendMessage,
    markClosing: () => void,
    clearClosingIfNoCombat: () => void,
  ): Promise<void> {
    if (inFlight.value) return
    markClosing()
    inFlight.value = true
    try {
      await sendMessage('/loot done')
    } finally {
      inFlight.value = false
      clearClosingIfNoCombat()
    }
  },
}
