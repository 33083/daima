import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/repos' },
  {
    path: '/repos',
    name: 'Repos',
    component: () => import('../views/Repos.vue'),
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('../views/Chat.vue'),
  },
  {
    path: '/architecture',
    name: 'Architecture',
    component: () => import('../views/Architecture.vue'),
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
