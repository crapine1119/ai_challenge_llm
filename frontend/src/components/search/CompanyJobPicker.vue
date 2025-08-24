<!-- src/components/search/CompanyJobPicker.vue -->
<template>
  <div class="grid gap-4 md:grid-cols-2">
    <!-- 회사 검색 -->
    <div>
      <label class="mb-1 block text-sm text-gray-700">회사 검색</label>
      <div class="relative">
        <input
          :value="cInput"
          @input="onCompanyInput(($event.target as HTMLInputElement).value)"
          placeholder="회사명 또는 company_code"
          class="w-full rounded border px-3 py-2"
        />
        <ul
          v-if="showCompanyList"
          class="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded border bg-white shadow"
        >
          <li
            v-for="c in catalog.cResults"
            :key="c.company_code"
            class="cursor-pointer px-3 py-2 hover:bg-gray-50"
            @click="selectCompany(c)"
          >
            <div class="font-medium">{{ c.name }}</div>
            <div class="text-xs text-gray-500">{{ c.company_code }}<span v-if="c.region"> · {{ c.region }}</span></div>
          </li>
          <li v-if="!catalog.loadingCompanies && catalog.cResults.length === 0" class="px-3 py-2 text-sm text-gray-500">
            결과가 없습니다.
          </li>
          <li v-if="catalog.loadingCompanies" class="px-3 py-2 text-sm text-gray-500">검색 중…</li>
        </ul>
      </div>
      <!-- 선택 뱃지 -->
      <p v-if="catalog.selectedCompany" class="mt-2 text-sm">
        선택됨: <span class="rounded bg-gray-100 px-2 py-0.5">{{ catalog.selectedCompany.name }} ({{catalog.selectedCompany.company_code}})</span>
      </p>
      <!-- 즐겨찾기 -->
      <div v-if="catalog.favorites.companies.length" class="mt-2 text-xs text-gray-500">
        최근 선택:
        <button
          v-for="c in catalog.favorites.companies"
          :key="c.company_code"
          class="ml-1 rounded border px-2 py-0.5 hover:bg-gray-50"
          @click="selectCompany(c)"
        >{{ c.name }}</button>
      </div>
    </div>

    <!-- 직무 검색 -->
    <div>
      <label class="mb-1 block text-sm text-gray-700">직무 검색</label>
      <div class="relative">
        <input
          :value="jInput"
          @input="onJobInput(($event.target as HTMLInputElement).value)"
          placeholder="직무명 또는 job_code"
          class="w-full rounded border px-3 py-2"
        />
        <ul
          v-if="showJobList"
          class="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded border bg-white shadow"
        >
          <li
            v-for="j in catalog.jResults"
            :key="j.job_code"
            class="cursor-pointer px-3 py-2 hover:bg-gray-50"
            @click="selectJob(j)"
          >
            <div class="font-medium">{{ j.name }}</div>
            <div class="text-xs text-gray-500">{{ j.job_code }}<span v-if="j.family"> · {{ j.family }}</span></div>
          </li>
          <li v-if="!catalog.loadingJobs && catalog.jResults.length === 0" class="px-3 py-2 text-sm text-gray-500">
            결과가 없습니다.
          </li>
          <li v-if="catalog.loadingJobs" class="px-3 py-2 text-sm text-gray-500">검색 중…</li>
        </ul>
      </div>
      <p v-if="catalog.selectedJob" class="mt-2 text-sm">
        선택됨: <span class="rounded bg-gray-100 px-2 py-0.5">{{ catalog.selectedJob.name }} ({{catalog.selectedJob.job_code}})</span>
      </p>
      <div v-if="catalog.favorites.jobs.length" class="mt-2 text-xs text-gray-500">
        최근 선택:
        <button
          v-for="j in catalog.favorites.jobs"
          :key="j.job_code"
          class="ml-1 rounded border px-2 py-0.5 hover:bg-gray-50"
          @click="selectJob(j)"
        >{{ j.name }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useCatalogStore } from '@/store/catalog'
import { useDebounce } from '@/composables/useDebounce'
import type { CompanyBrief, JobBrief } from '@/api/types'

const catalog = useCatalogStore()
const cInput = ref('')
const jInput = ref('')

const debouncedFindCompanies = useDebounce((q: string) => catalog.findCompanies(q), 250)
const debouncedFindJobs = useDebounce((q: string) => catalog.findJobs(q), 250)

function onCompanyInput(v: string) {
  cInput.value = v
  debouncedFindCompanies(v)
}
function onJobInput(v: string) {
  jInput.value = v
  debouncedFindJobs(v)
}

function selectCompany(c: CompanyBrief) {
  catalog.chooseCompany(c)
  catalog.addFavoriteCompany(c)
  cInput.value = `${c.name} (${c.company_code})`
}
function selectJob(j: JobBrief) {
  catalog.chooseJob(j)
  catalog.addFavoriteJob(j)
  jInput.value = `${j.name} (${j.job_code})`
}

const showCompanyList = computed(() => !!cInput.value && document.activeElement && (document.activeElement as HTMLElement).tagName === 'INPUT')
const showJobList = computed(() => !!jInput.value && document.activeElement && (document.activeElement as HTMLElement).tagName === 'INPUT')
</script>
