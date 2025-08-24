<template>
  <section class="grid gap-6 md:grid-cols-3">
    <AppCard title="직무 분석하기" badge="일배치">
      <p class="text-sm text-gray-600">어제 밤 배치 기준으로 과거 JD를 비교·요약합니다.</p>
      <div class="mt-4 flex gap-3">
        <AppButton @click="$router.push({ name: 'dashboard' })">바로 보기</AppButton>
        <AppButton variant="ghost">배치 실행</AppButton>
      </div>
    </AppCard>
    <AppCard title="실시간 JD 생성하기" badge="스트리밍">
      <p class="text-sm text-gray-600">초안을 즉시 보여주고 문장을 점진적으로 다듬습니다.</p>
      <div class="mt-4">
        <AppButton @click="$router.push({ name: 'generate-realtime' })">지금 생성</AppButton>
      </div>
    </AppCard>
    <AppCard title="직무 추가하기" badge="크롤링">
      <p class="text-sm text-gray-600">회사/직무 번호로 데이터를 수집해 DB에 반영합니다.</p>
      <div class="mt-4">
        <AppButton @click="$router.push({ name: 'collect' })">직무 추가</AppButton>
      </div>
    </AppCard>
  </section>
</template>

<script setup lang="ts">
import AppCard from '@/components/common/AppCard.vue'
import AppButton from '@/components/common/AppButton.vue'
</script>
