<!-- src/components/board/JDListTable.vue -->
<template>
  <div class="overflow-hidden rounded-lg border bg-white shadow-sm">
    <table class="min-w-full text-sm">
      <thead class="bg-gray-50">
        <tr>
          <th class="px-4 py-2 text-left">제목</th>
          <th class="px-4 py-2 text-left">상태</th>
          <th class="px-4 py-2 text-left">길이</th>
          <th class="px-4 py-2 text-left">품질</th>
          <th class="px-4 py-2 text-left">생성일시</th>
          <th class="px-4 py-2"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td colspan="6" class="px-4 py-6 text-center text-gray-500">불러오는 중…</td>
        </tr>
        <tr v-for="it in items" :key="it.id" class="border-t">
          <td class="px-4 py-2">{{ it.title }}</td>
          <td class="px-4 py-2">{{ it.status }}</td>
          <td class="px-4 py-2">{{ it.length ?? '-' }}</td>
          <td class="px-4 py-2">{{ it.quality_flags ?? 0 }}</td>
          <td class="px-4 py-2">{{ fmt(it.created_at) }}</td>
          <td class="px-4 py-2 text-right">
            <AppButton size="sm" variant="ghost">보기</AppButton>
            <AppButton size="sm" variant="ghost">편집</AppButton>
          </td>
        </tr>
        <tr v-if="!loading && items.length === 0">
          <td colspan="6" class="px-4 py-6 text-center text-gray-400">데이터가 없습니다.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import AppButton from '@/components/common/AppButton.vue'
import { fmt } from '@/utils/time'
import type { JDItem } from '@/api/types'

defineProps<{ items: JDItem[]; loading?: boolean }>()
</script>
