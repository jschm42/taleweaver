import { computed } from 'vue'
import type { CharacterSheet } from '@/types'
import { resolveAccent, resolveSkin, skinPreferenceOf } from './skinRegistry'

/**
 * Active dialog skin for a session (player preference → adventure theme → tone),
 * as the `data-skin` value and accent style to put on a `.tw-skin` root.
 */
export function useSheetSkin(sheet: () => CharacterSheet | null | undefined) {
  const skinPreference = computed(() => skinPreferenceOf(sheet()?.ui_skin))

  const activeSkin = computed(() =>
    resolveSkin(skinPreference.value, sheet()?.ui_theme, sheet()?.adventure_tone)
  )

  const skinStyle = computed((): Record<string, string> => {
    const accent = resolveAccent(skinPreference.value, sheet()?.ui_theme)
    if (!accent) return {}
    return { '--tw-accent': accent, '--tw-accent-soft': accent }
  })

  return { activeSkin, skinStyle }
}
