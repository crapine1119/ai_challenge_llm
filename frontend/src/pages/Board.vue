<!-- src/pages/Board.vue -->
<template>
  <div class="space-y-4">
    <h1 class="text-2xl font-semibold">생성한 JD</h1>
    <div class="flex items-end gap-2">
      <label class="text-sm">회사</label>
      <input v-model="company_code" class="rounded border px-2 py-1 text-sm" />
      <label class="text-sm">직무</label>
      <input v-model="job_code" class="rounded border px-2 py-1 text-sm" />
      <AppButton size="sm" @click="reload">조회</AppButton>
    </div>
    <JDListTable :items="items" :loading="loading" />
  </div>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia'
import AppButton from '@/components/common/AppButton.vue'
import JDListTable from '@/components/board/JDListTable.vue'
import { useBoardStore } from '@/store/board'

const company_code = ref('jobkorea')
const job_code = ref('1000242')
const board = useBoardStore()
const { items, loading } = storeToRefs(board)

function reload() {
  board.loadList({ company_code: company_code.value, job_code: job_code.value, limit: 10 })
}

onMounted(reload)
</script>
