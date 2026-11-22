/** Shares the Region Builder page state with its cards. */
import { inject, provide, type InjectionKey } from 'vue'
import type { RegionBuilderState } from '@/composables/regionBuilder/useRegionBuilder'

const KEY: InjectionKey<RegionBuilderState> = Symbol('regionBuilder')

export function provideRegionBuilder(state: RegionBuilderState): void {
  provide(KEY, state)
}

export function useRegionBuilderContext(): RegionBuilderState {
  const state = inject(KEY)
  if (!state) throw new Error('useRegionBuilderContext() needs provideRegionBuilder() in a parent.')
  return state
}
