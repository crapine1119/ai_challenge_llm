<template>
  <div class="min-h-screen bg-gray-50 text-gray-900">
    <AppHeader />

    <!-- 선택 완료 전 메인 인터랙션만 잠금(헤더는 열림) -->
    <main
      class="mx-auto max-w-7xl px-4 py-6 transition"
      :class="!ready ? 'pointer-events-none opacity-40' : ''"
    >
      <RouterView />
    </main>

    <!-- 전역 선택 모달 -->
    <ChangeJobModal />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppHeader from '@/components/common/AppHeader.vue'
import ChangeJobModal from '@/components/search/ChangeJobModal.vue'
import { useCatalogStore } from '@/store/catalog'
import { useUIStore } from '@/store/ui'

const route = useRoute()
const router = useRouter()
const catalog = useCatalogStore()
const ui = useUIStore()

const ready = computed(() => catalog.ready)

function forceOpen() {
  ui.openJobModal({ requireDifferentJob: false })
}

onMounted(() => {
  // 1) **모달을 먼저 띄움** (선택이 없는 경우 즉시 표시)
  if (!catalog.ready) {
    ui.openJobModal({ requireDifferentJob: false })
  }

  // 2) 비동기로 선택 복원 (URL 쿼리 → localStorage)
  ;(async () => {
    try {
      await catalog.initFromCodes(
        route.query.company_code as string | undefined,
        route.query.job_code as string | undefined
      )
    } catch (e) {
      // 복원 실패해도 UI는 모달에서 수동 선택 가능
      console.error('initFromCodes failed:', e)
    } finally {
      // 복원 완료 후 쿼리 동기화
      const q: any = { ...route.query }
      const cc = catalog.selectedCompany?.company_code || ''
      const jc = catalog.selectedJob?.job_code || ''
      if (cc) q.company_code = cc; else delete q.company_code
      if (jc) q.job_code = jc; else delete q.job_code
      const same = String(route.query.company_code || '') === (q.company_code || '')
        && String(route.query.job_code || '') === (q.job_code || '')
      if (!same) router.replace({ query: q })

      // 선택이 끝났다면 모달 닫기
      if (catalog.ready) ui.closeJobModal()
      ui.setBootChecked(true)
    }
  })()
})
</script>
