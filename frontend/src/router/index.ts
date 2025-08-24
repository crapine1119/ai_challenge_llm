// src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import { routes } from './routes'

const router = createRouter({
  // Vite 권장: BASE_URL 반영
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

// 라우터 에러 로깅(하얀 화면 원인 추적에 도움)
router.onError((err) => {
  console.error('[router error]', err)
})

export default router
