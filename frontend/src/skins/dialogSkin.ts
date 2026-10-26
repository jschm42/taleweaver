import { computed, inject, provide, type ComputedRef, type InjectionKey } from 'vue'
import type { SkinId } from './skinRegistry'

type DialogSkin = {
  activeSkin: ComputedRef<SkinId>
  skinStyle: ComputedRef<Record<string, string>>
}

const DIALOG_SKIN_KEY: InjectionKey<DialogSkin> = Symbol('dialogSkin')

/** Called by the game view so its (teleported) dialogs can wear the session's skin. */
export function provideDialogSkin(skin: DialogSkin) {
  provide(DIALOG_SKIN_KEY, skin)
}

/**
 * Skin for a dialog root: bind `class="tw-skin"`, `:data-skin="activeSkin"` and
 * `:style="skinStyle"`. Falls back to the classic skin outside a game session.
 */
export function useDialogSkin(): DialogSkin {
  return inject(DIALOG_SKIN_KEY, () => ({
    activeSkin: computed<SkinId>(() => 'classic'),
    skinStyle: computed(() => ({})),
  }), true)
}
