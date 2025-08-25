<template>
  <div class="space-y-4">
    <!-- 회사 선택 -->
    <div>
      <label class="mb-1 block text-sm font-medium">회사</label>
      <select
        class="w-full rounded border px-3 py-2"
        v-model="companyCode"
        :disabled="catalog.loadingCompanies"
      >
        <option value="" disabled>회사를 선택하세요</option>
        <option v-for="c in catalog.companies" :key="c.company_code" :value="c.company_code">
          {{ c.company_name }}
        </option>
      </select>
      <p v-if="catalog.errorCompanies" class="mt-1 text-xs text-red-600">{{ catalog.errorCompanies }}</p>
    </div>

    <!-- 직무 선택 -->
    <div>
      <label class="mb-1 block text-sm font-medium">직무</label>
      <select
        class="w-full rounded border px-3 py-2"
        v-model="jobCode"
        :disabled="!companyCode || catalog.loadingJobs"
      >
        <option value="" disabled>직무를 선택하세요</option>
        <option v-for="j in catalog.jobs" :key="j.job_code" :value="j.job_code">
          {{ j.job_name }}
        </option>
      </select>
      <p v-if="catalog.errorJobs" class="mt-1 text-xs text-red-600">{{ catalog.errorJobs }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useCatalogStore } from '@/store/catalog'

const catalog = useCatalogStore()

const companyCode = ref(catalog.selectedCompany?.company_code || '')
const jobCode = ref(catalog.selectedJob?.job_code || '')

onMounted(async () => {
  if (!catalog.companies.length && !catalog.loadingCompanies) {
    await catalog.loadCompanies() // => backend.ts API 호출
  }
  // 회사가 이미 선택돼 있으면 해당 회사의 직무 로드
  if (companyCode.value) {
    const foundC = catalog.companies.find(c => c.company_code === companyCode.value) || null
    catalog.chooseCompany(foundC) // 내부에서 loadJobs 호출
  }
})

// 회사 선택 변경 → store 선택 + 해당 회사 직무 로드
watch(companyCode, async (cc) => {
  const found = catalog.companies.find(c => c.company_code === cc) || null
  catalog.chooseCompany(found) // 내부에서 loadJobs 호출 (backend.ts 사용)
  jobCode.value = ''
})

// 직무 선택 변경 → store 선택만
watch(jobCode, (jc) => {
  const found = catalog.jobs.find(j => j.job_code === jc) || null
  catalog.chooseJob(found)
})
</script>
