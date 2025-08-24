<template>
  <div class="rounded-lg border bg-white p-4 shadow-sm">
    <div class="mb-1 flex items-center justify-between">
      <h3 class="font-medium">{{ template.name }}</h3>
      <span class="rounded bg-gray-100 px-2 py-0.5 text-xs">{{ template.source.toUpperCase() }}</span>
    </div>

    <!-- 요약을 타이핑처럼 노출 -->
    <p class="min-h-[3.5rem] whitespace-pre-wrap text-sm text-gray-700">
      <span v-if="!started" class="inline-block h-5 w-24 animate-pulse rounded bg-gray-200"></span>
      <span>{{ shown }}</span><span v-if="typing" class="animate-pulse">▍</span>
    </p>

    <!-- 섹션 칩 -->
    <div class="mt-2 flex flex-wrap gap-1">
      <span v-for="s in chipSections" :key="s" class="rounded border px-2 py-0.5 text-xs text-gray-600">
        {{ s }}
      </span>
      <span v-if="moreCount>0" class="rounded bg-gray-50 px-2 py-0.5 text-xs text-gray-500">+{{ moreCount }}</span>
    </div>

    <div class="mt-4 flex gap-2">
      <button class="rounded-md bg-black px-3 py-2 text-sm text-white hover:bg-gray-800" @click="$emit('select')">
        이 템플릿으로 시작
      </button>
      <button class="rounded-md px-3 py-2 text-sm hover:bg-gray-100" @click="$emit('preview')">미리보기</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue'
import type { JDTemplate } from '@/api/types'

const props = defineProps<{ template: JDTemplate; delay?: number; speed?: number }>()
defineEmits<{ (e: 'select'): void; (e: 'preview'): void }>()

const shown = ref('')
const typing = ref(false)
const started = ref(false)

const chipSections = computed(() => props.template.sections.slice(0, 4))
const moreCount = computed(() => Math.max(props.template.sections.length - 4, 0))

onMounted(() => {
  // 지연 후 타자 효과
  const delay = props.delay ?? 300
  const speed = props.speed ?? 18 // ms/char
  setTimeout(() => {
    started.value = true
    typing.value = true
    const full = props.template.summary || ''
    let i = 0
    const id = setInterval(() => {
      shown.value += full[i++] || ''
      if (i >= full.length) {
        typing.value = false
        clearInterval(id)
      }
    }, speed)
  }, delay)
})
</script>
