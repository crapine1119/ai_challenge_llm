<template>
  <div class="rounded-lg border bg-white p-4 shadow-sm">
    <div class="mb-1 flex items-center justify-between">
      <h3 class="truncate font-medium">{{ item.title || 'JD' }}</h3>
      <span class="rounded bg-gray-100 px-2 py-0.5 text-xs">{{ when }}</span>
    </div>

    <!-- 타자 효과: 전체 마크다운을 그대로 출력 (자르지 않음) -->
    <pre class="min-h-[4.5rem] whitespace-pre-wrap text-sm text-gray-800">
{{ shown }}<span v-if="typing" class="animate-pulse">▍</span>
    </pre>

    <div class="mt-3">
      <button class="rounded-md px-3 py-2 text-sm hover:bg-gray-100" @click="copy">복사</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import type { JDListItem } from '@/api/types'

const props = defineProps<{
  item: JDListItem
  delay?: number      // 카드가 나타난 후 타자 효과 시작 지연(ms)
  speed?: number      // 글자당 타자 속도(ms)
  instant?: boolean   // true면 타자 효과 없이 즉시 전체 출력
}>()

const typing = ref(false)
const shown = ref('')

const when = computed(() => {
  const d = new Date(props.item.created_at)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleString()
})

async function copy() {
  try {
    await navigator.clipboard.writeText(props.item.markdown || '')
    alert('클립보드에 복사되었습니다.')
  } catch {}
}

onMounted(() => {
  const target = (props.item.markdown || '').trim().replace(/\n{3,}/g, '\n\n') // 전체 사용
  if (props.instant) {
    shown.value = target
    typing.value = false
    return
  }

  const delay = props.delay ?? 400
  const speed = props.speed ?? 24
  let i = 0
  setTimeout(() => {
    typing.value = true
    const id = setInterval(() => {
      shown.value += target[i++] || ''
      if (i >= target.length) {
        typing.value = false
        clearInterval(id)
      }
    }, speed)
  }, delay)
})
</script>
