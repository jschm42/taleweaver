export type UiPanelCommand = 'map' | 'sheet' | 'quests'

export type SpecialGameCommand =
  | 'walkthrough'
  | 'walkthroughReveal'
  | 'hint'
  | 'debugWalkthrough'
  | 'debugRevealMap'
  | 'debugSession'

export type ContextMenuItem = {
  label: string
  action: string
}

export type ContextMenuModel = {
  title: string
  items: ContextMenuItem[]
}

const OPEN_CONTAINER_PREFIX = '[OPEN_CONTAINER] '
const OPEN_TEXT_LOG_PREFIX = '[OPEN_TEXT_LOG] '
const PREFILL_SAY_TO_PREFIX = '[PREFILL_SAY_TO] '

const isContainerEntity = (entity: any): boolean => {
  if (!entity) return false
  return String(entity.item_type || '').toUpperCase() === 'CONTAINER'
}

const isReadableEntity = (entity: any): boolean => {
  if (!entity) return false
  return String(entity.item_type || '').toUpperCase() === 'READABLE'
}

const isConsumableEntity = (entity: any): boolean => {
  if (!entity) return false
  return String(entity.item_type || '').toUpperCase() === 'CONSUMABLE'
}

const isPortableEntity = (entity: any): boolean => {
  if (!entity) return false
  return entity.is_portable !== false
}

const isStationaryEntity = (entity: any): boolean => {
  if (!entity) return false
  return String(entity.movement_type || '').toUpperCase() === 'STATIONARY'
}

export const gameCommandService = {
  resolveUiPanelCommand(normalized: string): UiPanelCommand | null {
    if (normalized === '/map') return 'map'
    if (normalized === '/sheet' || normalized === '/inventory') return 'sheet'
    if (normalized === '/quests') return 'quests'
    return null
  },

  resolveSpecialCommand(normalized: string): SpecialGameCommand | null {
    switch (normalized) {
      case '/walkthrough':
        return 'walkthrough'
      case '/walkthrough reveal':
        return 'walkthroughReveal'
      case '/hint':
        return 'hint'
      case '/debug walkthrough':
        return 'debugWalkthrough'
      case '/debug reveal_map':
        return 'debugRevealMap'
      case '/debug session':
        return 'debugSession'
      default:
        return null
    }
  },

  isAllowedCombatCommand(content: string): boolean {
    const msg = content.trim().toLowerCase()
    return msg === 'attack' || msg === '/attack' || msg === 'run' || msg === '/run' || msg.startsWith('/consume ')
  },

  resolveEntityActionCommand(actionId: string, entity: any): { command: string | null; errorMessage: string | null } {
    const targetName = entity?.name || entity?.id
    if (!targetName) {
      return { command: null, errorMessage: null }
    }

    const isDefeatedNpc = entity?.entity_type === 'NPC' && (entity?.is_defeated === true || entity?.hp === 0)
    if (isDefeatedNpc && actionId !== 'inspect') {
      return { command: null, errorMessage: 'This enemy is defeated. Only inspect is available.' }
    }

    switch (actionId) {
      case 'talk':
        return { command: `/say Hello, ${targetName}.`, errorMessage: null }
      case 'inspect':
        return { command: `/inspect ${targetName}`, errorMessage: null }
      case 'open':
        return { command: `/open ${targetName}`, errorMessage: null }
      case 'read':
        return { command: `/read ${targetName}`, errorMessage: null }
      case 'take':
        return { command: `/take ${targetName}`, errorMessage: null }
      case 'attack':
        if (entity?.is_attackable === false) {
          return { command: null, errorMessage: 'You cannot attack this target.' }
        }
        return { command: `/attack ${targetName}`, errorMessage: null }
      case 'push':
        return { command: `Push ${targetName}`, errorMessage: null }
      case 'pull':
        return { command: `Pull ${targetName}`, errorMessage: null }
      default:
        return { command: `${actionId} ${targetName}`, errorMessage: null }
    }
  },

  shouldAutoTakeOnEntityClick(entity: any): boolean {
    return entity?.entity_type === 'OBJECT' && entity?.is_portable !== false && !isContainerEntity(entity)
  },

  buildContextMenu(entity: any, _ruleMode?: string): ContextMenuModel | null {
    const items: ContextMenuItem[] = []
    let title = entity?.name || 'Action'

    if (entity?.id === 'PLAYER') {
      title = 'You'
      items.push({ label: 'Inspect', action: '/sheet' })
      items.push({ label: 'Rest', action: 'Rest' })
    } else if (entity?.entity_type === 'NPC') {
      items.push({ label: 'Talk', action: `${PREFILL_SAY_TO_PREFIX}${entity.name || ''}` })
      items.push({ label: 'Inspect', action: `/inspect ${entity.name}` })
      const isDefeatedNpc = entity?.is_defeated === true || entity?.hp === 0
      if (!isDefeatedNpc && entity?.is_attackable !== false) {
        items.push({ label: 'Attack', action: `/attack ${entity.name}` })
      }
    } else if (entity?.entity_type === 'SCENE') {
      items.push({ label: 'Search', action: 'Search the area' })
      items.push({ label: 'Look around', action: 'Look around' })
    } else if (entity?.entity_type === 'OBJECT' || entity?.entity_type === 'ITEM') {
      items.push({ label: 'Inspect', action: `/inspect ${entity.name}` })

      if (isPortableEntity(entity)) {
        items.push({ label: 'Take', action: `/take ${entity.name}` })
      }

      if (!isStationaryEntity(entity)) {
        items.push({ label: 'Pull', action: `Pull ${entity.name}` })
        items.push({ label: 'Push', action: `Push ${entity.name}` })
      }

      if (isConsumableEntity(entity)) {
        items.push({ label: 'Consume', action: `/consume ${entity.name}` })
      }

      if (isContainerEntity(entity)) {
        items.push({ label: 'Open', action: `${OPEN_CONTAINER_PREFIX}${entity.id || entity.name}` })
      }

      if (isReadableEntity(entity)) {
        items.push({ label: 'Read', action: `${OPEN_TEXT_LOG_PREFIX}${entity.id || entity.name}` })
      }
    }

    if (items.length === 0) return null
    return { title, items }
  },

  buildInventoryContextMenu(item: any, _ruleMode?: string): ContextMenuModel | null {
    const items: ContextMenuItem[] = []
    const title = item?.name || 'Item'

    const isEquippable = !!item.slot || (item.wearable_slots && item.wearable_slots.length > 0)
    const isEquipped = !!item.equipped_slot

    if (isEquippable) {
      if (isEquipped) {
        items.push({ label: 'Unequip', action: `/unequip ${item.equipped_slot}` })
      } else {
        items.push({ label: 'Equip', action: `/equip ${item.name}` })
      }
    } else if (isConsumableEntity(item)) {
      items.push({ label: 'Consume', action: `/consume ${item.name}` })
    }

    if (isContainerEntity(item)) {
      items.push({ label: 'Open', action: `${OPEN_CONTAINER_PREFIX}${item.id || item.name}` })
    }

    if (isReadableEntity(item)) {
      items.push({ label: 'Read', action: `${OPEN_TEXT_LOG_PREFIX}${item.id || item.name}` })
    }

    items.push({ label: 'Drop', action: `/drop ${item.name}` })
    items.push({ label: 'Inspect', action: `/inspect ${item.name}` })

    return items.length > 0 ? { title, items } : null
  },
}
