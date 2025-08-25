<template>
  <section class="space-y-8">
    <!-- 홈 카드 3종: 분석 / 실시간 생성 / 크롤링 -->
    <div class="grid gap-6 md:grid-cols-3">
      <!-- 1. 직무 분석하기 -->
      <router-link :to="{ name: 'dashboard' }" class="block rounded-lg border bg-white p-4 hover:bg-gray-50">
        <h3 class="text-lg font-semibold">1. 직무 분석하기</h3>
        <p class="mt-2 text-sm text-gray-600">
          - 과거 채용공고를 기준으로 회사 JD 스타일을 추출합니다.<br>
          - 전날 배치 기준으로 생성(일배치)하여 Hallucination과 비용을 줄입니다.<br>
          - 사전 생성된 내용을 호출해 UX를 개선합니다.
        </p>
        <div class="mt-4">
          <span class="inline-block rounded bg-black px-3 py-2 text-sm text-white">바로 보기</span>
        </div>
      </router-link>

      <!-- 2. 실시간 JD 생성하기 -->
      <router-link :to="{ name: 'generate-realtime' }" class="block rounded-lg border bg-white p-4 hover:bg-gray-50">
        <h3 class="text-lg font-semibold">실시간 JD 생성하기</h3>
        <p class="mt-2 text-sm text-gray-600">
          사전에 생성된 JD를 스트리밍 연출로 보여주어 실시간처럼 느끼게 합니다.
        </p>
        <div class="mt-4">
          <span class="inline-block rounded border px-3 py-2 text-sm">지금 생성</span>
        </div>
        <p class="mt-2 text-xs text-gray-500">
          회사·직무는 우측 상단 <b>“직무 변경”</b>에서 선택합니다.
        </p>
      </router-link>

      <!-- 3. 직무 추가하기 -->
      <router-link :to="{ name: 'collect' }" class="block rounded-lg border bg-white p-4 hover:bg-gray-50">
        <h3 class="text-lg font-semibold">직무 추가하기</h3>
        <p class="mt-2 text-sm text-gray-600">
          회사/직무 코드로 데이터를 수집해 DB에 반영합니다.
        </p>
        <div class="mt-4">
          <span class="inline-block rounded border px-3 py-2 text-sm">직무 추가</span>
        </div>
      </router-link>
    </div>
  </section>
</template>

<script setup lang="ts">
// 홈에서는 어떤 스토어/실시간 컴포넌트도 import하지 않습니다.
// useRouter / AppButton 불필요 → 제거
</script>
