<template>
  <div class="space-y-10">
    <!-- 상단: 현재 선택 요약 + 액션 -->
    <div class="space-y-6">
      <div class="flex items-start justify-between">
        <h1 class="text-2xl font-semibold">실시간 JD 생성</h1>
        <AppButton size="sm" :disabled="!canStart || running" @click="startNow">
          생성
        </AppButton>
      </div>

      <div class="rounded border bg-white p-3 text-sm text-gray-700">
        <div>
          회사: <span class="font-medium">{{ companyLabel || '—' }}</span>
          <span v-if="companyCode" class="ml-1 text-xs text-gray-500">({{ companyCode }})</span>
        </div>
        <div>
          직무: <span class="font-medium">{{ jobLabel || '—' }}</span>
          <span v-if="jobCode" class="ml-1 text-xs text-gray-500">({{ jobCode }})</span>
        </div>
      </div>
    </div>

    <!-- 섹션: 실시간 생성 JD -->
    <section class="space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-medium">
          JD 템플릿 ({{ companyLabel || companyCode || '—' }} · {{ jobLabel || jobCode || '—' }})
        </h2>
         <AppButton
           size="sm"
           variant="ghost"
           @click="refetchInstant"
           :disabled="!started || !companyCode || !jobCode"
         >
           다시 가져오기
         </AppButton>
      </div>

      <!-- 로딩 스켈레톤 -->
      <div v-if="latestLoading" class="grid gap-4 md:grid-cols-3">
        <div class="h-40 animate-pulse rounded-lg border bg-white"></div>
        <div class="h-40 animate-pulse rounded-lg border bg-white"></div>
        <div class="h-40 animate-pulse rounded-lg border bg-white"></div>
      </div>

      <!-- 카드들 -->
      <div v-else-if="latestVisible.length" class="grid gap-4 md:grid-cols-3">
          <JDStreamCard
            v-for="(it, idx) in latestVisible"
            :key="it.id"
            :item="it"
            :delay="idx * 250"
            :speed="24"
            :instant="instantRender"
          />
        </div>

      <!-- 빈 상태 -->
      <div v-else class="rounded-lg border bg-white p-6 text-center text-sm text-gray-600">
        실시간 생성된 JD가 아직 없습니다.
        <span class="ml-1">상단의 <b>생성</b> 버튼으로 시작하세요.</span>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '@/components/common/AppButton.vue'
import ProgressBar from '@/components/generation/ProgressBar.vue'
import JDStreamCard from '@/components/generation/JDStreamCard.vue'

import { useGenerationStore } from '@/store/generation'
import { useCatalogStore } from '@/store/catalog'

import { getLatestJDs } from '@/api/backend'
import type { JDListItem } from '@/api/types'

/* ---------------- 선택/스토어 ---------------- */
const route = useRoute()
const gen = useGenerationStore()
const catalog = useCatalogStore()

const qCompany = (route.query.company_code as string) || ''
const qJob = (route.query.job_code as string) || ''

const companyLabel = computed(() => catalog.companyLabel)
const jobLabel = computed(() => catalog.jobLabel)
const companyCode = computed(() => catalog.selectedCompany?.company_code || '')
const jobCode = computed(() => catalog.selectedJob?.job_code || '')
const canStart = computed(() => !!(companyCode.value && jobCode.value))

/* ---------------- 생성 상태 ---------------- */
const status = computed(() => gen.status)
const content = computed(() => gen.content)
const running = computed(() => gen.status === 'queue' || gen.status === 'streaming')

/* ---------------- 시작 여부 & 퍼시스트 키 ---------------- */
const started = ref(false)
const persistKey = computed(() => (companyCode.value && jobCode.value) ? `${companyCode.value}::${jobCode.value}` : '')
const LS_STARTED = (key: string) => `jd_started:${key}`
const LS_CONTENT = (key: string) => `jd_live_content:${key}`

/* ---------------- 실시간 생성 JD(사전 생성본) ---------------- */
const latestLoading = ref(false) // 초기 자동 로드 금지
const latestFetched = ref<JDListItem[]>([])
const latestVisible = ref<JDListItem[]>([])
const instantRender = ref(false) // true면 즉시 전체 출력

async function fetchLatest(opts?: { instant?: boolean }) {
  if (!started.value) return
  latestLoading.value = true
  latestVisible.value = []
  latestFetched.value = []
  instantRender.value = !!opts?.instant

  const list = await getLatestJDs({
    company_code: companyCode.value,
    job_code: jobCode.value,
    limit: 3
  })

  latestFetched.value = list
  latestLoading.value = false

  if (instantRender.value) {
    // 즉시 한 번에 렌더
    latestVisible.value = [...latestFetched.value]
    return
  }

  // 스트리밍 연출: 300ms 간격으로 하나씩 추가
  let i = 0
  const id = setInterval(() => {
    if (i < latestFetched.value.length) {
      latestVisible.value.push(latestFetched.value[i++])
    } else {
      clearInterval(id)
    }
  }, 0)
}

/* ---------------- 시작 액션 ---------------- */
function startNow() {
  if (!canStart.value || running.value) return
  started.value = true
  // 시작 플래그를 저장(복원용)
  if (persistKey.value) localStorage.setItem(LS_STARTED(persistKey.value), '1')

  // 시작과 동시에 사전 생성본을 스트리밍처럼 노출
  fetchLatest({ instant: false })

  // 생성 스타일 우선 → 실패 시 기본('일반적')로 폴백
  try {
    gen.startGenerate({
      provider: 'openai',
      model: 'gpt-4o-mini',
      language: 'ko',
      company_code: companyCode.value,
      job_code: jobCode.value,
      style_source: 'generated'
    })
  } catch {
    gen.startGenerate({
      provider: 'openai',
      model: 'gpt-4o-mini',
      language: 'ko',
      company_code: companyCode.value,
      job_code: jobCode.value,
      style_source: 'default',
      default_style_name: '일반적'
    })
  }
}

/* ---------------- 재조회 버튼: 카드 없으면 즉시, 있으면 스트리밍 ---------------- */
async function refetchInstant() {
  await fetchLatest({ instant: true })
}

/* ---------------- 퍼시스트(페이지 이탈 후 복원) ---------------- */
// content를 회사·직무 키로 저장(마크다운 전문 유지)
watch(content, (md) => {
  if (!persistKey.value || !started.value) return
  localStorage.setItem(LS_CONTENT(persistKey.value), JSON.stringify({
    markdown: md || '',
    company_code: companyCode.value,
    job_code: jobCode.value,
    created_at: new Date().toISOString()
  }))
})

// 진입 시: 이전 세션에 시작 이력이 있고 저장된 마크다운이 있으면 카드로 복원
function hydrateFromPersisted() {
  if (!persistKey.value) return
  const wasStarted = localStorage.getItem(LS_STARTED(persistKey.value)) === '1'
  if (!wasStarted) return

  const raw = localStorage.getItem(LS_CONTENT(persistKey.value))
  if (!raw) { started.value = true; return } // 시작 이력만 남았을 수도 있음

  try {
    const saved = JSON.parse(raw) as { markdown: string; company_code: string; job_code: string; created_at: string }
    if (saved?.markdown) {
      started.value = true
      latestVisible.value = [{
        id: -Date.now(), // 로컬 복원용 가짜 ID
        company_code: saved.company_code,
        job_code: saved.job_code,
        title: '이전 세션에서 생성됨',
        markdown: saved.markdown,
        created_at: saved.created_at || new Date().toISOString()
      }]
      latestLoading.value = false
      instantRender.value = true // 복원 시 즉시 출력
    }
  } catch { /* noop */ }
}

/* ---------------- 라이프사이클 ---------------- */
onMounted(async () => {
  await catalog.initFromCodes(qCompany, qJob)
  // 자동 fetch 금지. 대신 과거 세션 내용이 있으면 복원만 수행.
  hydrateFromPersisted()
})

// 회사/직무 변경 시: 시작 이력이 있으면 해당 키 기준으로 복원 또는 재조회
watch([companyCode, jobCode], async ([c, j], [pc, pj]) => {
  if (c && j && (c !== pc || j !== pj)) {
    latestVisible.value = []
    latestFetched.value = []
    latestLoading.value = false
    started.value = false
    hydrateFromPersisted()
  }
})
</script>
