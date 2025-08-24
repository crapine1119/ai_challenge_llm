export const routes = [
  { path: '/', name: 'home', component: () => import('@/pages/Home.vue') },
  { path: '/generate/realtime', name: 'generate-realtime', component: () => import('@/pages/GenerateRealtime.vue') },
  { path: '/generate/wait', name: 'wait-hub', component: () => import('@/pages/WaitHub.vue') },
  { path: '/generate/board', name: 'board', component: () => import('@/pages/Board.vue') },
  { path: '/generate/stats', name: 'dashboard', component: () => import('@/pages/Dashboard.vue') },
  { path: '/collect', name: 'collect', component: () => import('@/pages/CrawlAdd.vue') }
]
