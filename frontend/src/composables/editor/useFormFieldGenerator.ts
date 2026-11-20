/**
 * AI generation for one adventure text setting: the result goes into the draft (`editor.form`),
 * so the author reviews it and saves or discards it with the save bar.
 */
import type { EditorContext } from '@/composables/editor/editorContext'

export interface FormFieldGenerator {
  generate: (field: string) => Promise<void>
  isGenerating: (field: string) => boolean
}

export function useFormFieldGenerator(editor: EditorContext): FormFieldGenerator {
  async function generate(field: string): Promise<void> {
    // handleGenerateField writes its result into tempValue (the old click-to-edit buffer).
    editor.tempValue = ''
    await editor.handleGenerateField(field)
    if (editor.tempValue) {
      ;(editor.form as Record<string, unknown>)[field] = editor.tempValue
    }
    editor.tempValue = ''
  }

  function isGenerating(field: string): boolean {
    return Boolean(editor.isGeneratingField[field])
  }

  return { generate, isGenerating }
}
