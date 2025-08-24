<template>
  <div class="overflow-hidden rounded-lg border bg-white shadow-sm">
    <table class="min-w-full text-sm">
      <thead class="bg-gray-50">
        <tr>
          <th class="px-4 py-2 text-left">제목</th>
          <th class="px-4 py-2 text-left">직무</th>
          <th class="px-4 py-2 text-left">회사 스타일</th>
          <th class="px-4 py-2 text-left">생성일시</th>
          <th class="px-4 py-2 text-left">상태</th>
          <th class="px-4 py-2">액션</th>
        </tr>
      </thead>
      <tbody>
        <!-- PLACEHOLDER: 실제 데이터 로딩/페이징 연동 -->
        <tr>
          <td class="px-4 py-2">[예시] AI 엔지니어 채용공고 v1</td>
          <td class="px-4 py-2">개발</td>
          <td class="px-4 py-2">기본(일반형)</td>
          <td class="px-4 py-2">2025-08-24 19:42</td>
          <td class="px-4 py-2">완료</td>
          <td class="px-4 py-2 text-right">
            <AppButton size="sm" variant="ghost">보기</AppButton>
            <AppButton size="sm" variant="ghost">편집</AppButton>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
<script setup lang="ts">
import AppButton from '@/components/common/AppButton.vue'
</script>
