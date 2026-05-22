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
  icon: string
  color: string
}

export type ContextMenuModel = {
  title: string
  items: ContextMenuItem[]
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
        return { command: `/talk ${targetName}`, errorMessage: null }
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
    return entity?.entity_type === 'OBJECT' && entity?.is_portable !== false
  },

  buildContextMenu(entity: any, ruleMode?: string): ContextMenuModel | null {
    const items: ContextMenuItem[] = []
    let title = entity?.name || 'Action'

    if (entity?.id === 'PLAYER') {
      title = 'You'
      items.push({ label: 'Inspect', action: '/sheet', icon: 'ra ra-player', color: 'text-cyan-400' })
      items.push({ label: 'Rest', action: 'Take a rest', icon: 'ra ra-sleeping-bag', color: 'text-emerald-400' })
      items.push({ label: 'Sing', action: 'Sing a song', icon: 'ra ra-music-spell', color: 'text-pink-400' })
      items.push({ label: 'Dance', action: 'Start dancing', icon: 'ra ra-double-team', color: 'text-orange-400' })
    } else if (entity?.entity_type === 'NPC') {
      items.push({ label: 'Inspect', action: `/inspect ${entity.name}`, icon: 'ra ra-scroll-unfurled', color: 'text-cyan-400' })
      const isDefeatedNpc = entity?.is_defeated === true || entity?.hp === 0
      if (!isDefeatedNpc) {
        if (ruleMode === 'rpg' && entity?.is_attackable !== false) {
          items.push({ label: 'Attack', action: `/attack ${entity.name}`, icon: 'ra ra-sword', color: 'text-red-400' })
        }
        items.push({ label: 'Chat', action: `/talk ${entity.name}`, icon: 'ra ra-speech-bubbles', color: 'text-blue-400' })
      }
    } else if (entity?.entity_type === 'SCENE') {
      items.push({ label: 'Look around', action: 'Look around', icon: 'ra ra-eye', color: 'text-indigo-400' })
      items.push({ label: 'Search', action: 'Search the area', icon: 'ra ra-magnifying-glass', color: 'text-emerald-400' })
      items.push({ label: 'Read signs/logs', action: '/read surroundings', icon: 'ra ra-book-cover', color: 'text-violet-400' })
    } else if (entity?.entity_type === 'OBJECT' || entity?.entity_type === 'ITEM') {
      items.push({ label: 'Inspect', action: `/inspect ${entity.name}`, icon: 'ra ra-scroll-unfurled', color: 'text-cyan-400' })
      items.push({ label: 'Open', action: `/open ${entity.name}`, icon: 'ra ra-chest', color: 'text-lime-400' })
      items.push({ label: 'Read', action: `/read ${entity.name}`, icon: 'ra ra-book-cover', color: 'text-violet-400' })
      items.push({ label: 'Pick up', action: `/take ${entity.name}`, icon: 'ra ra-hand', color: 'text-amber-400' })
      items.push({ label: 'Push', action: `Push ${entity.name}`, icon: 'ra ra-cog', color: 'text-slate-400' })
      items.push({ label: 'Pull', action: `Pull ${entity.name}`, icon: 'ra ra-tread', color: 'text-slate-400' })
      items.push({ label: 'Hit', action: `Hit ${entity.name}`, icon: 'ra ra-hammer', color: 'text-red-400' })
      items.push({ label: 'Smell', action: `Smell ${entity.name}`, icon: 'ra ra-scent', color: 'text-pink-400' })
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
        items.push({ label: 'Unequip', action: `/unequip ${item.equipped_slot}`, icon: 'ra ra-hand', color: 'text-amber-400' })
      } else {
        items.push({ label: 'Equip', action: `/equip ${item.name}`, icon: 'ra ra-vest', color: 'text-emerald-400' })
      }
    } else if (item.item_type === 'CONSUMABLE') {
      items.push({ label: 'Consume', action: `/consume ${item.name}`, icon: 'ra ra-flask', color: 'text-emerald-400' })
    }

    items.push({ label: 'Drop', action: `/drop ${item.name}`, icon: 'ra ra-bottom-right', color: 'text-red-400' })
    items.push({ label: 'Inspect', action: `/inspect ${item.name}`, icon: 'ra ra-scroll-unfurled', color: 'text-cyan-400' })

    return items.length > 0 ? { title, items } : null
  },
}
