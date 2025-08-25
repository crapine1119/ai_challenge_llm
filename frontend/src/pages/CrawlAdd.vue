<!-- src/pages/CrawlAdd.vue -->
<template>
  <div class="max-w-lg space-y-4">
    <h1 class="text-2xl font-semibold">직무 추가(크롤링)</h1>
    <div class="grid gap-2">
      <label>회사 ID</label>
      <input v-model.number="company_id" class="rounded border px-2 py-1" type="number" />
      <label>회사 코드</label>
      <input v-model="company_code" class="rounded border px-2 py-1" />
      <label>직무 코드</label>
      <input v-model="job_code" class="rounded border px-2 py-1" />
      <label>최대 상세 수집</label>
      <input v-model.number="max_details" class="rounded border px-2 py-1" type="number" />
      <AppButton @click="collect">수집 시작</AppButton>
    </div>

    <div v-if="result" class="rounded border bg-white p-4">
      <div>수집 성공: {{ result.success }}</div>
      <div>수집 건수: {{ result.collected_count }}</div>
      <div v-if="result.logs?.length">로그</div>
      <pre class="whitespace-pre-wrap text-xs text-gray-600">{{ result.logs?.join('\n') }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import AppButton from '@/components/common/AppButton.vue'
import { postCollectJobKorea } from '@/api/backend'
import type { CrawlResponse } from '@/api/types'

const company_id = ref(1517115)
const company_code = ref('jobkorea')
const job_code = ref('1000242')
const max_details = ref(3)

const result = ref<CrawlResponse | null>(null)

async function collect() {
  result.value = await postCollectJobKorea({
    company_id: company_id.value,
    company_code: company_code.value,
    job_code: job_code.value,
    max_details: max_details.value
  })
}
</script>
