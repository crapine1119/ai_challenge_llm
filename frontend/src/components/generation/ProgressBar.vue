<template>
  <div>
    <div class="mb-1 text-xs text-gray-500">상태: {{ status }}</div>
    <div class="h-2 w-full overflow-hidden rounded bg-gray-200">
      <div class="h-2 bg-gray-800 transition-all" :style="{ width: progress + '%' }"></div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ status: 'idle'|'starting'|'streaming'|'refining'|'done'|'error' }>()
const progress = computed(() => {
  switch (props.status) {
    case 'starting': return 5
    case 'streaming': return 60
    case 'refining': return 90
    case 'done': return 100
    case 'error': return 100
    default: return 0
  }
})
</script>
