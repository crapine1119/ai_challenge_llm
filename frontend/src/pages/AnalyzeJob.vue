<template>
  <div class="space-y-6">
    <!-- AnalyzeJob.vue 상단 헤더 교체 -->
    <div class="flex items-start justify-between">
      <h1 class="text-2xl font-semibold">직무 분석하기</h1>
      <div class="flex gap-2">
        <button
          class="rounded bg-black px-3 py-2 text-sm text-white hover:bg-gray-800 disabled:opacity-50"
          :disabled="!canRun || runningAnalysis || analyze.batchStatus==='running'"
          @click="onAnalyze"
        >
          분석하기
        </button>
        <button
          class="rounded border px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
          :disabled="!canRun || runningAnalysis || analyze.batchStatus==='running'"
          @click="onRefresh"
        >
          새로고침
        </button>
      </div>
    </div>

    <!-- 현재 선택 -->
    <div class="rounded border bg-white p-3 text-sm">
      <div>
        회사: <span class="font-medium">{{ companyLabel || '—' }}</span>
        <span v-if="companyCode" class="ml-1 text-xs text-gray-500">({{ companyCode }})</span>
      </div>
      <div>
        직무: <span class="font-medium">{{ jobLabel || '—' }}</span>
        <span v-if="jobCode" class="ml-1 text-xs text-gray-500">({{ jobCode }})</span>
      </div>
      <p v-if="!canRun" class="mt-2 text-xs text-amber-600">
        우측 상단 <b>직무 변경</b>에서 회사·직무를 먼저 선택해주세요.
      </p>
    </div>

    <!-- 스타일 4열 -->
    <div>
      <div class="mb-2 flex items-center justify-between">
        <h2 class="text-lg font-medium">스타일</h2>
        <span class="text-xs text-gray-500">기본 프리셋 3개 + 회사 스타일 1개</span>
      </div>

      <!-- 로딩 스켈레톤 -->
      <div v-if="loading" class="grid gap-4 md:grid-cols-4">
        <div class="h-40 animate-pulse rounded-lg border bg-white"></div>
        <div class="h-40 animate-pulse rounded-lg border bg-white"></div>
        <div class="h-40 animate-pulse rounded-lg border bg-white"></div>
        <div class="h-40 animate-pulse rounded-lg border bg-white"></div>
      </div>

      <!-- 카드 -->
      <div v-else class="grid gap-4 md:grid-cols-4">
      <!-- 프리셋 카드 -->
      <StyleCard
        v-for="(p, i) in topPresets"
        :key="`preset:${p.style?.style_label ?? 'unknown'}:${i}`"
        :title="p.style.style_label"
        badge="PRESET"
        :detail="p.style"
      />

      <!-- 회사 스타일 카드 -->
      <StyleCard
         :key="`gen:${companyCode}:${jobCode}:${companyStyle?.style?.style_label ?? 'none'}`"
         title="회사 스타일 최신"
         badge="GENERATED"
         :detail="companyStyle?.style || null"
      />
      </div>

      <p v-if="!loading && topPresets.length === 0" class="mt-2 text-xs text-amber-600">
        기본 프리셋을 불러오지 못했습니다. <button class="underline" @click="onRefresh">다시 시도</button>
      </p>
      <p v-if="!loading && !companyStyle" class="mt-1 text-xs text-gray-500">
        회사 스타일이 아직 생성되지 않았습니다. <b>분석하기</b>를 눌러 생성 후 새로고침 해보세요.
      </p>
    </div>

    <!-- JD Generation 결과 (분석하기 클릭 후 자동 실행) -->
    <div class="rounded-lg border bg-white p-4 shadow-sm">
      <div class="mb-2 flex items-center justify-between">
        <h3 class="font-medium">JD Generation 결과</h3>
        <span
          v-if="batchStatus !== 'idle'"
          class="rounded bg-gray-100 px-2 py-1 text-xs"
        >
          {{ batchStatusText }}
        </span>
      </div>

      <!-- 실행 로그 -->
      <div class="mb-3 max-h-40 overflow-auto rounded border bg-gray-50 p-2 text-xs text-gray-700">
        <div v-if="!batchLog.length" class="text-gray-400">분석 후 자동으로 생성이 실행됩니다…</div>
        <div v-for="(line, i) in batchLog" :key="i">{{ line }}</div>
      </div>

      <!-- 결과 목록 -->
      <div v-if="jdResults.length" class="grid gap-3">
        <details v-for="(r, i) in jdResults" :key="i" class="rounded border bg-white">
          <summary class="cursor-pointer px-3 py-2 text-sm">
            {{ r.label }} <span v-if="r.saved_id" class="ml-2 text-xs text-gray-500">(#{{ r.saved_id }})</span>
          </summary>
          <pre class="whitespace-pre-wrap p-3 text-xs">{{ r.markdown }}</pre>
        </details>
      </div>
    </div>

    <!-- (옵션) 분석 로그 토글 -->
    <details open @toggle="$event.target.open = true" class="rounded border bg-white p-3 text-xs text-gray-700">
      <summary class="cursor-pointer select-none text-sm font-medium">분석 로그</summary>
      <div class="mt-2 max-h-48 overflow-auto whitespace-pre-wrap">
        <div v-if="!analysisLog.length" class="text-gray-400">로그가 없습니다.</div>
        <div v-for="(line, i) in analysisLog" :key="i">{{ line }}</div>
      </div>
    </details>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useCatalogStore } from '@/store/catalog'
import { useAnalyzeStore } from '@/store/analyze'
import { useUIStore } from '@/store/ui'
import StyleCard from '@/components/analysis/StyleCard.vue'

const route = useRoute()
const ui = useUIStore()
const catalog = useCatalogStore()
const analyze = useAnalyzeStore()

// 선택 복원
const qCompany = (route.query.company_code as string) || ''
const qJob = (route.query.job_code as string) || ''

const companyCode = computed(() => catalog.selectedCompany?.company_code || '')
const jobCode = computed(() => catalog.selectedJob?.job_code || '')
const companyLabel = computed(() => catalog.companyLabel)
const jobLabel = computed(() => catalog.jobLabel)
const canRun = computed(() => !!(companyCode.value && jobCode.value))

// 스타일 섹션 상태
const loading = ref(true)
const topPresets = computed(() => (analyze.presets || []).slice(0, 3))
const companyStyle = computed(() => analyze.companyStyle)

// 분석 상태
const runningAnalysis = computed(() => analyze.zeroShotStatus === 'running' || analyze.analyzeAllStatus === 'running')
const analysisLog = computed(() => analyze.analysisLog)

// JD Generation 상태
const batchStatus = computed(() => analyze.batchStatus)
const runningBatch = computed(() => analyze.batchStatus === 'running')
const batchLog = computed(() => analyze.batchLog)
const jdResults = computed(() => analyze.jdResults)
const batchStatusText = computed(() => {
  switch (batchStatus.value) {
    case 'running': return '생성 중'
    case 'done': return '완료'
    case 'error': return '오류'
    default: return '대기'
  }
})

// 초기 로드
onMounted(async () => {
  await catalog.initFromCodes(qCompany, qJob)
  if (canRun.value) {
    await refreshStyles()
  } else {
    ui.openJobModal()
    loading.value = false
  }
})

// 선택 변경 시 자동 새로고침
watch([companyCode, jobCode], async ([c, j], [pc, pj]) => {
  if (c && j && (c !== pc || j !== pj)) {
    await refreshStyles()
  }
})

// 액션: 분석하기 = 회사 분석 → 스타일 리프레시 → JD Generation 자동 실행
async function onAnalyze() {
  if (!canRun.value || runningAnalysis.value || runningBatch.value) return
  try {
    await analyze.runCompanyAnalysis({ company_code: companyCode.value, job_code: jobCode.value })
  } finally {
    await refreshStyles()
    // 회사 스타일이 방금 생성/업데이트되었으므로, 사전 생성(기본 3종 + 회사 1종) 자동 실행
    await analyze.runPreBatch({ company_code: companyCode.value, job_code: jobCode.value })
  }
}

// 액션: 새로고침 = 스타일만 다시 가져오기 (생성은 실행 안 함)
async function onRefresh() {
  if (!canRun.value || runningAnalysis.value || runningBatch.value) return
  await refreshStyles()
}

// 내부: 스타일 새로고침
async function refreshStyles() {
  loading.value = true
  await analyze.loadStyles({ company_code: companyCode.value, job_code: jobCode.value })
  loading.value = false
}
</script>
