/**
 * Parts of the entity form that save through their own endpoints (combat aggression, combat
 * profile, special attacks, companion settings). Inside the entity form they register here, hide
 * their own save buttons and are saved by the form's "Save changes" before the entity itself, so
 * the page keeps one save action (docs/specs/workbench_ui.md, 6.1). Used anywhere else (no
 * registry provided), they keep their own save button.
 */
import { computed, inject, onBeforeUnmount, onMounted, provide, shallowReactive, type ComputedRef, type InjectionKey } from 'vue'

export interface EntitySubform {
  /** Shown in error messages, e.g. "Combat profile". */
  label: string
  isDirty: () => boolean
  /** First validation problem, or null. */
  error: () => string | null
  /** Saves through the part's own endpoint; throws on failure. */
  save: () => Promise<void>
}

interface Registry {
  register: (subform: EntitySubform) => () => void
}

const SUBFORMS: InjectionKey<Registry> = Symbol('entity-subforms')

export interface EntitySubforms {
  dirtyCount: ComputedRef<number>
  /** Saves every changed part; returns an error message, or null when all succeeded. */
  saveDirty: () => Promise<string | null>
}

export function provideEntitySubforms(): EntitySubforms {
  const parts = shallowReactive<EntitySubform[]>([])

  provide(SUBFORMS, {
    register(subform) {
      parts.push(subform)
      return () => {
        const index = parts.indexOf(subform)
        if (index !== -1) parts.splice(index, 1)
      }
    },
  })

  const dirtyCount = computed(() => parts.filter((part) => part.isDirty()).length)

  async function saveDirty(): Promise<string | null> {
    const dirty = parts.filter((part) => part.isDirty())
    for (const part of dirty) {
      const problem = part.error()
      if (problem) return `${part.label}: ${problem}`
    }
    for (const part of dirty) {
      try {
        await part.save()
      } catch (err) {
        return `${part.label}: ${err instanceof Error ? err.message : 'could not be saved.'}`
      }
    }
    return null
  }

  return { dirtyCount, saveDirty }
}

/** Registers a part with the surrounding entity form; returns true when it is embedded there. */
export function useEntitySubform(subform: EntitySubform): boolean {
  const registry = inject(SUBFORMS, null)
  if (!registry) return false
  let unregister: (() => void) | null = null
  onMounted(() => {
    unregister = registry.register(subform)
  })
  onBeforeUnmount(() => unregister?.())
  return true
}
