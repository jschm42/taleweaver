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
  onAction?: () => void
  onDirectAction?: (action: string) => boolean
}

export function useGameInteractionState(options: UseGameInteractionStateOptions) {
  const {
    isActionInputBlocked,
    ruleMode,
    npcMetadata,
    handlePlayerInput,
    onAction,
    onDirectAction,
  } = options

  const hoveredEntity = ref<any>(null)
  const mousePos = ref({ x: 0, y: 0 })
  const tooltipImageFailed = ref(false)
  const contextMenu = ref<ContextMenuState>(null)

  const tooltipStyle = computed(() => {
    if (!hoveredEntity.value) return {}
    const OFFSET = 20
    const VERTICAL_LIFT = 34
    const EDGE_GAP = 8
    const mx = mousePos.value.x
    const my = mousePos.value.y
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight
    const tooltipWidth = Math.max(280, Math.min(384, viewportWidth - EDGE_GAP * 2))

    const availableBelow = Math.max(0, viewportHeight - my - OFFSET - EDGE_GAP)
    const availableAbove = Math.max(0, my - OFFSET - EDGE_GAP)
    const renderAbove = availableBelow < 300 && availableAbove > availableBelow

    // Flip left if tooltip would overflow right edge
    const x = mx + OFFSET + tooltipWidth > viewportWidth
      ? mx - tooltipWidth - OFFSET
      : mx + OFFSET

    const maxLeft = Math.max(EDGE_GAP, viewportWidth - tooltipWidth - EDGE_GAP)
    const clampedLeft = Math.min(Math.max(EDGE_GAP, x), maxLeft)

    const style: Record<string, string> = {
      left: `${clampedLeft}px`,
      width: `${tooltipWidth}px`,
      maxWidth: `calc(100vw - ${EDGE_GAP * 2}px)`,
      maxHeight: `${Math.max(220, (renderAbove ? availableAbove : availableBelow))}px`,
    }

    if (renderAbove) {
      style.bottom = `${Math.max(EDGE_GAP, viewportHeight - my + 10 + VERTICAL_LIFT)}px`
      style.top = 'auto'
    } else {
      style.top = `${Math.max(EDGE_GAP, my + 10 - VERTICAL_LIFT)}px`
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

  const openInventoryContextMenu = (item: any, event: MouseEvent) => {
    if (isActionInputBlocked.value) return

    const menu = gameCommandService.buildInventoryContextMenu(item, ruleMode.value)
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

    if (typeof action === 'string' && onDirectAction?.(action)) {
      return
    }

    if (onAction) onAction()
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
    openInventoryContextMenu,
    handleMenuSelect,
  }
}
