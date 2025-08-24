<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div class="text-sm text-gray-600">
        진행 상태: <span class="font-medium">{{ statusLabel }}</span>
        <span v-if="eta" class="ml-2">· ETA {{ eta }}</span>
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

    <AppTabs>
      <!-- 탭 ① 실시간 채용시장 -->
      <template #tab-1>실시간 채용시장</template>
      <template #panel-1>
        <div class="grid gap-4 md:grid-cols-3">
          <AppCard title="수급지수"> <!-- PLACEHOLDER 카드 --> </AppCard>
          <AppCard title="급등 스킬"> <!-- PLACEHOLDER 카드 --> </AppCard>
          <AppCard title="제목 길이 권장"> <!-- PLACEHOLDER 카드 --> </AppCard>
        </div>
      </template>

      <!-- 탭 ② 인기 공고·댓글 -->
      <template #tab-2>인기 공고·댓글</template>
      <template #panel-2>
        <AppCard title="Top 공고 미리보기"> <!-- PLACEHOLDER --> </AppCard>
      </template>

      <!-- 탭 ③ 리플레이·레이더 -->
      <template #tab-3>리플레이·레이더</template>
      <template #panel-3>
        <AppCard title="과거 성과 리플레이"> <!-- PLACEHOLDER --> </AppCard>
      </template>

      <!-- 탭 ④ 통계 미리보기 -->
      <template #tab-4>통계 미리보기</template>
      <template #panel-4>
        <AppCard title="큐/ETA/품질 요약"> <!-- PLACEHOLDER --> </AppCard>
      </template>
    </AppTabs>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppButton from '@/components/common/AppButton.vue'
import AppTabs from '@/components/common/AppTabs.vue'
import AppCard from '@/components/common/AppCard.vue'
import { useGenerationStore } from '@/store/generation'

const router = useRouter()
const gen = useGenerationStore()

const toast = ref(false)
const autoBack = ref(true)
const eta = ref<string | null>(null)

const statusLabel = computedStatus()

function computedStatus() {
  return computed(() => {
    switch (gen.status) {
      case 'starting': return '초안 대기 중'
      case 'streaming': return '생성 중'
      case 'refining': return '정밀화 중'
      case 'done': return '완료'
      case 'error': return '오류'
      default: return '대기'
    }
  })
}

function goBack() { router.push({ name: 'generate-realtime' }) }
function stay() { toast.value = false }
function toggleAuto() { autoBack.value = !autoBack.value }

onMounted(() => {
  // “첫 토큰 도착”을 감지: generation.status가 streaming으로 바뀌는 순간
  const unwatch = watch(() => gen.status, (s) => {
    if (s === 'streaming') {
      toast.value = true
      if (autoBack.value) {
        setTimeout(() => goBack(), 2000)
      }
    }
    if (s === 'done') toast.value = false
  }, { immediate: true })
  // (선택) ETA 폴링은 /dash/jd/preview로 구현 가능
})
</script>
