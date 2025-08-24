<!-- src/components/search/CompanyJobSelect.vue -->
<template>
  <div class="grid gap-4 md:grid-cols-2">
    <!-- 회사 선택 -->
    <div>
      <label class="mb-1 block text-sm text-gray-700">회사 선택</label>
      <select
        class="w-full rounded border px-3 py-2"
        :disabled="catalog.loadingCompanies"
        :value="companyCode"
        @focus="onCompaniesFocus"
        @change="onCompanyChange(($event.target as HTMLSelectElement).value)"
      >
        <!-- selected 제거, v-bind value에 위임 -->
        <option :value="''" disabled>회사를 선택하세요</option>
        <option v-for="c in catalog.companies" :key="c.company_code" :value="c.company_code">
          {{ c.name || c.company_code }} ({{ c.company_code }})
        </option>
      </select>

      <p v-if="catalog.loadingCompanies" class="mt-1 text-xs text-gray-500">회사 목록 불러오는 중…</p>
      <div v-else-if="catalog.errorCompanies" class="mt-1 flex items-center gap-2 text-xs text-amber-700">
        {{ catalog.errorCompanies }}
        <button class="rounded border px-2 py-0.5 hover:bg-gray-50" @click="catalog.loadCompanies()">재시도</button>
      </div>
      <p v-else-if="!catalog.companies.length" class="mt-1 text-xs text-gray-500">표시할 회사가 없습니다.</p>
    </div>

    <!-- 직무 선택 -->
    <div>
      <label class="mb-1 block text-sm text-gray-700">직무 선택</label>
      <select
        class="w-full rounded border px-3 py-2"
        :disabled="!catalog.selectedCompany || catalog.loadingJobs"
        :value="jobCode"
        @focus="onJobsFocus"
        @change="onJobChange(($event.target as HTMLSelectElement).value)"
      >
        <option :value="''" disabled>직무를 선택하세요</option>
        <option v-for="j in catalog.jobs" :key="j.job_code" :value="j.job_code">
          {{ j.name }} ({{ j.job_code }})
        </option>
      </select>

      <p v-if="!catalog.selectedCompany" class="mt-1 text-xs text-gray-500">먼저 회사를 선택하세요.</p>
      <p v-else-if="catalog.loadingJobs" class="mt-1 text-xs text-gray-500">직무 목록 불러오는 중…</p>
      <div v-else-if="catalog.errorJobs" class="mt-1 flex items-center gap-2 text-xs text-amber-700">
        {{ catalog.errorJobs }}
        <button class="rounded border px-2 py-0.5 hover:bg-gray-50" @click="catalog.loadJobs(catalog.selectedCompany?.company_code)">재시도</button>
      </div>
      <p v-else-if="catalog.selectedCompany && !catalog.jobs.length" class="mt-1 text-xs text-gray-500">표시할 직무가 없습니다.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useCatalogStore } from '@/store/catalog'

const catalog = useCatalogStore()

onMounted(async () => {
  // 모달이 아주 빨리 뜨는 경우를 대비해 최초 마운트에도 로드
  await catalog.ensureLoaded()
})

const companyCode = computed(() => catalog.selectedCompany?.company_code || '')
const jobCode = computed(() => catalog.selectedJob?.job_code || '')

function onCompaniesFocus() {
  if (!catalog.companies.length && !catalog.loadingCompanies) catalog.loadCompanies()
}
function onJobsFocus() {
  if (catalog.selectedCompany && !catalog.jobs.length && !catalog.loadingJobs) {
    catalog.loadJobs(catalog.selectedCompany.company_code)
  }
}

function onCompanyChange(code: string) {
  const c = catalog.companies.find(x => x.company_code === code) || null
  catalog.chooseCompany(c)
}

function onJobChange(code: string) {
  const j = catalog.jobs.find(x => x.job_code === code) || null
  catalog.chooseJob(j)
}
</script>
