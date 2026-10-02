import { createRouter, createWebHistory } from 'vue-router'

import { useUserStore } from '@/store/user'

const routes = [
  {
    path: '/',
    name: 'Layout',
    component: () => import('../layout/index.vue'),
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach(async () => {
  const userStore = useUserStore()
  if (userStore.accessToken && !userStore.currentUser) {
    try {
      await userStore.hydrateCurrentUser()
    } catch {
      userStore.handleUnauthorized()
    }
  }
})

export default router
