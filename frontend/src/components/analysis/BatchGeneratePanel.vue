<template>
  <div class="rounded-lg border bg-white p-4 shadow-sm">
    <div class="mb-3 flex items-center justify-between">
      <h3 class="font-medium">사전 JD Generation (일배치 가정)</h3>
      <div class="text-xs text-gray-500">기본 3종 + 회사 스타일</div>
    </div>

    <div class="mb-3 flex gap-2">
      <button class="rounded bg-black px-3 py-2 text-sm text-white hover:bg-gray-800 disabled:opacity-50"
              :disabled="running || disabled" @click="$emit('run')">
        전체 실행
      </button>
      <span v-if="status !== 'idle'" class="rounded bg-gray-100 px-2 py-1 text-xs">{{ statusText }}</span>
    </div>

    <div class="mb-3 max-h-40 overflow-auto rounded border bg-gray-50 p-2 text-xs text-gray-700">
      <div v-if="!logs.length" class="text-gray-400">로그가 여기에 표시됩니다…</div>
      <div v-for="(line, i) in logs" :key="i">{{ line }}</div>
    </div>

    <div v-if="results.length" class="grid gap-3">
      <details v-for="(r, i) in results" :key="i" class="rounded border bg-white">
        <summary class="cursor-pointer px-3 py-2 text-sm">
          {{ r.label }} <span v-if="r.saved_id" class="ml-2 text-xs text-gray-500">(#{{ r.saved_id }})</span>
        </summary>
        <pre class="whitespace-pre-wrap p-3 text-xs">{{ r.markdown }}</pre>
      </details>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  disabled?: boolean
  running: boolean
  status: 'idle' | 'running' | 'done' | 'error'
  logs: string[]
  results: { label: string; markdown: string; saved_id?: number }[]
}>()
defineEmits<{ (e: 'run'): void }>()
const statusTextMap = { idle: '대기', running: '실행 중', done: '완료', error: '오류' }
const statusText = computed(() => statusTextMap[(defineProps as any).status])
</script>
