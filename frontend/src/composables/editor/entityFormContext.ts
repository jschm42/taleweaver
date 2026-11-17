/**
 * Shares the entity form (EditEntityModal) with its section components in
 * components/editor/entity/. Reactive, so templates use plain access (`ef.localForm.name`).
 */
import { computed, inject, provide, reactive, type InjectionKey } from 'vue'
import { useEntityForm, type EntityFormEmits, type EntityFormProps } from '@/composables/editor/useEntityForm'

function createEntityFormContext(props: EntityFormProps, emit: EntityFormEmits) {
  return reactive({
    ...useEntityForm(props, emit),
    props,
    emit,
    /** Entity kind of the open form ('npc', 'object', 'scene', 'cover', 'protagonist'); '' when none. */
    type: computed(() => props.context?.type ?? ''),
    entityId: computed(() => props.context?.id ?? ''),
  })
}

export type EntityFormContext = ReturnType<typeof createEntityFormContext>

const ENTITY_FORM: InjectionKey<EntityFormContext> = Symbol('entity-form')

export function provideEntityForm(props: EntityFormProps, emit: EntityFormEmits): EntityFormContext {
  const form = createEntityFormContext(props, emit)
  provide(ENTITY_FORM, form)
  return form
}

export function useEntityFormContext(): EntityFormContext {
  const form = inject(ENTITY_FORM, null)
  if (!form) {
    throw new Error('useEntityFormContext() is only available inside EditEntityModal.')
  }
  return form
}
