import { computed, ref, watch, type Ref } from 'vue'
import { gameCommandService } from '@/services/gameCommandService'
import { isConsumableEntity, normalizeHoverEntity } from '@/services/hoverEntityService'

type ContextMenuState = {
  x: number
  y: number
  items: any[]
  title: string
} | null

type UseGameInteractionStateOptions = {
  isActionInputBlocked: Ref<boolean>
  ruleMode: Ref<string | undefined>
  npcMetadata: Ref<Record<string, any>>
  handlePlayerInput: (content: string) => Promise<void>
}

export function useGameInteractionState(options: UseGameInteractionStateOptions) {
  const {
    isActionInputBlocked,
    ruleMode,
    npcMetadata,
    handlePlayerInput,
  } = options

  const hoveredEntity = ref<any>(null)
  const mousePos = ref({ x: 0, y: 0 })
  const tooltipImageFailed = ref(false)
  const contextMenu = ref<ContextMenuState>(null)

  const tooltipStyle = computed(() => {
    if (!hoveredEntity.value) return {}
    const TOOLTIP_WIDTH = 384 // w-96 = 24rem = 384px
    const OFFSET = 20
    const mx = mousePos.value.x
    const my = mousePos.value.y
    const threshold = window.innerHeight * 0.5

    // Flip left if tooltip would overflow right edge
    const x = mx + OFFSET + TOOLTIP_WIDTH > window.innerWidth
      ? mx - TOOLTIP_WIDTH - OFFSET
      : mx + OFFSET

    const style: Record<string, string> = {
      left: `${Math.max(8, x)}px`,
    }

    if (my > threshold) {
      style.bottom = `${window.innerHeight - my + 10}px`
      style.top = 'auto'
    } else {
      style.top = `${my + 10}px`
      style.bottom = 'auto'
    }
    return style
  })

  const isConsumableHover = computed(() => isConsumableEntity(hoveredEntity.value))

  const handleHover = (ent: any, event: MouseEvent) => {
    tooltipImageFailed.value = false
    hoveredEntity.value = normalizeHoverEntity(ent)
    mousePos.value = { x: event.clientX, y: event.clientY }
  }

  const handleChatNpcHover = (name: string, event: MouseEvent) => {
    const metadata = npcMetadata.value[name]
    if (metadata) {
      tooltipImageFailed.value = false
      hoveredEntity.value = normalizeHoverEntity({ ...metadata, entity_type: 'NPC' })
      mousePos.value = { x: event.clientX, y: event.clientY }
    }
  }

  const onTooltipImageError = (): void => {
    tooltipImageFailed.value = true
  }

  const openContextMenu = (entity: any, event: MouseEvent) => {
    if (isActionInputBlocked.value) return

    const menu = gameCommandService.buildContextMenu(entity, ruleMode.value)
    if (!menu) return

    contextMenu.value = {
      x: event.clientX,
      y: event.clientY,
      items: menu.items,
      title: menu.title,
    }

    hoveredEntity.value = null
  }

  const handleMenuSelect = async (item: any) => {
    if (isActionInputBlocked.value) return
    const action = item.action
    contextMenu.value = null
    await handlePlayerInput(action)
  }

  watch(() => hoveredEntity.value?.image_url, () => {
    tooltipImageFailed.value = false
  })

  return {
    hoveredEntity,
    mousePos,
    tooltipImageFailed,
    contextMenu,
    tooltipStyle,
    isConsumableHover,
    handleHover,
    handleChatNpcHover,
    onTooltipImageError,
    openContextMenu,
    handleMenuSelect,
  }
}
