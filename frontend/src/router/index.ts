import { createRouter, createWebHistory } from 'vue-router'
import { authState } from '@/store/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'portal',
      component: () => import('@/views/PortalView.vue'),
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
    },
    {
      path: '/adventures/new',
      name: 'adventure-create',
      component: () => import('@/views/CreateAdventureView.vue'),
    },
    {
      path: '/game/:id',
      name: 'game',
      component: () => import('@/views/GameView.vue'),
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
      component: () => import('@/views/LoginView.vue'),
    },
    {
      path: '/setup',
      name: 'setup',
      component: () => import('@/views/SetupView.vue'),
    },
    {
      path: '/error',
      name: 'error',
      component: () => import('@/views/ErrorView.vue'),
    },
  ],
})

router.beforeEach(async (to, _from, next) => {
  // If we're not initialized yet, we don't know the auth state or if setup is needed.
  // We allow the navigation to proceed, and App.vue will handle the final redirection
  // once the bootstrap status is known.
  if (!authState.isInitialized) {
    if (to.name === 'login' || to.name === 'setup' || to.name === 'error') {
      return next()
    }
    // Continue navigation; App.vue will redirect if necessary after init.
    return next()
  }

  if (to.name === 'login' || to.name === 'setup' || to.name === 'error') {
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

