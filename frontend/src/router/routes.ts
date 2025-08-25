// src/router/routes.ts
import type { RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: () => import('@/pages/Home.vue') },
  { path: '/generate/realtime', name: 'generate-realtime', component: () => import('@/pages/GenerateRealtime.vue') },
  { path: '/generate/wait', name: 'wait-hub', component: () => import('@/pages/WaitHub.vue') },
  { path: '/generate/board', name: 'board', component: () => import('@/pages/Board.vue') },
  { path: '/collect', name: 'collect', component: () => import('@/pages/CrawlAdd.vue') },
  { path: '/analyze', name: 'dashboard', component: () => import('@/pages/AnalyzeJob.vue') },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/pages/NotFound.vue') },
  { path: '/collect', name: 'collect', component: () => import('@/pages/Collect.vue') }
]

// (원래 index.ts에서 `import { routes } from './routes'` 형태를 쓰고 있으므로 named export 유지)
export default routes
