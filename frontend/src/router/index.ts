import { createRouter, createWebHistory } from 'vue-router'
import PortalView from '@/views/PortalView.vue'
import AdminView from '@/views/AdminView.vue'
import CharacterCreateView from '@/views/CharacterCreateView.vue'
import GameView from '@/views/GameView.vue'

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
      path: '/characters/create',
      name: 'character-create',
      component: CharacterCreateView,
    },
    {
      path: '/game/:id',
      name: 'game',
      component: GameView,
      // Pass the route params as props to the component easily
      props: true, 
    },
  ],
})

export default router
