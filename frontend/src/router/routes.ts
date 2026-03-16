import type { RouteRecordRaw } from 'vue-router'
import ChatPage from '@/pages/ChatPage.vue'

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'chat',
    component: ChatPage,
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/pages/SettingsPage.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'notfound',
    component: () => import('@/pages/NotFoundPage.vue'),
  },
]
