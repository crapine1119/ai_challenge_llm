<!-- src/pages/WaitHub.vue -->
<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div class="text-sm text-gray-600">
        진행 상태: <span class="font-medium">{{ statusLabel }}</span>
        <span v-if="etaStr" class="ml-2">· ETA {{ etaStr }}</span>
      </div>
      <div class="flex gap-2">
        <AppButton variant="secondary" @click="goBack">편집기로 돌아가기</AppButton>
        <AppButton variant="ghost" @click="toggleAuto">{{ autoBack ? '자동 복귀 ON' : '자동 복귀 OFF' }}</AppButton>
      </div>
    </div>

    <div v-if="toast" class="rounded bg-emerald-50 px-3 py-2 text-emerald-800">
      초안이 준비되기 시작했습니다.
      <AppButton size="sm" class="ml-2" @click="goBack">지금 보기</AppButton>
      <AppButton size="sm" variant="ghost" class="ml-1" @click="stay">여기 머무르기</AppButton>
    </div>

    <!-- 간단 탭 대체: 4개 카드 섹션 -->
    <div class="grid gap-4 md:grid-cols-2">
      <AppCard title="실시간 채용시장"> <!-- TODO: API 연동 --> </AppCard>
      <AppCard title="인기 공고·댓글"> <!-- TODO: API 연동 --> </AppCard>
      <AppCard title="리플레이·레이더"> <!-- TODO: API 연동 --> </AppCard>
      <AppCard title="통계 미리보기">
        <div v-if="preview">
          <div>큐 위치: {{ preview.position ?? '-' }}</div>
          <div>TTFMC(ms): {{ preview.speed?.ttfmc_ms ?? '-' }}</div>
          <div>품질 경고: {{ preview.quality?.dei_flags ?? 0 }}</div>
        </div>
        <div v-else class="text-sm text-gray-500">불러오는 중…</div>
      </AppCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/common/AppButton.vue'
import AppCard from '@/components/common/AppCard.vue'
import { useGenerationStore } from '@/store/generation'
import { useDashStore } from '@/store/dash'

const router = useRouter()
const route = useRoute()
const gen = useGenerationStore()
const dash = useDashStore()

const toast = ref(false)
const autoBack = ref(true)

const statusLabel = computed(() => {
  switch (gen.status) {
    case 'starting': return '초안 대기 중'
    case 'streaming': return '생성 중'
    case 'refining': return '정밀화 중'
    case 'done': return '완료'
    case 'error': return '오류'
    default: return '대기'
  }
})

const preview = computed(() => dash.preview)
const etaStr = computed(() => {
  const s = preview.value?.eta_sec_p50
  if (!s && s !== 0) return ''
  const mm = Math.floor((s as number) / 60).toString().padStart(2, '0')
  const ss = Math.floor((s as number) % 60).toString().padStart(2, '0')
  return `${mm}:${ss}`
})

function goBack() { router.push({ name: 'generate-realtime' }) }
function stay() { toast.value = false }
function toggleAuto() { autoBack.value = !autoBack.value }

onMounted(() => {
  // request_id가 있으면 프리뷰 폴링
  const rid = (route.query.rid as string) || gen.requestId
  if (rid) dash.startPolling(rid, 2000)

  // 첫 토큰(= streaming) 감지 → 토스트 & 자동 복귀
  const unwatch = watch(() => gen.status, (s) => {
    if (s === 'streaming') {
      toast.value = true
      if (autoBack.value) setTimeout(() => goBack(), 2000)
    }
    if (s === 'done') toast.value = false
  }, { immediate: true })

  onUnmounted(() => {
    unwatch()
    dash.stopPolling()
  })
})
</script>
