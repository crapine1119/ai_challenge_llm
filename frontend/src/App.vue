<template>
  <div class="min-h-screen bg-gray-50 text-gray-900">
    <AppHeader />
    <main class="mx-auto max-w-7xl px-4 py-6">
      <RouterView />
    </main>
    <AppFooter />

    <!-- 전역 모달 -->
    <JobSelectModal />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/common/AppHeader.vue'
import AppFooter from '@/components/common/AppFooter.vue'
import JobSelectModal from '@/components/catalog/JobSelectModal.vue'
import { useCatalogStore } from '@/store/catalog'
import { useUIStore } from '@/store/ui'

const route = useRoute()
const catalog = useCatalogStore()
const ui = useUIStore()

onMounted(async () => {
  // 1) 쿼리/로컬스토리지 복원
  await catalog.initFromCodes(
    route.query.company_code as string | undefined,
    route.query.job_code as string | undefined
  )
  // 2) 첫 진입 & 선택 없음 → 모달 오픈 (1회만)
  if (!catalog.canRun && !ui.bootChecked) {
    ui.openJobModal()
  }
  ui.setBootChecked(true)
})
</script>