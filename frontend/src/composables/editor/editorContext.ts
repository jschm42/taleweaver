/**
 * Shares the adventure editor state with its pages. AdventureEditorView creates it once with
 * provideEditor(); every page and modal reads it with useEditor(). The context is reactive, so
 * templates use plain property access (`editor.form.title`, `editor.activeTab = 'map'`).
 */
import { computed, inject, provide, reactive, type InjectionKey } from 'vue'
import { useAdventureEditor, type AdventureEditorProps } from '@/composables/editor/useAdventureEditor'

function createEditorContext(props: AdventureEditorProps) {
  return reactive({
    ...useAdventureEditor(props),
    adventureId: computed(() => props.adventureId),
  })
}

export type EditorContext = ReturnType<typeof createEditorContext>

const EDITOR_CONTEXT: InjectionKey<EditorContext> = Symbol('adventure-editor')

export function provideEditor(props: AdventureEditorProps): EditorContext {
  const editor = createEditorContext(props)
  provide(EDITOR_CONTEXT, editor)
  return editor
}

export function useEditor(): EditorContext {
  const editor = inject(EDITOR_CONTEXT, null)
  if (!editor) {
    throw new Error('useEditor() is only available inside AdventureEditorView.')
  }
  return editor
}
