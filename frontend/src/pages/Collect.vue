<template>
  <div class="space-y-8">
    <div class="flex items-start justify-between">
      <h1 class="text-2xl font-semibold">직무 추가하기</h1>
      <AppButton size="sm" variant="ghost" @click="refreshAll">새로고침</AppButton>
    </div>

    <!-- 안내 -->
    <AppCard title="수집 설명" badge="크롤링">
      <p class="text-sm text-gray-600">
        회사/직무 코드를 입력하면 크롤링 서비스로 데이터를 수집하고 DB에 반영합니다. <br>
        잡코리아 백엔드를 연결하기 위해 임시로 구성한 내용입니다. <br>
        크롤링 규칙에 벗어나거나, 직무 정보가 없는 경우 실패할 수 있습니다.
        (현재 플랫폼: <b>jobkorea</b>)
      </p>
    </AppCard>

    <!-- 입력 폼 -->
    <AppCard title="수집 요청" badge="FORM">
      <form @submit.prevent="onSubmit" class="grid gap-4 md:grid-cols-4">
        <div class="md:col-span-1">
          <label class="mb-1 block text-xs text-gray-500">플랫폼</label>
          <input class="w-full rounded border px-3 py-2 text-sm bg-gray-50" value="jobkorea" disabled />
        </div>
        <div class="md:col-span-1">
          <label class="mb-1 block text-xs text-gray-500">회사 ID (number)</label>
          <input v-model.number="form.company_id" type="number" min="1" class="w-full rounded border px-3 py-2 text-sm" placeholder="예: 1517115" />
        </div>
        <div class="md:col-span-1">
          <label class="mb-1 block text-xs text-gray-500">직무 코드 (job_code)</label>
          <input v-model.trim="form.job_code" class="w-full rounded border px-3 py-2 text-sm" placeholder="예: 1000242" />
        </div>
        <!-- max_details 고정: 입력칸 제거 -->
        <div class="md:col-span-4 flex items-center gap-2">
          <AppButton :disabled="!canSubmit || loading" type="submit">
            {{ loading ? '수집 중...' : '수집 시작' }}
          </AppButton>
          <span v-if="error" class="text-xs text-red-600">{{ error }}</span>
        </div>
      </form>
    </AppCard>

    <!-- 응답/로그 -->
    <AppCard title="응답 로그" badge="RESULT">
      <div class="max-h-64 overflow-auto rounded border bg-gray-50 p-3 text-xs">
        <div v-if="!logs.length" class="text-gray-400">아직 로그가 없습니다. 수집을 실행해보세요.</div>
        <pre v-for="(l, i) in logs" :key="i" class="whitespace-pre-wrap">{{ l }}</pre>
      </div>
    </AppCard>

    <!-- DB 미리보기 -->
    <div class="grid gap-6 md:grid-cols-2">
      <AppCard title="수집된 회사 목록" badge="DB">
        <div class="mb-2 flex items-center justify-between">
          <div class="text-xs text-gray-500">총 {{ companies.length }}개</div>
          <AppButton size="sm" variant="ghost" @click="loadCompanies">새로고침</AppButton>
        </div>
        <ul class="divide-y rounded border bg-white">
          <li
            v-for="(c, idx) in companies"
            :key="idx"
            class="flex items-center justify-between px-3 py-2 text-sm"
          >
            <div>
              <span class="font-medium">{{ companyLabelOf(c) }}</span>
              <span class="ml-1 text-xs text-gray-500">({{ companyCodeOf(c) }})</span>
            </div>
            <AppButton size="xs" variant="ghost" @click="selectCompany(companyCodeOf(c))">
              직무 보기
            </AppButton>
          </li>
        </ul>
      </AppCard>

      <AppCard title="선택 회사의 직무 목록" badge="DB">
        <div class="mb-2 flex items-center justify-between">
          <div class="text-xs text-gray-500">
            회사:
            <span class="font-medium">{{ selectedCompany || '—' }}</span>
          </div>
          <div class="flex items-center gap-2">
            <input
              v-model.trim="jobFilter"
              class="rounded border px-2 py-1 text-xs"
              placeholder="필터 (이름/코드)"
            />
            <AppButton size="sm" variant="ghost" @click="loadJobs" :disabled="!selectedCompany">새로고침</AppButton>
          </div>
        </div>

        <ul class="divide-y rounded border bg-white max-h-80 overflow-auto">
          <li
            v-for="(j, idx) in filteredJobs"
            :key="idx"
            class="px-3 py-2 text-sm"
          >
            <div class="flex items-center justify-between">
              <div>
                <span class="font-medium">{{ j.name || j.title || j.code }}</span>
                <span class="ml-1 text-xs text-gray-500">({{ j.code || j.job_code }})</span>
              </div>
              <button
                class="rounded px-2 py-1 text-xs hover:bg-gray-100"
                @click="prefillFromJob(j)"
              >
                폼에 채우기
              </button>
            </div>
          </li>
        </ul>
      </AppCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import AppCard from '@/components/common/AppCard.vue'
import AppButton from '@/components/common/AppButton.vue'
import { collectJobkorea, getCollectedCompanies, getCollectedJobsForCompany } from '@/api/backend'
import type { CompanyBrief, JobBrief } from '@/api/types'

/** ------- 폼 상태 ------- */
const form = ref<{ company_id: number | null; job_code: string }>({
  company_id: null,
  job_code: '',
})
const loading = ref(false)
const error = ref<string | null>(null)
const logs = ref<string[]>([])

const canSubmit = computed(() => {
  return !!form.value.company_id && !!form.value.job_code
})

async function onSubmit() {
  if (!canSubmit.value || loading.value) return
  loading.value = true
  error.value = null
  try {
    const body = {
      company_id: Number(form.value.company_id),
      job_code: form.value.job_code.trim(),
      company_code: 'jobkorea',
    }
    ;(body as any).max_details = 3
    logs.value.push(`▶ 요청: ${JSON.stringify(body, null, 2)}`)
    const res = await collectJobkorea(body)
    logs.value.push(`✔ 응답: ${JSON.stringify(res, null, 2)}`)

    // 성공 후 목록 리프레시
    await refreshAll()
  } catch (e: any) {
    error.value = e?.message || '요청 실패'
    logs.value.push(`✖ 오류: ${error.value}`)
  } finally {
    loading.value = false
  }
}

/** ------- DB 미리보기 ------- */
const companies = ref<any[]>([])
const selectedCompany = ref<string>('') // company_code
const jobs = ref<any[]>([])
const jobFilter = ref('')

function companyCodeOf(c: any): string {
  return c?.company_code || c?.code || (typeof c === 'string' ? c : '')
}
function companyLabelOf(c: any): string {
  return c?.company_name || c?.name || companyCodeOf(c)
}

async function loadCompanies() {
  const list = await getCollectedCompanies(500)
  companies.value = list || []
  // 선택이 없으면 첫 항목 선택
  if (!selectedCompany.value && companies.value.length) {
    selectedCompany.value = companyCodeOf(companies.value[0])
    await loadJobs()
  }
}

async function loadJobs() {
  if (!selectedCompany.value) { jobs.value = []; return }
  const list = await getCollectedJobsForCompany(selectedCompany.value, 500)
  // API가 {jobs:[{code,name}]} or {items:[...]} or [...] 형태일 수 있어 유연 처리
  const arr = Array.isArray((list as any)?.jobs) ? (list as any).jobs
    : Array.isArray((list as any)?.items) ? (list as any).items
    : Array.isArray(list) ? list
    : []
  jobs.value = arr
}

function selectCompany(code: string) {
  selectedCompany.value = code
  loadJobs()
}

const filteredJobs = computed(() => {
  const q = jobFilter.value.trim().toLowerCase()
  if (!q) return jobs.value
  return jobs.value.filter((j: any) => {
    const name = (j.name || j.title || '').toString().toLowerCase()
    const code = (j.code || j.job_code || '').toString().toLowerCase()
    return name.includes(q) || code.includes(q)
  })
})

function prefillFromJob(j: any) {
  form.value.job_code = String(j.code || j.job_code || '').trim()
  // 회사 ID는 사용자가 알아야 하므로 유지. 필요 시 별도 조회로 매핑 가능.
}

async function refreshAll() {
  await loadCompanies()
  if (selectedCompany.value) await loadJobs()
}

onMounted(async () => {
  await refreshAll()
})
</script>
