<template>
  <section class="space-y-8">
    <!-- 상단 선택 UI 제거됨 -->

    <!-- 홈 카드 3종 복구: 분석 / 실시간 생성 / 크롤링 -->
    <div class="grid gap-6 md:grid-cols-3">
      <!-- 직무 분석하기 -->
      <AppCard title="1. 직무 분석하기" badge="일배치">
        <p class="text-sm text-gray-600">
          과거 채용공고를 기준으로 회사 JD 스타일을 추출합니다.
          전날 배치 기준으로 생성하는 것을 가정하며, 사전 생성된 내용을 기반으로<br>
          사용자 경험을 극대화하고, LLM service의 단점을 상쇄하는 것이 목표입니다.
        </p>
        <div class="mt-4 flex gap-3">
          <AppButton @click="goDashboard">바로 보기</AppButton>
        </div>
      </AppCard>

      <!-- 실시간 JD 생성하기 (복구됨) -->
      <AppCard title="실시간 JD 생성하기" badge="스트리밍">
        <p class="text-sm text-gray-600">
          사전에 생성 JD를 Streaming으로 보여줌으로써<br>
          사용자가 실시간 생성 서비스라고 느끼도록 도와줍니다.<br>
          (TODO: Streaming 및 JD 수정)
        </p>
        <div class="mt-4">
          <AppButton @click="goGenerate">지금 생성</AppButton>
        </div>
        <p class="mt-2 text-xs text-gray-500">
          회사·직무는 우측 상단 <b>“직무 변경”</b> 버튼에서 언제든 선택할 수 있어요.
        </p>
      </AppCard>

      <!-- 직무 추가하기 -->
      <AppCard title="직무 추가하기" badge="크롤링">
        <p class="text-sm text-gray-600">
          회사/직무 코드로 데이터를 수집해 DB에 반영합니다.
        </p>
        <div class="mt-4">
          <AppButton @click="goCollect">직무 추가</AppButton>
        </div>
      </AppCard>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import AppCard from '@/components/common/AppCard.vue'
import AppButton from '@/components/common/AppButton.vue'

const router = useRouter()

function goGenerate() {
  // 회사/직무 선택은 헤더의 "직무 변경" 모달에서 처리 (초기 진입 시 자동 오픈)
  router.push({ name: 'generate-realtime' })
}
function goDashboard() {
  router.push({ name: 'dashboard' })
}
function goCollect() {
  router.push({ name: 'collect' })
}
</script>
