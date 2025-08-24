<template>
  <div class="rounded-lg border bg-white p-4 shadow-sm">
    <!-- 헤더 -->
    <div class="mb-2 flex items-center justify-between">
      <h3 class="font-medium">
        {{ title || detail?.style_label || 'Style' }}
      </h3>
      <span v-if="badge" class="rounded bg-gray-100 px-2 py-0.5 text-xs">{{ badge }}</span>
    </div>

    <!-- 본문: 스타일 상세 -->
    <div v-if="detail" class="space-y-3 text-sm text-gray-700">
      <!-- 톤 키워드 -->
      <div v-if="detail.tone_keywords?.length">
        <div class="mb-1 text-xs text-gray-500">Tone</div>
        <div class="flex flex-wrap gap-1">
          <span
            v-for="(t, i) in detail.tone_keywords"
            :key="i"
            class="rounded border px-2 py-0.5 text-xs"
          >{{ t }}</span>
        </div>
      </div>

      <!-- 섹션 아웃라인 -->
      <div v-if="detail.section_outline?.length">
        <div class="mb-1 text-xs text-gray-500">Sections</div>
        <ol class="list-decimal pl-4">
          <li v-for="(s, i) in detail.section_outline" :key="i">{{ s }}</li>
        </ol>
      </div>

      <!-- 템플릿 키 수 -->
      <div v-if="detail.templates && Object.keys(detail.templates).length">
        <div class="mb-1 text-xs text-gray-500">Templates</div>
        <ul class="list-disc pl-4">
          <li v-for="(v, k) in detail.templates" :key="k">{{ k }}</li>
        </ul>
      </div>

      <!-- 예시 미리보기(접기/펼치기) -->
      <details v-if="detail.example_jd_markdown" class="rounded border bg-gray-50 p-2">
        <summary class="cursor-pointer select-none text-xs text-gray-600">예시 미리보기</summary>
        <pre class="mt-2 whitespace-pre-wrap text-xs">{{ detail.example_jd_markdown }}</pre>
      </details>
    </div>

    <!-- 본문: 비어있음 -->
    <div v-else class="text-sm text-gray-500">
      회사 스타일이 아직 없습니다. 상단 <b>분석하기</b> 후 새로고침하세요.
    </div>
  </div>
</template>

<script setup lang="ts">
type StyleDetail = {
  style_label?: string
  tone_keywords?: string[]
  section_outline?: string[]
  example_jd_markdown?: string
  templates?: Record<string, string>
}

defineProps<{
  title?: string
  badge?: 'PRESET' | 'GENERATED' | string
  detail: StyleDetail | null
}>()
</script>
