import { createRouter, createWebHistory } from 'vue-router'
import PortalView from '@/views/PortalView.vue'
import AdminView from '@/views/AdminView.vue'
import CharactersView from '@/views/CharactersView.vue'
import CharacterEditorView from '@/views/CharacterEditorView.vue'
import GameView from '@/views/GameView.vue'
import CreateAdventureView from '@/views/CreateAdventureView.vue'
import LoginView from '@/views/LoginView.vue'
import SetupView from '@/views/SetupView.vue'
import { authState } from '@/store/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'portal',
      component: PortalView,
    },
    {
      path: '/admin',
      name: 'admin',
      component: AdminView,
    },
    {
      path: '/characters',
      name: 'characters',
      component: CharactersView,
    },
    {
      path: '/characters/create',
      name: 'character-create',
      component: CharacterEditorView,
    },
    {
      path: '/characters/:id/edit',
      name: 'character-edit',
      component: CharacterEditorView,
      props: true,
    },
    {
      path: '/adventures/new',
      name: 'adventure-create',
      component: CreateAdventureView,
    },
    {
      path: '/game/:id',
      name: 'game',
      component: GameView,
      // Pass the route params as props to the component easily
      props: true, 
    },
    {
      path: '/adventures/:adventureId/editor',
      name: 'adventure-editor',
      component: () => import('@/views/AdventureEditorView.vue'),
      props: true,
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
    },
    {
      path: '/setup',
      name: 'setup',
      component: SetupView,
    },
  ],
})

router.beforeEach(async (to, from, next) => {
  // Wait for initial auth check (performed in App.vue)
  if (!authState.isInitialized && to.name !== 'setup') {
    // Initial load: App.vue will handle the first getMe() call.
    // If we're already on a route, we just let it be until isInitialized is true.
  }

  if (to.name === 'login' || to.name === 'setup') {
    return next()
  }

  if (!authState.token) {
    return next({ name: 'login' })
  }

  if (to.name === 'admin' && authState.user?.role !== 'admin') {
    return next({ name: 'portal' })
  }

  next()
})

export default router
