<template>
  <div class="rounded-lg border bg-white p-4 shadow-sm">
    <div class="mb-2 flex items-center justify-between">
      <h3 class="font-medium">{{ title }}</h3>
      <span class="rounded bg-gray-100 px-2 py-0.5 text-xs">{{ badge }}</span>
    </div>

    <div v-if="detail" class="space-y-2 text-sm">
      <div>
        <div class="mb-1 font-medium">Tone</div>
        <div class="flex flex-wrap gap-1">
          <span v-for="t in detail.tone_keywords" :key="t" class="rounded border px-2 py-0.5 text-xs text-gray-600">{{ t }}</span>
        </div>
      </div>
      <div>
        <div class="mb-1 font-medium">Sections</div>
        <div class="flex flex-wrap gap-1">
          <span v-for="s in detail.section_outline" :key="s" class="rounded bg-gray-50 px-2 py-0.5 text-xs text-gray-600">{{ s }}</span>
        </div>
      </div>
      <details class="mt-2">
        <summary class="cursor-pointer text-xs text-gray-500">예시 미리보기</summary>
        <pre class="mt-2 whitespace-pre-wrap rounded bg-gray-50 p-2 text-xs">{{ detail.example_jd_markdown || '예시 없음' }}</pre>
      </details>
    </div>

    <div v-else class="text-sm text-gray-500">데이터 없음</div>
  </div>
</template>

<script setup lang="ts">
import type { StyleDetail } from '@/api/types'
defineProps<{ title: string; badge: string; detail?: StyleDetail | null }>()
</script>
