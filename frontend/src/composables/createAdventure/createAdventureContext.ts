/** Shares the "Generate adventure" page state with its section components. */
import { inject, provide, type InjectionKey } from 'vue'
import type { CreateAdventureState } from '@/composables/createAdventure/useCreateAdventure'

const KEY: InjectionKey<CreateAdventureState> = Symbol('createAdventure')

export function provideCreateAdventure(state: CreateAdventureState): void {
  provide(KEY, state)
}

export function useCreateAdventureContext(): CreateAdventureState {
  const state = inject(KEY)
  if (!state) throw new Error('useCreateAdventureContext() needs provideCreateAdventure() in a parent.')
  return state
}
