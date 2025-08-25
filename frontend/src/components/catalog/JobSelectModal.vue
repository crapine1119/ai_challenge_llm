<template>
  <div v-if="ui.jobModalOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
    <div class="w-full max-w-md rounded-lg bg-white p-4 shadow-lg">
      <div class="mb-3 flex items-center justify-between">
        <h3 class="text-lg font-semibold">직무 선택</h3>
        <button class="text-gray-500 hover:text-black" @click="ui.closeJobModal()">✕</button>
      </div>

      <div class="space-y-3">
        <div>
          <label class="block text-xs text-gray-600 mb-1">회사 코드</label>
          <input v-model="company_code" class="w-full rounded border px-3 py-2" placeholder="예: 1000187" />
        </div>
        <div>
          <label class="block text-xs text-gray-600 mb-1">직무 코드</label>
          <input v-model="job_code" class="w-full rounded border px-3 py-2" placeholder="예: 1000242" />
        </div>
      </div>

      <div class="mt-4 flex justify-end gap-2">
        <button class="rounded border px-3 py-2 hover:bg-gray-50" @click="ui.closeJobModal()">취소</button>
        <button
          class="rounded bg-black px-3 py-2 text-white hover:bg-gray-800 disabled:opacity-50"
          :disabled="!company_code || !job_code"
          @click="apply"
        >적용</button>
      </div>

      <p class="mt-3 text-xs text-gray-500">
        * 라벨(회사/직무명)은 서버에서 가져오지 못하면 코드로 표기합니다.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useUIStore } from '@/store/ui'
import { useCatalogStore } from '@/store/catalog'
import { useRoute, useRouter } from 'vue-router'

const ui = useUIStore()
const catalog = useCatalogStore()
const route = useRoute()
const router = useRouter()

const company_code = ref(catalog.companyCode)
const job_code = ref(catalog.jobCode)

function apply() {
  // 라벨은 코드로 폴백
  catalog.setSelection(
    { company_code: company_code.value, label: catalog.companyLabel || company_code.value },
    { job_code: job_code.value,         label: catalog.jobLabel || job_code.value },
  )

  // 쿼리 동기화
  router.replace({
    query: {
      ...route.query,
      company_code: company_code.value,
      job_code: job_code.value,
    },
  })

  ui.closeJobModal()
}
</script>
