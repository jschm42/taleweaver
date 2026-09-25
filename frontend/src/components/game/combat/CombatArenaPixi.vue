<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import 'pixi.js/unsafe-eval'
import { Application } from 'pixi.js'
import { CombatStage, type CombatantInfo } from './CombatStage'
import type { CombatState, CharacterSheet } from '@/types'
import { getImageUrl, hasRenderableImagePath } from '@/utils/game_icons'

const props = defineProps<{
  combat: CombatState | null
  playerSheet?: CharacterSheet | null
  npcMetadata?: Record<string, any>
  activeTurn?: string
  sceneImageUrl?: string | null
}>()

const emit = defineEmits<{
  ready: []
}>()

const canvasHostRef = ref<HTMLDivElement | null>(null)
let app: Application | null = null
let stage: CombatStage | null = null
let resizeObserver: ResizeObserver | null = null
let motionMediaQuery: MediaQueryList | null = null

const isPixiReady = ref(false)

function resolvePlayerInfo(): CombatantInfo {
  const p = props.combat?.player
  const sheet = props.playerSheet
  const rawImage = p?.image_url || sheet?.profile_image
  const imageUrl = hasRenderableImagePath(rawImage) ? getImageUrl(rawImage) : null

  return {
    id: 'PLAYER',
    name: sheet?.name ? sheet.name : p?.name || 'Protagonist',
    imageUrl,
    hp: typeof p?.hp === 'number' ? p.hp : 0,
    maxHp: typeof p?.max_hp === 'number' && p.max_hp > 0 ? p.max_hp : (sheet?.max_hp || 100),
    stamina: p?.stamina,
    maxStamina: p?.max_stamina,
    isDefeated: (p?.hp ?? 0) <= 0,
  }
}

function resolveEnemyInfo(): CombatantInfo {
  const enemy = props.combat?.enemy
  const meta = props.npcMetadata?.[enemy?.id || ''] || props.npcMetadata?.[enemy?.name || ''] || {}
  const rawImage = enemy?.image_url || meta.image_url
  const imageUrl = hasRenderableImagePath(rawImage) ? getImageUrl(rawImage) : null

  return {
    id: enemy?.id || 'ENEMY',
    name: enemy?.name || 'Opponent',
    imageUrl,
    hp: typeof enemy?.hp === 'number' ? enemy.hp : 0,
    maxHp: typeof enemy?.max_hp === 'number' && enemy.max_hp > 0 ? enemy.max_hp : (meta.max_hp || 100),
    stamina: enemy?.stamina,
    maxStamina: enemy?.max_stamina,
    isDefeated: (enemy?.hp ?? 0) <= 0,
  }
}

async function syncCombatants(): Promise<void> {
  if (!stage || !isPixiReady.value) return

  const pInfo = resolvePlayerInfo()
  const eInfo = resolveEnemyInfo()

  stage.playerUnit.updateData(pInfo)
  stage.enemyUnit.updateData(eInfo)

  void stage.playerUnit.setAvatar(pInfo.imageUrl)
  void stage.enemyUnit.setAvatar(eInfo.imageUrl)

  const currentTurn = props.activeTurn || props.combat?.turn || 'player'
  stage.playerUnit.setTurn(currentTurn === 'player')
  stage.enemyUnit.setTurn(currentTurn === 'enemy')
}

async function syncBackdrop(): Promise<void> {
  if (!stage || !isPixiReady.value) return
  const rawScene = props.sceneImageUrl
  const sceneUrl = hasRenderableImagePath(rawScene) ? getImageUrl(rawScene) : null
  await stage.setSceneBackground(sceneUrl)
}

// Public API exposed via template ref
defineExpose({
  playAttack: (attacker: 'player' | 'enemy', options?: { isCrit?: boolean; isHit?: boolean }, onImpact?: () => void) => {
    stage?.playAttack(attacker, options, onImpact)
  },
  playHitReaction: (target: 'player' | 'enemy', isCrit?: boolean) => {
    stage?.playHitReaction(target, isCrit)
  },
  playMagicSurge: (target: 'player' | 'enemy', type?: 'heal' | 'arcane' | 'fire') => {
    stage?.playMagicSurge(target, type)
  },
  spawnDamageNumber: (target: 'player' | 'enemy', amount: number | string, type: 'damage' | 'crit' | 'heal' | 'miss') => {
    stage?.spawnDamageNumber(target, amount, type)
  },
  showArcadeBanner: (title: string, subtitle?: string, isCrit = false) => {
    stage?.showArcadeBanner(title, subtitle, isCrit)
  },
  shakeCamera: (intensity?: number, durationMs?: number) => {
    stage?.shakeCamera(intensity, durationMs)
  },
})

watch(() => [props.combat?.player?.hp, props.combat?.enemy?.hp, props.activeTurn], () => {
  void syncCombatants()
})

watch(() => [props.combat?.player?.image_url, props.combat?.enemy?.image_url], () => {
  void syncCombatants()
})

watch(() => props.sceneImageUrl, () => {
  void syncBackdrop()
})

watch(() => props.combat?.round, (newRound, oldRound) => {
  if (newRound && newRound !== oldRound && stage && isPixiReady.value) {
    stage.showArcadeBanner(`ROUND ${newRound}`, 'FIGHT!')
  }
})

onMounted(async () => {
  const host = canvasHostRef.value
  if (!host) return

  try {
    app = new Application()
    await app.init({
      resizeTo: host,
      backgroundAlpha: 0,
      antialias: true,
      autoDensity: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
    })

    host.appendChild(app.canvas)

    stage = new CombatStage()
    await stage.init(app)

    // Check reduced motion
    motionMediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    stage.prefersReducedMotion = motionMediaQuery.matches
    motionMediaQuery.addEventListener('change', (e) => {
      if (stage) stage.prefersReducedMotion = e.matches
    })

    // Animation ticker loop
    app.ticker.add((ticker) => {
      stage?.update(ticker)
    })

    // Resize handling
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect
        if (width > 0 && height > 0) {
          stage?.resize(width, height)
        }
      }
    })
    resizeObserver.observe(host)

    isPixiReady.value = true
    await syncCombatants()
    await syncBackdrop()

    if (props.combat?.round) {
      stage.showArcadeBanner(`ROUND ${props.combat.round}`, 'FIGHT!')
    }

    emit('ready')
  } catch (err) {
    console.error('[CombatArenaPixi] Failed to initialize PixiJS combat stage:', err)
  }
})

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (stage) {
    stage.destroy()
    stage = null
  }
  if (app) {
    try {
      app.destroy(true, { children: true, texture: false, context: true })
    } catch (e) {
      console.warn('[CombatArenaPixi] Error during app destroy:', e)
    }
    app = null
  }
})
</script>

<template>
  <div class="relative w-full h-full min-h-[220px] rounded-xl overflow-hidden bg-slate-950/80 border border-amber-500/20 shadow-[0_0_30px_rgba(0,0,0,0.6),inset_0_1px_0_rgba(251,191,36,0.1)] flex items-center justify-center">
    <!-- PixiJS Canvas Host -->
    <div ref="canvasHostRef" class="w-full h-full absolute inset-0"></div>

    <!-- Loading Fallback before Pixi attaches -->
    <div v-if="!isPixiReady" class="text-xs text-amber-300/60 uppercase tracking-widest flex items-center gap-2">
      <i class="ra ra-crossed-swords animate-spin"></i>
      Initializing Combat Arena...
    </div>
  </div>
</template>

<style scoped>
canvas {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
