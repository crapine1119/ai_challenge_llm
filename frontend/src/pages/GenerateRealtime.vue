<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-semibold">실시간 JD 생성</h1>

    <!-- 현재 선택 표시: '이름' 우선 -->
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

    <!-- 템플릿 섹션 헤더 & 액션 -->
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-medium">추천 템플릿</h2>
      <div class="flex gap-2">
        <AppButton size="sm" variant="ghost" @click="reloadTemplates">템플릿 다시 불러오기</AppButton>
        <!-- 전역 CTA: 템플릿이 비어도 생성 시작 가능 -->
        <AppButton size="sm" variant="secondary" @click="startGenerated" :disabled="!canStart">
          Generated 스타일로 바로 시작
        </AppButton>
        <AppButton size="sm" @click="startDefault" :disabled="!canStart">
          기본(일반적) 스타일로 시작
        </AppButton>
      </div>
    </div>

    <!-- ① 로딩 스켈레톤 -->
    <div v-if="loading" class="grid gap-4 md:grid-cols-2">
      <div class="h-32 animate-pulse rounded-lg border bg-white"></div>
      <div class="h-32 animate-pulse rounded-lg border bg-white"></div>
    </div>

    <!-- ② 템플릿 카드 -->
    <div v-else-if="visibleTemplates.length" class="grid gap-4 md:grid-cols-2">
      <TemplateStreamCard
        v-for="(t, idx) in visibleTemplates"
        :key="t.id"
        :template="t"
        :delay="idx * 250"
        :speed="16"
        @select="startWith(t)"
        @preview="preview(t)"
      />
    </div>

    <!-- ③ 빈 상태: 버튼이 사라지지 않도록 명확한 CTA 제공 -->
    <div v-else class="rounded-lg border bg-white p-6 text-center text-sm">
      <p class="text-gray-700">표시할 템플릿이 없습니다.</p>
      <div class="mt-3 flex flex-wrap items-center justify-center gap-2">
        <AppButton size="sm" variant="ghost" @click="reloadTemplates">템플릿 다시 불러오기</AppButton>
        <AppButton size="sm" variant="secondary" @click="startGenerated" :disabled="!canStart">
          Generated 스타일로 바로 시작
        </AppButton>
        <AppButton size="sm" @click="startDefault" :disabled="!canStart">
          기본(일반적) 스타일로 시작
        </AppButton>
      </div>
      <p v-if="!canStart" class="mt-2 text-xs text-amber-600">
        우측 상단 <b>직무 변경</b>에서 회사·직무를 선택해주세요.
      </p>
    </div>

    <!-- 진행 상태 & 실시간 미리보기 -->
    <ProgressBar v-if="status !== 'idle'" :status="status" />
    <section v-if="content" class="rounded-lg border bg-white p-4 shadow-sm">
      <h2 class="mb-2 font-medium">실시간 생성 미리보기</h2>
      <pre class="whitespace-pre-wrap">{{ content }}</pre>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '@/components/common/AppButton.vue'
import TemplateStreamCard from '@/components/generation/TemplateStreamCard.vue'
import ProgressBar from '@/components/generation/ProgressBar.vue'
import { useGenerationStore } from '@/store/generation'
import { useCatalogStore } from '@/store/catalog'
import { getJDTemplates } from '@/api/backend'
import type { JDTemplate } from '@/api/types'

const route = useRoute()
const gen = useGenerationStore()
const catalog = useCatalogStore()

// 쿼리 우선 복원
const qCompany = (route.query.company_code as string) || ''
const qJob = (route.query.job_code as string) || ''

// 표시용
const companyLabel = computed(() => catalog.companyLabel)
const jobLabel = computed(() => catalog.jobLabel)
const companyCode = computed(() => catalog.selectedCompany?.company_code || '')
const jobCode = computed(() => catalog.selectedJob?.job_code || '')
const canStart = computed(() => !!(companyCode.value && jobCode.value))

// 생성 상태
const status = computed(() => gen.status)
const content = computed(() => gen.content)

// 템플릿 로딩
const loading = ref(true)
const fetchedTemplates = ref<JDTemplate[]>([])
const visibleTemplates = ref<JDTemplate[]>([])

async function fetchTemplates() {
  loading.value = true
  visibleTemplates.value = []
  fetchedTemplates.value = await getJDTemplates({
    company_code: companyCode.value,
    job_code: jobCode.value,
    limit: 4
  })
  loading.value = false

  // 스트리밍처럼 하나씩 등장
  let i = 0
  const id = setInterval(() => {
    if (i < fetchedTemplates.value.length) {
      visibleTemplates.value.push(fetchedTemplates.value[i++])
    } else {
      clearInterval(id)
    }
  }, 350)
}

function reloadTemplates() {
  fetchTemplates().catch(() => {})
}

onMounted(async () => {
  // 선택 복원
  await catalog.initFromCodes(qCompany, qJob)
  // 템플릿 로드
  await fetchTemplates()
})

// 시작 함수들
function startWith(t: JDTemplate) {
  if (!canStart.value) return
  gen.startGenerate({
    provider: 'openai',
    model: 'gpt-4o-mini',
    language: 'ko',
    company_code: companyCode.value,
    job_code: jobCode.value,
    style_source: t.source === 'preset' ? 'default' : 'generated',
    default_style_name: t.source === 'preset' ? t.name : undefined
  })
}
function startGenerated() {
  if (!canStart.value) return
  gen.startGenerate({
    provider: 'openai',
    model: 'gpt-4o-mini',
    language: 'ko',
    company_code: companyCode.value,
    job_code: jobCode.value,
    style_source: 'generated'
  })
}
function startDefault() {
  if (!canStart.value) return
  gen.startGenerate({
    provider: 'openai',
    model: 'gpt-4o-mini',
    language: 'ko',
    company_code: companyCode.value,
    job_code: jobCode.value,
    style_source: 'default',
    default_style_name: '일반적' // 필요시 'Notion' 등으로 교체
  })
}

// 옵션: 미리보기 모달 등
function preview(t: JDTemplate) {
  // eslint-disable-next-line no-console
  console.log('preview template', t)
}
</script>
